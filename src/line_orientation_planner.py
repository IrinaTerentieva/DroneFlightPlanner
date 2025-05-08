# src/line_flight_planner.py

import math
import random
import geopandas as gpd
import pandas as pd
import pvlib
import hydra
from omegaconf import DictConfig
from shapely.geometry import LineString

from src.orientation_utils import (
    compute_orientation,
    orientation_category,
    calculate_shadow,
    calc_buffer_percentage,
    find_flight_windows,
    format_windows
)

@hydra.main(version_base="1.1", config_path="../config", config_name="orientation_planner")
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


