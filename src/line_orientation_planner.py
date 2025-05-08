# src/line_flight_planner.py

import math
import random
import geopandas as gpd
import pandas as pd
import pvlib
import hydra
from omegaconf import DictConfig
from shapely.geometry import LineString

def calculate_shadow(tree_height: float, solar_alt: float, solar_az: float):
    if solar_alt <= 0:
        return 0.0, 0.0
    alt_rad = math.radians(solar_alt)
    return tree_height / math.tan(alt_rad), (solar_az + 180) % 360

def calc_buffer_percentage(shadow_length: float, shadow_direction: float,
                           buffer_width: float, line_orientation: float):
    # project shadow onto the buffer perpendicular to the line
    perp = (line_orientation + 90) % 360
    delta = math.radians(shadow_direction - perp)
    comp = abs(math.cos(delta)) * shadow_length
    return (min(comp, buffer_width) / buffer_width) * 100

def find_flight_windows(times, series, elevation, threshold, day_start, day_end):
    mask = (series <= threshold) & (elevation > 0)
    periods, start, prev = [], None, None
    for t, ok in zip(times, mask):
        if ok and start is None and day_start <= t <= day_end:
            start = t
        if start is not None and (((not ok) and t <= day_end) or t == times[-1]):
            end = prev if not ok else t
            # clamp to daylight
            end = min(end, day_end)
            periods.append((start, end))
            start = None
        prev = t
    return periods

def format_windows(wins):
    return ";".join(f"{s.strftime('%H:%M')}-{e.strftime('%H:%M')}" for s,e in wins)

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

@hydra.main(version_base="1.1", config_path="../config", config_name="config")
def main(cfg: DictConfig):
    # 1) Read lines
    gdf = gpd.read_file(cfg.vector_path)

    # 2) Orientation & compass category
    gdf['orientation']    = gdf.geometry.apply(compute_orientation)
    gdf['dir_category']   = gdf['orientation'].apply(orientation_category)

    # 3) Build time index, convert freq alias
    freq = cfg.freq.replace('T','min')
    times = pd.date_range(f"{cfg.date} 00:00", f"{cfg.date} 23:59",
                          freq=freq, tz=cfg.timezone)

    # 4) Solar positions
    solpos = pvlib.solarposition.get_solarposition(
        times, cfg.latitude, cfg.longitude, altitude=cfg.elevation
    ).tz_convert(cfg.timezone)
    elev = solpos['apparent_elevation']

    # sunrise/sunset bounds
    daylight = elev > 0
    day_times = times[daylight]
    if not day_times.empty:
        day_start, day_end = day_times[0], day_times[-1]
    else:
        day_start, day_end = times[0], times[-1]

    # 5) Per-line windows
    windows_list = []
    for _, row in gdf.iterrows():
        ori = row['orientation']
        axis = 'NS'  # now we allow any orientation
        tree_h = cfg.tree_height

        # compute buffer% series for this orientation
        buf = []
        for alt, az in zip(solpos['apparent_elevation'], solpos['azimuth']):
            length, direction = calculate_shadow(tree_h, alt, az)
            buf.append(calc_buffer_percentage(length, direction,
                                              cfg.buffer_width_m, ori))
        series = pd.Series(buf, index=times)

        # find windows within daylight
        threshold = cfg.flight_window.max_buffer_pct
        wins = find_flight_windows(times, series, elev,
                                   threshold, day_start, day_end)
        windows_list.append(format_windows(wins))

    # 6) Save results
    gdf[cfg.output_field] = windows_list
    print(gdf[['orientation', 'dir_category', 'flight_windows']].head(30))
    out = cfg.vector_path.replace('.gpkg','_with_windows.gpkg')
    gdf.to_file(out, driver='GPKG')
    print(f"Saved to {out}")

if __name__ == "__main__":
    main()


