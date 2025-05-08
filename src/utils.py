# src/shadow_calculator.py
import math
import pandas as pd
import matplotlib.dates as mdates

def calculate_shadow(tree_height: float, solar_altitude: float, solar_azimuth: float):
    """Return absolute shadow length and direction."""
    if solar_altitude <= 0:
        return 0.0, 0.0
    alt_rad = math.radians(solar_altitude)
    length = tree_height / math.tan(alt_rad)
    print(f"Tree height is {tree_height} and length of shadow is {length}")
    direction = (solar_azimuth + 180) % 360
    return length, direction


def calc_buffer_percentage(shadow_length: float, shadow_direction: float, buffer_width: float, axis: str):
    """Compute penetration of shadow into a perpendicular buffer."""
    if shadow_length <= 0:
        return 0.0
    dir_rad = math.radians(shadow_direction)
    comp = (abs(math.sin(dir_rad)) if axis == 'NS' else abs(math.cos(dir_rad))) * shadow_length
    penetration = min(comp, buffer_width)
    return round((penetration / buffer_width) * 100, 1)


def find_flight_windows(df: pd.DataFrame, column: str, threshold: float):
    """Identify contiguous periods where df[column] <= threshold and sun is up."""
    mask = (df[column] <= threshold) & (df['Elevation'] > 0)
    periods = []
    start = None
    prev_t = None
    for t, ok in zip(df.index, mask):
        if ok and start is None:
            start = t
        if start is not None and ((not ok) or t == df.index[-1]):
            end = prev_t if not ok else t
            periods.append((start, end))
            start = None
        prev_t = t
    return periods


def shade_contiguous(ax, times, mask, color, alpha):
    """Shade contiguous spans where mask is True."""
    start = None
    prev_t = None
    for t, flag in zip(times, mask):
        if flag and start is None:
            start = t
        if start is not None and ((not flag) or t == times[-1]):
            end = prev_t if not flag else t
            ax.axvspan(start, end, color=color, alpha=alpha)
            start = None
        prev_t = t


def format_time(x, pos=None):
    dt = mdates.num2date(x)
    return dt.strftime('%-I%p').lower()
