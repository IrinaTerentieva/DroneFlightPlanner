import math
import pandas as pd
import numpy as np
from shapely.geometry import LineString, mapping

def compute_orientation(geom: LineString) -> int:
    x0, y0 = geom.coords[0]
    x1, y1 = geom.coords[-1]
    ang = (math.degrees(math.atan2(x1 - x0, y1 - y0)) + 360) % 360
    return int(round(ang))

def orientation_category(angle: int) -> str:
    dirs = ['N','NNE','NE','ENE','E','ESE','SE','SSE',
            'S','SSW','SW','WSW','W','WNW','NW','NNW']
    return dirs[round(angle / 22.5) % 16]

def calculate_shadow(tree_h, solar_alt, solar_az):
    if solar_alt <= 0:
        return 0.0, 0.0
    alt_rad = math.radians(solar_alt)
    return tree_h / math.tan(alt_rad), (solar_az + 180) % 360

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