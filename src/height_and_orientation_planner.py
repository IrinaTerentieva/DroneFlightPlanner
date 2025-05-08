import geopandas as gpd
import pandas as pd
import numpy as np
import pvlib
import rasterio
from rasterio.mask import mask as rio_mask
import hydra
from omegaconf import DictConfig
from shapely.geometry import mapping

from src.utils import (
    compute_orientation,
    orientation_category,
    calculate_shadow,
    calc_buffer_pct,
    find_windows,
    format_windows,
    compute_total_duration,
    split_line,
    categorize_window,
)

@hydra.main(version_base="1.1", config_path="../config", config_name="config")
def main(cfg: DictConfig):
    # 0) Shorthands for each config block
    loc  = cfg.location
    hop  = cfg.height_and_orientation_planner
    stp  = cfg.simple_time_planner

    # 1) Load vector & CHM
    gdf = gpd.read_file(hop.segmentation.vector_path)
    chm = rasterio.open(hop.chm.path)

    # 2) Precompute solar series & daylight window
    freq = loc.freq.replace("T","min")
    times = pd.date_range(
        f"{loc.date} 00:00", f"{loc.date} 23:59",
        freq=freq, tz=loc.timezone
    )
    solpos = pvlib.solarposition.get_solarposition(
        times, loc.latitude, loc.longitude, altitude=loc.elevation
    ).tz_convert(loc.timezone)
    elev = solpos["apparent_elevation"]
    day_times = times[elev > 0]
    if len(day_times):
        day_start, day_end = day_times[0], day_times[-1]
    else:
        day_start, day_end = times[0], times[-1]

    # 3) Split into segments
    segs = []
    for idx, row in gdf.iterrows():
        for seg in split_line(row.geometry, hop.segmentation.segment_length):
            segs.append({"orig_index": idx, "geometry": seg})
    sgdf = gpd.GeoDataFrame(segs, crs=gdf.crs)

    # 4) Compute per‐segment attributes & flight windows
    rows = []
    all_windows = []
    for seg in sgdf.itertuples():
        ori = compute_orientation(seg.geometry)
        cat = orientation_category(ori)

        # 4a) 75th percentile canopy height around segment
        buf_poly = seg.geometry.buffer(hop.chm.segment_buffer_radius)
        img, _ = rio_mask(chm, [mapping(buf_poly)], crop=True, filled=False)
        band = img[0]
        if hasattr(band, "compressed"):
            vals = band.compressed()
        else:
            arr = band.filled(np.nan)
            vals = arr[~np.isnan(arr)]
        tree_h = float(np.percentile(vals.copy(), 75)) if vals.size else sh.tree_height

        # 4b) Build buffer‐% series along segment orientation
        pct = []
        for sp in solpos.itertuples():
            length, direction = calculate_shadow(tree_h, sp.apparent_elevation, sp.azimuth)
            pct.append(calc_buffer_pct(length, direction, stp.buffer_width_m, ori))
        series = pd.Series(pct, index=times)

        # 4c) Find flight windows under threshold
        thresh = stp.flight_window.preferred_shadow_pct
        wins = find_windows(times, series, elev, thresh, day_start, day_end)
        win_str = format_windows(wins)
        all_windows.append(win_str)

        # 4d) Compute duration and category
        dur = compute_total_duration(wins)
        win_cat = categorize_window(win_str)

        rows.append({
            "orig_index":      seg.orig_index,
            "orientation":     ori,
            "dir_category":    cat,
            "canopy_h75":      tree_h,
            "flight_windows":  win_str,
            "flight_duration": dur,
            "window_category": win_cat,
            "geometry":        seg.geometry
        })

    # 5) Report unique patterns and save
    uniq = sorted(set(all_windows))
    print("Unique windows:", uniq)

    out_gdf = gpd.GeoDataFrame(rows, crs=gdf.crs)
    out_path = hop.segmentation.vector_path.replace(".gpkg", "_segments_with_windows.gpkg")
    out_gdf.to_file(out_path, driver="GPKG")
    print(f"Saved to {out_path}")

if __name__ == "__main__":
    main()
