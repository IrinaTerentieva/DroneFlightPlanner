# src/shadow_calculator.py
# ------------------------
import math
from datetime import datetime
import numpy as np
import pandas as pd
import pvlib
import matplotlib.pyplot as plt

import hydra
from omegaconf import DictConfig


def calculate_shadow(tree_height, solar_altitude, solar_azimuth):
    if solar_altitude <= 0:
        return None, None
    alt_rad = math.radians(solar_altitude)
    length = tree_height / math.tan(alt_rad)
    direction = (solar_azimuth + 180) % 360
    return length, direction


def calc_ns_ew_pct(length, direction):
    if length is None:
        return None, None
    rad = math.radians(direction)
    ns = length * abs(math.sin(rad))
    ew = length * abs(math.cos(rad))
    return round((ns / length) * 100, 0), round((ew / length) * 100, 0)


@hydra.main(version_base=None, config_path="../config", config_name="config")
def main(cfg: DictConfig):
    # 1) Generate timestamps
    times = pd.date_range(
        start=f"{cfg.date} 00:00:00",
        end=f"{cfg.date} 23:59:59",
        freq="H",
        tz=cfg.timezone
    )

    # 2) Solar positions
    solpos = pvlib.solarposition.get_solarposition(
        times, cfg.latitude, cfg.longitude, altitude=cfg.elevation
    )
    solpos.index = solpos.index.tz_convert(cfg.timezone)

    # 3) Calculate shadows & directions
    solpos["shadow_len"], solpos["shadow_dir"] = zip(*solpos.apply(
        lambda r: calculate_shadow(cfg.tree_height, r["apparent_elevation"], r["azimuth"]), axis=1
    ))

    # 4) Split into NS/EW percentages
    solpos["ns_pct"], solpos["ew_pct"] = zip(*solpos.apply(
        lambda r: calc_ns_ew_pct(r["shadow_len"], r["shadow_dir"]), axis=1
    ))

    # 5) Tidy up
    df = solpos.reset_index()[[
        "index", "apparent_elevation", "azimuth", "shadow_len", "shadow_dir", "ns_pct", "ew_pct"
    ]]
    df.columns = [
        "Time", "Solar Alt (°)", "Solar Azim (°)",
        "Shadow Length (m)", "Shadow Dir (°)",
        "NS Shadow (%)", "EW Shadow (%)"
    ]
    df["Time"] = df["Time"].dt.strftime("%H:%M")
    df.fillna(0, inplace=True)
    df[["Shadow Length (m)", "Shadow Dir (°)"]] = df[["Shadow Length (m)", "Shadow Dir (°)"]].astype(int)

    # 6) Display & plot
    print(df.to_string(index=False))
    plt.figure(figsize=(12, 6))
    plt.plot(df["Time"], df["NS Shadow (%)"], marker="o", label="NS %")
    plt.plot(df["Time"], df["EW Shadow (%)"], marker="o", label="EW %")
    plt.xlabel("Time (HH:MM)")
    plt.ylabel("Shadow Coverage (%)")
    plt.title(f"Shadow Coverage on {cfg.date}")
    plt.xticks(rotation=45)
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
