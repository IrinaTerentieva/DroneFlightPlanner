# src/orientation_planner.py

import geopandas as gpd
import pandas as pd
import pvlib
import hydra
from omegaconf import DictConfig

from src.utils import (
    compute_orientation,
    orientation_category,
    calculate_shadow,
    calc_buffer_percentage,
    find_flight_windows,
    format_windows,
)

@hydra.main(version_base="1.1", config_path="../config", config_name="config")
def main(cfg: DictConfig):
    # 0) short-hands
    loc = cfg.location
    stp = cfg.simple_time_planner
    op  = cfg.orientation_planner

    # 1) Read input
    gdf = gpd.read_file(op.vector_path)

    # 2) Add orientation columns
    gdf["orientation"]    = gdf.geometry.apply(compute_orientation)
    gdf["dir_category"]   = gdf["orientation"].apply(orientation_category)

    # 3) Build time index
    freq  = loc.freq.replace("T", "min")
    times = pd.date_range(
        f"{loc.date} 00:00", f"{loc.date} 23:59",
        freq=freq, tz=loc.timezone
    )

    # 4) Solar angles
    solpos = pvlib.solarposition.get_solarposition(
        times, loc.latitude, loc.longitude, altitude=loc.elevation
    ).tz_convert(loc.timezone)
    elev = solpos["apparent_elevation"]

    # 5) Daylight window
    day_mask  = elev > 0
    day_times = times[day_mask]
    if len(day_times):
        day_start, day_end = day_times[0], day_times[-1]
    else:
        day_start, day_end = times[0], times[-1]

    # 6) Compute flight windows for each line
    windows_list = []
    for _, row in gdf.iterrows():
        ori    = row["orientation"]
        tree_h = stp.tree_height

        # build percent-shadow‐in-buffer series
        pct = []
        for alt, az in zip(solpos["apparent_elevation"], solpos["azimuth"]):
            length, direction = calculate_shadow(tree_h, alt, az)
            pct.append(calc_buffer_percentage(
                length,
                direction,
                stp.buffer_width_m,
                ori
            ))
        series = pd.Series(pct, index=times)

        # find contiguous daylight windows under threshold
        thresh = stp.flight_window.max_ns_shadow_pct
        wins   = find_flight_windows(
            times, series, elev,
            thresh, day_start, day_end
        )
        windows_list.append(format_windows(wins))

    # 7) Save back to GPKG
    gdf[op.output_field] = windows_list
    print(gdf[["orientation", "dir_category", op.output_field]].head(10))

    out_path = op.vector_path.replace(".gpkg", "_with_windows.gpkg")
    gdf.to_file(out_path, driver="GPKG")
    print(f"Saved to {out_path}")

if __name__ == "__main__":
    main()
