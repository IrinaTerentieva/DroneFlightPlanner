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

def compute_orientation(geom: LineString) -> int:
    """
    Compute bearing from North (0°) clockwise:
    0° = north, 90° = east, 180° = south, 270° = west.
    """
    x0, y0 = geom.coords[0]
    x1, y1 = geom.coords[-1]
    # note: atan2(dx, dy) gives angle from north
    bearing = (math.degrees(math.atan2(x1 - x0, y1 - y0)) + 360) % 360
    return int(round(bearing))

def orientation_category(angle: int) -> str:
    dirs = ['N','NNE','NE','ENE','E','ESE','SE','SSE',
            'S','SSW','SW','WSW','W','WNW','NW','NNW']
    return dirs[round(angle / 22.5) % 16]

def calculate_shadow(tree_h, solar_alt, solar_az):
    if solar_alt <= 0:
        return 0.0, 0.0
    alt_rad = math.radians(solar_alt)
    length = tree_h / math.tan(alt_rad)
    return length, (solar_az + 180) % 360

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

def split_line(geom: LineString, seg_len: float):
    """Divide a line into equal‐length segments (last may be shorter)."""
    total = geom.length
    if total <= seg_len:
        return [geom]
    segments = []
    distances = np.arange(0, total, seg_len).tolist() + [total]
    for d0, d1 in zip(distances[:-1], distances[1:]):
        seg = LineString([
            geom.interpolate(d0, normalized=False),
            geom.interpolate(d1, normalized=False)
        ])
        segments.append(seg)
    return segments

def compute_total_duration(wins):
    # wins: list of (start,end) datetimes
    total = sum((e - s).total_seconds() for s,e in wins)
    return round(total/3600, 2)  # hours, two decimals

@hydra.main(version_base="1.1", config_path="../config", config_name="config")
def main(cfg: DictConfig):
    # 1) Load vector & CHM
    gdf = gpd.read_file(cfg.vector_path)
    chm = rasterio.open(cfg.chm_path)

    # 2) Precompute common solar series & daylight bounds
    freq = cfg.freq.replace("T","min")
    times = pd.date_range(f"{cfg.date} 00:00", f"{cfg.date} 23:59",
                          freq=freq, tz=cfg.timezone)
    solpos = pvlib.solarposition.get_solarposition(
        times, cfg.latitude, cfg.longitude, altitude=cfg.elevation
    ).tz_convert(cfg.timezone)
    elev = solpos["apparent_elevation"]
    day_times = times[elev > 0]
    day_start, day_end = (day_times[0], day_times[-1]) if len(day_times)>0 else (times[0], times[-1])

    # 3) For each input line, split into segments
    segs = []
    for idx, row in gdf.iterrows():
        for seg in split_line(row.geometry, cfg.segment_length):
            segs.append({
                "orig_index": idx,
                "geometry": seg
            })
    sgdf = gpd.GeoDataFrame(segs, crs=gdf.crs)

    # 4) Compute per‐segment attributes & flight windows
    results = []
    for seg in sgdf.itertuples():
        ori = compute_orientation(seg.geometry)
        category = orientation_category(ori)

        # 4a) buffer CHM and sample 75th percentile canopy height
        buf = seg.geometry.buffer(cfg.segment_buffer_radius)
        out_image, out_transform = rio_mask(
            chm, [mapping(buf)], crop=True, filled=False
        )
        masked_band = out_image[0]
        # extract valid data
        if hasattr(masked_band, 'compressed'):
            vals = masked_band.compressed()
        else:
            arr = masked_band.filled(np.nan)
            vals = arr[~np.isnan(arr)]
        # compute 75th percentile on a writable array
        tree_h = float(np.percentile(vals.copy(), 75)) if vals.size > 0 else cfg.tree_height

        # 4b) build buffer% series
        pct = []
        for sp in solpos.itertuples():
            length, direction = calculate_shadow(
                tree_h, sp.apparent_elevation, sp.azimuth
            )
            pct.append(calc_buffer_pct(
                length, direction, cfg.buffer_width_m, ori
            ))
        series = pd.Series(pct, index=times)

        # 4c) windows for this orientation
        thresh = cfg.flight_window.max_buffer_pct
        wins = find_windows(times, series, elev, thresh, day_start, day_end)

        duration = compute_total_duration(wins)

        results.append({
            "orig_index": seg.orig_index,
            "orientation": ori,
            "dir_category": category,
            "canopy_h75": tree_h,
            "flight_windows": format_windows(wins),
            "flight_duration_h": duration,
            "geometry": seg
        })

    out_gdf = gpd.GeoDataFrame(results, geometry=[s.geometry for s in sgdf.itertuples()],
                               crs=gdf.crs)
    output_path = cfg.vector_path.replace(".gpkg","_segments_with_windows.gpkg")
    out_gdf.to_file(output_path, driver="GPKG")
    print(f"Saved per‐segment results to {output_path}")

if __name__ == "__main__":
    main()
