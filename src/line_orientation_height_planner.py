# src/line_flight_planner.py
import numpy as np
from rasterio.mask import mask as rio_mask
from shapely.geometry import mapping

import math
import geopandas as gpd
import pandas as pd
import numpy as np
import pvlib
import rasterio
import rasterio.mask
import hydra
from omegaconf import DictConfig
from shapely.geometry import LineString, mapping

# src/line_flight_planner.py

import math
import geopandas as gpd
import pandas as pd
import numpy as np
import pvlib
import rasterio
from rasterio.mask import mask as rio_mask
import hydra
from omegaconf import DictConfig
from shapely.geometry import LineString, mapping

# --- helpers ---

def compute_orientation(geom: LineString) -> int:
    x0, y0 = geom.coords[0]
    x1, y1 = geom.coords[-1]
    ang = (math.degrees(math.atan2(x1 - x0, y1 - y0)) + 360) % 360
    return int(round(ang))

def orientation_category(angle: int) -> str:
    dirs = ['N','NNE','NE','ENE','E','ESE','SE','SSE',
            'S','SSW','SW','WSW','W','WNW','NW','NNW']
    return dirs[round(angle / 22.5) % 16]

def calculate_shadow(tree_h, solar_alt, solar_az):
    if solar_alt <= 0:
        return 0.0, 0.0
    alt_rad = math.radians(solar_alt)
    return tree_h / math.tan(alt_rad), (solar_az + 180) % 360

def calc_buffer_pct(shadow_len, shadow_dir, buf_w, line_ori):
    perp = (line_ori + 90) % 360
    delta = math.radians(shadow_dir - perp)
    comp = abs(math.cos(delta)) * shadow_len
    return (min(comp, buf_w) / buf_w) * 100

def find_windows(times, series, elev, thresh, start, end):
    mask = (series <= thresh) & (elev > 0)
    periods, st, prev = [], None, None
    for t, ok in zip(times, mask):
        if ok and st is None and start <= t <= end:
            st = t
        if st is not None and (((not ok) and t <= end) or t == times[-1]):
            en = prev if not ok else t
            periods.append((max(st, start), min(en, end)))
            st = None
        prev = t
    return periods

def format_windows(wins):
    return ";".join(f"{s.strftime('%H:%M')}-{e.strftime('%H:%M')}" for s,e in wins)

def compute_total_duration(wins):
    total = sum((e - s).total_seconds() for s,e in wins)
    return round(total/3600, 2)

def split_line(geom: LineString, seg_len: float):
    total = geom.length
    if total <= seg_len:
        return [geom]
    segs = []
    dists = np.arange(0, total, seg_len).tolist() + [total]
    for d0, d1 in zip(dists[:-1], dists[1:]):
        segs.append(LineString([geom.interpolate(d0), geom.interpolate(d1)]))
    return segs

def categorize_window(win_str):
    """Bucket window string into pilot-friendly categories."""
    if not win_str:
        return "no fly window"
    intervals = win_str.split(';')
    # compute total flight hours
    total_sec = sum(
        (pd.to_datetime(iv.split('-')[1]) - pd.to_datetime(iv.split('-')[0])).seconds
        for iv in intervals
    )
    total_hr = total_sec / 3600
    # determine period segments
    periods = set()
    for iv in intervals:
        start_hour = int(iv.split('-')[0][:2])
        if start_hour < 10:
            periods.add('morning')
        elif start_hour < 15:
            periods.add('noon')
        else:
            periods.add('evening')
    # categorize
    if total_hr >= 8:
        return "fly any time"
    if total_hr >= 4:
        if periods == {'morning', 'evening'}:
            return "fly long morning+evening"
        if 'noon' in periods:
            return "fly long noon"
    if total_hr < 2.5:
        return "fly extra short"
    if periods <= {'morning', 'evening'}:
        return "fly short morning+evening"
    return "fly short noon"



# --- main ---

@hydra.main(version_base="1.1", config_path="../config", config_name="config")
def main(cfg: DictConfig):
    # load data
    gdf = gpd.read_file(cfg.vector_path)
    chm = rasterio.open(cfg.chm_path)

    # solar series
    freq = cfg.freq.replace("T","min")
    times = pd.date_range(f"{cfg.date} 00:00", f"{cfg.date} 23:59",
                          freq=freq, tz=cfg.timezone)
    sol = pvlib.solarposition.get_solarposition(
        times, cfg.latitude, cfg.longitude, altitude=cfg.elevation
    ).tz_convert(cfg.timezone)
    elev = sol["apparent_elevation"]
    dt = times[elev>0]
    start, end = (dt[0], dt[-1]) if len(dt)>0 else (times[0],times[-1])

    # collect all window strings
    all_windows = []

    # process segments
    rows = []
    for idx, row in gdf.iterrows():
        for seg in split_line(row.geometry, cfg.segment_length):
            # orientation
            ori = compute_orientation(seg)
            cat = orientation_category(ori)

            # canopy height
            buf = seg.buffer(cfg.segment_buffer_radius)
            img, _ = rio_mask(chm, [mapping(buf)], crop=True, filled=False)
            band = img[0]
            vals = band.compressed() if hasattr(band,"compressed") else band.filled(np.nan)[~np.isnan(band)]
            tree_h = float(np.percentile(vals.copy(),75)) if vals.size>0 else cfg.tree_height

            # buffer% series
            pct = [ calc_buffer_pct(*calculate_shadow(tree_h, sp.apparent_elevation, sp.azimuth),
                                   cfg.buffer_width_m, ori) for sp in sol.itertuples() ]
            series = pd.Series(pct, index=times)

            # windows & duration
            wins = find_windows(times, series, elev,
                                cfg.flight_window.max_buffer_pct, start, end)
            win_str = format_windows(wins)
            dur = compute_total_duration(wins)
            all_windows.append(win_str)

            # category
            win_cat = categorize_window(win_str)

            rows.append({
                "orig_index": idx,
                "orientation": ori,
                "dir_category": cat,
                "canopy_h75": tree_h,
                "flight_windows": win_str,
                "flight_duration_h": dur,
                "window_category": win_cat,
                "geometry": seg
            })

    # unique windows
    uniq = sorted(set(all_windows))
    print("Unique windows:", uniq)

    out = gpd.GeoDataFrame(rows, crs=gdf.crs)
    path = cfg.vector_path.replace(".gpkg","_segments_with_windows.gpkg")
    out.to_file(path, driver="GPKG")
    print(f"Saved to {path}")

if __name__=="__main__":
    main()
