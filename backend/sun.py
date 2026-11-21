"""Sun azimuth/elevation from time and place (NOAA formula, no extra library)."""
import math
from datetime import datetime, timezone


def sun_position(lat, lon, when=None):
    """Return (azimuth_deg_from_north, elevation_deg) for a UTC datetime."""
    when = when or datetime.now(timezone.utc)
    when = when.astimezone(timezone.utc)
    doy = when.timetuple().tm_yday
    hour = when.hour + when.minute / 60 + when.second / 3600

    g = 2 * math.pi / 365 * (doy - 1 + (hour - 12) / 24)       # fractional year
    eqtime = 229.18 * (0.000075 + 0.001868 * math.cos(g) - 0.032077 * math.sin(g)
                       - 0.014615 * math.cos(2 * g) - 0.040849 * math.sin(2 * g))
    decl = (0.006918 - 0.399912 * math.cos(g) + 0.070257 * math.sin(g)
            - 0.006758 * math.cos(2 * g) + 0.000907 * math.sin(2 * g)
            - 0.002697 * math.cos(3 * g) + 0.00148 * math.sin(3 * g))

    tst = hour * 60 + eqtime + 4 * lon                          # true solar time, minutes
    ha = math.radians(tst / 4 - 180)                            # hour angle
    la = math.radians(lat)

    cos_zen = math.sin(la) * math.sin(decl) + math.cos(la) * math.cos(decl) * math.cos(ha)
    zen = math.acos(max(-1.0, min(1.0, cos_zen)))
    elev = 90 - math.degrees(zen)

    az = math.degrees(math.atan2(math.sin(ha),
                                 math.cos(ha) * math.sin(la) - math.tan(decl) * math.cos(la)))
    az = (az + 180) % 360                                       # from north, clockwise
    return az, elev
