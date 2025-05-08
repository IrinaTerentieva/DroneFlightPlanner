import rasterio.mask
import geopandas as gpd
import pandas as pd
import numpy as np
import pvlib
import rasterio
from rasterio.mask import mask as rio_mask
import hydra
from omegaconf import DictConfig
from shapely.geometry import LineString, mapping
from src.height_orientation_utils import (compute_orientation,
                                          orientation_category,
                                          calculate_shadow,
                                          calc_buffer_pct,
                                          find_windows,
                                          format_windows,
                                          compute_total_duration,
                                          split_line,
                                          categorize_window
                                          )

# --- main ---

@hydra.main(version_base="1.1", config_path="../config", config_name="height_and_orientation_planner")
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
