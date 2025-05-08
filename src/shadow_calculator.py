# src/shadow_calculator.py
import math
import pandas as pd
import pvlib
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import hydra
from omegaconf import DictConfig
from matplotlib.ticker import FuncFormatter
from src.utils import calculate_shadow, calc_buffer_percentage, find_flight_windows, shade_contiguous, format_time

@hydra.main(version_base=None, config_path="../config", config_name="shadow_calculator")
def main(cfg: DictConfig):
    # 1) Generate timestamps every 15 minutes
    times = pd.date_range(
        f"{cfg.date} 00:00", f"{cfg.date} 23:59", freq=cfg.freq, tz=cfg.timezone
    )

    # 2) Compute solar positions
    solpos = pvlib.solarposition.get_solarposition(
        times, cfg.latitude, cfg.longitude, altitude=cfg.elevation
    ).tz_convert(cfg.timezone)

    # 3) Compute buffer coverage
    records = []
    for t, row in solpos.iterrows():
        length, direction = calculate_shadow(
            cfg.tree_height, row['apparent_elevation'], row['azimuth']
        )
        ns_buf = calc_buffer_percentage(length, direction, cfg.buffer_width_m, axis='NS')
        ew_buf = calc_buffer_percentage(length, direction, cfg.buffer_width_m, axis='EW')
        records.append({
            'Elevation': row['apparent_elevation'],
            'NS Buffer (%)': ns_buf,
            'EW Buffer (%)': ew_buf
        })
    df = pd.DataFrame(records, index=times.tz_convert(cfg.timezone).tz_localize(None))

    # 4) Print HH:MM and metrics
    df_print = df.copy()
    df_print['Time'] = df_print.index.strftime('%H:%M')
    print(df_print[['Time', 'Elevation', 'NS Buffer (%)', 'EW Buffer (%)']].to_string(index=False))

    # 5) Peak sun time
    peak_time = df['Elevation'].idxmax()
    print(f"\nPeak sun at: {peak_time.strftime('%H:%M')} "
          f"(Elevation: {df.at[peak_time, 'Elevation']:.1f}°)")

    # 6) Flight windows
    ns_windows = find_flight_windows(
        df, 'NS Buffer (%)', cfg.flight_window.max_ns_shadow_pct
    )
    ew_windows = find_flight_windows(
        df, 'EW Buffer (%)', cfg.flight_window.max_ew_shadow_pct
    )
    print("\nRecommended NS flight windows:")
    for s, e in ns_windows:
        print(f" - {s.strftime('%H:%M')} to {e.strftime('%H:%M')}")
    print("\nRecommended EW flight windows:")
    for s, e in ew_windows:
        print(f" - {s.strftime('%H:%M')} to {e.strftime('%H:%M')}")

    # 7) Plot settings
    major_locator = mdates.HourLocator(interval=1)
    major_formatter = FuncFormatter(format_time)
    title_font, label_font, tick_font, leg_font = 18, 14, 12, 12

            # NS Buffer plot
    fig, ax = plt.subplots(figsize=tuple(cfg.plot.figure_size))
    day_mask = df['Elevation'] >= 0
    # plot daytime buffer percent
    ax.plot(df.index[day_mask], df['NS Buffer (%)'][day_mask], color='teal', linewidth=2.5, label='NS Buffer (%)')

    # night shading
    shade_contiguous(ax, df.index, df['Elevation'] < 0, color='blue', alpha=0.2)

    # highlight flight windows (continuous spans)
    print('NS windows: ', ns_windows)
    for start, end in ns_windows:
        ax.axvspan(start, end, color='yellow', alpha=0.3)
    ax.axvline(peak_time, color='red', linestyle='--', linewidth=2, label='Peak Sun')
    ax.set_title(f"NS Shadow (%) on {cfg.date}", fontsize=title_font)
    ax.set_xlabel('Time', fontsize=label_font)
    ax.set_ylabel('NS Buffer (%)', fontsize=label_font)
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=1))
    ax.xaxis.set_major_formatter(FuncFormatter(format_time))
    # ax.xaxis.set_minor_locator(mdates.MinuteLocator(byminute=[0,15,30,45]))
    ax.tick_params(axis='both', labelsize=tick_font)
    ax.grid(which='major', axis='x', linestyle='--', color='gray')
    ax.grid(which='minor', axis='x', linestyle=':', color='lightgray')
    ax.legend(loc='upper right', fontsize=leg_font)
    plt.tight_layout()
    plt.show()

    # EW Buffer plot
    fig, ax = plt.subplots(figsize=tuple(cfg.plot.figure_size))
    ew_mask = (df['EW Buffer (%)'] <= cfg.flight_window.preferred_ew_shadow_pct) & day_mask
    ax.plot(df.index[day_mask], df['EW Buffer (%)'][day_mask], color='purple', linewidth=2.5, label='EW Buffer (%)')
    shade_contiguous(ax, df.index, df['Elevation'] < 0, color='blue', alpha=0.2)

    print('EW windows: ', ew_windows)
    for start, end in ew_windows:
        ax.axvspan(start, end, color='yellow', alpha=0.3)

    ax.axvline(peak_time, color='red', linestyle='--', linewidth=2, label='Peak Sun')
    ax.set_title(f"EW Shadow (%) on {cfg.date}", fontsize=title_font)
    ax.set_xlabel('Time', fontsize=label_font)
    ax.set_ylabel('EW Buffer (%)', fontsize=label_font)
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=1))
    ax.xaxis.set_major_formatter(FuncFormatter(format_time))
    # ax.xaxis.set_minor_locator(mdates.MinuteLocator(byminute=[0,15,30,45]))
    ax.tick_params(axis='both', labelsize=tick_font)
    ax.grid(which='major', axis='x', linestyle='--', color='gray')
    ax.grid(which='minor', axis='x', linestyle=':', color='lightgray')
    ax.legend(loc='upper right', fontsize=leg_font)
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    main()
