# src/shadow_calculator.py

import math
import pandas as pd
import pvlib
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import hydra
from omegaconf import DictConfig
from matplotlib.ticker import FuncFormatter
from src.utils import (
    calculate_shadow,
    calc_buffer_percentage,
    find_flight_windows,
    shade_contiguous,
    format_time
)

@hydra.main(version_base=None, config_path="../config", config_name="config")
def main(cfg: DictConfig):
    # shorthand for nested blocks
    loc  = cfg.location
    print('Location config: ', loc)
    stp  = cfg.simple_time_planner
    print('Simple time planner config: ', stp)

    # 1) Generate timestamps every cfg.location.freq
    times = pd.date_range(
        f"{loc.date} 00:00",
        f"{loc.date} 23:59",
        freq=loc.freq,
        tz=loc.timezone
    )

    # 2) Compute solar positions
    solpos = pvlib.solarposition.get_solarposition(
        times, loc.latitude, loc.longitude, altitude=loc.elevation
    ).tz_convert(loc.timezone)

    # 3) Compute buffer coverage (NS vs EW)
    records = []
    for _, row in solpos.iterrows():
        length, direction = calculate_shadow(
            stp.tree_height,
            row["apparent_elevation"],
            row["azimuth"]
        )
        # NS = line_ori=0°, EW = 90°
        ns_pct = calc_buffer_percentage(length, direction, stp.buffer_width_m, 0)
        ew_pct = calc_buffer_percentage(length, direction, stp.buffer_width_m, 90)
        records.append({
            "Elevation": row["apparent_elevation"],
            "NS Shadow (%)": ns_pct,
            "EW Shadow (%)": ew_pct
        })

    df = pd.DataFrame(records, index=times.tz_convert(loc.timezone).tz_localize(None))

    # 4) Print metrics
    df_print = df.copy()
    df_print["Time"] = df_print.index.strftime("%H:%M")
    print(df_print[["Time", "Elevation", "NS Shadow (%)", "EW Shadow (%)"]].to_string(index=False))

    # 5) Peak sun
    peak = df["Elevation"].idxmax()
    print(f"\nPeak sun at: {peak.strftime('%H:%M')} (Elevation: {df.at[peak,'Elevation']:.1f}°)")

    # 6) Flight windows
    ns_windows = find_flight_windows(df.index, df["NS Shadow (%)"], df["Elevation"],
                                     stp.flight_window.max_ns_shadow_pct,
                                     df.index[0], df.index[-1])
    ew_windows = find_flight_windows(df.index, df["EW Shadow (%)"], df["Elevation"],
                                     stp.flight_window.max_ew_shadow_pct,
                                     df.index[0], df.index[-1])

    print("\nRecommended NS flight windows:")
    for s, e in ns_windows:
        print(f" - {s.strftime('%H:%M')} to {e.strftime('%H:%M')}")
    print("\nRecommended EW flight windows:")
    for s, e in ew_windows:
        print(f" - {s.strftime('%H:%M')} to {e.strftime('%H:%M')}")

    # 7) Plot
    fmt = FuncFormatter(format_time)
    major_locator = mdates.HourLocator(interval=1)
    title_font, label_font, tick_font, leg_font = 18, 14, 12, 12

    # NS plot
    fig, ax = plt.subplots(figsize=tuple(stp.plot.figure_size))
    day = df["Elevation"] >= 0
    ax.plot(df.index[day], df["NS Shadow (%)"][day], color="teal", linewidth=2.5, label="NS")
    shade_contiguous(ax, df.index, df["Elevation"] < 0, color="blue", alpha=0.2)
    for s, e in ns_windows:
        ax.axvspan(s, e, color="gold", alpha=0.3)
    ax.axvline(peak, color="red", linestyle="--", linewidth=2, label="Peak Sun")
    ax.set_title(stp.plot.title, fontsize=title_font)
    ax.set_xlabel("Time", fontsize=label_font)
    ax.set_ylabel("NS Shadow (%)", fontsize=label_font)
    ax.xaxis.set_major_locator(major_locator)
    ax.xaxis.set_major_formatter(fmt)
    ax.tick_params(labelsize=tick_font)
    ax.grid(True, linestyle="--", color="gray")
    ax.legend(fontsize=leg_font)
    plt.tight_layout()
    plt.show()

    # EW plot
    fig, ax = plt.subplots(figsize=tuple(stp.plot.figure_size))
    ax.plot(df.index[day], df["EW Shadow (%)"][day], color="purple", linewidth=2.5, label="EW")
    shade_contiguous(ax, df.index, df["Elevation"] < 0, color="blue", alpha=0.2)
    for s, e in ew_windows:
        ax.axvspan(s, e, color="gold", alpha=0.3)
    ax.axvline(peak, color="red", linestyle="--", linewidth=2, label="Peak Sun")
    ax.set_title(stp.plot.title, fontsize=title_font)
    ax.set_xlabel("Time", fontsize=label_font)
    ax.set_ylabel("EW Shadow (%)", fontsize=label_font)
    ax.xaxis.set_major_locator(major_locator)
    ax.xaxis.set_major_formatter(fmt)
    ax.tick_params(labelsize=tick_font)
    ax.grid(True, linestyle="--", color="gray")
    ax.legend(fontsize=leg_font)
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    main()
