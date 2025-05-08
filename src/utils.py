# src/shadow_calculator.py
import matplotlib.dates as mdates
import math
import pandas as pd
import numpy as np
from shapely.geometry import LineString, mapping

def calculate_shadow(tree_height: float, solar_altitude: float, solar_azimuth: float):
    """Return absolute shadow length and direction."""
    if solar_altitude <= 0:
        return 0.0, 0.0
    alt_rad = math.radians(solar_altitude)
    length = tree_height / math.tan(alt_rad)
    direction = (solar_azimuth + 180) % 360
    return length, direction

def format_windows(wins):
    return ";".join(f"{s.strftime('%H:%M')}-{e.strftime('%H:%M')}" for s,e in wins)

def calc_buffer_pct(shadow_len: float,
                    shadow_dir: float,
                    buf_w: float,
                    line_ori: float):
    """Project the shadow onto the buffer that’s perpendicular to the flight line."""
    perp = (line_ori + 90) % 360
    delta = math.radians(shadow_dir - perp)
    comp = abs(math.cos(delta)) * shadow_len
    return (min(comp, buf_w) / buf_w) * 100

def calc_buffer_percentage(shadow_length: float, shadow_direction: float, buffer_width: float, axis: str):
    """Compute penetration of shadow into a perpendicular buffer."""
    if shadow_length <= 0:
        return 0.0
    dir_rad = math.radians(shadow_direction)
    comp = (abs(math.sin(dir_rad)) if axis == 'NS' else abs(math.cos(dir_rad))) * shadow_length
    penetration = min(comp, buffer_width)
    return round((penetration / buffer_width) * 100, 1)

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

def compute_total_duration(wins):
    total = sum((e - s).total_seconds() for s,e in wins)
    return round(total/3600, 2)

def split_line(geom: LineString, seg_len: float):
    total = geom.length
    if total <= seg_len:
        return [geom]
    segs = []
    dists = np.arange(0, total, seg_len).tolist() + [total]
    for d0, d1 in zip(dists[:-1], dists[1:]):
        segs.append(LineString([geom.interpolate(d0), geom.interpolate(d1)]))
    return segs

def categorize_window(win_str):
    """Bucket window string into pilot-friendly categories."""
    if not win_str:
        return "no fly window"
    intervals = win_str.split(';')
    # compute total flight hours
    total_sec = sum(
        (pd.to_datetime(iv.split('-')[1]) - pd.to_datetime(iv.split('-')[0])).seconds
        for iv in intervals
    )
    total_hr = total_sec / 3600
    # determine period segments
    periods = set()
    for iv in intervals:
        start_hour = int(iv.split('-')[0][:2])
        if start_hour < 10:
            periods.add('morning')
        elif start_hour < 15:
            periods.add('noon')
        else:
            periods.add('evening')
    # categorize
    if total_hr >= 8:
        return "fly any time"
    if total_hr >= 4:
        if periods == {'morning', 'evening'}:
            return "fly long morning+evening"
        if 'noon' in periods:
            return "fly long noon"
    if total_hr < 2.5:
        return "fly extra short"
    if periods <= {'morning', 'evening'}:
        return "fly short morning+evening"
    return "fly short noon"