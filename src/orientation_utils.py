import math
from shapely.geometry import LineString

def calculate_shadow(tree_height: float, solar_alt: float, solar_az: float):
    if solar_alt <= 0:
        return 0.0, 0.0
    alt_rad = math.radians(solar_alt)
    return tree_height / math.tan(alt_rad), (solar_az + 180) % 360

def calc_buffer_percentage(shadow_length: float, shadow_direction: float,
                           buffer_width: float, line_orientation: float):
    # project shadow onto the buffer perpendicular to the line
    perp = (line_orientation + 90) % 360
    delta = math.radians(shadow_direction - perp)
    comp = abs(math.cos(delta)) * shadow_length
    return (min(comp, buffer_width) / buffer_width) * 100

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

def format_windows(wins):
    return ";".join(f"{s.strftime('%H:%M')}-{e.strftime('%H:%M')}" for s,e in wins)

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