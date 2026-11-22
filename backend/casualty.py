"""MIST card, evacuation priority and tourniquet timers.

Decision support only: this organises what the medic said. Thresholds are
placeholders in config.py, to validate with a mentor.
"""
from datetime import datetime, timedelta

PRIORITY_RANK = {"urgent": 1, "priority": 2, "routine": 3}


def tourniquet_epoch_ms(hhmm):
    """'14:32' -> epoch milliseconds today (or yesterday if that would be in the future)."""
    if not hhmm:
        return None
    try:
        h, m = (int(x) for x in hhmm.split(":"))
    except ValueError:
        return None
    now = datetime.now()
    t = now.replace(hour=h, minute=m, second=0, microsecond=0)
    if t > now + timedelta(minutes=30):
        t -= timedelta(days=1)
    return int(t.timestamp() * 1000)


def priority(c):
    """Rule-based priority for one casualty entry."""
    s = c.get("signs") or {}
    has_tq = any(t.get("type") == "tourniquet" for t in c.get("treatments") or [])
    if s.get("massive_bleeding") or has_tq or s.get("conscious") is False or s.get("breathing") is False:
        return "urgent"
    if c.get("priority_hint") in PRIORITY_RANK:
        return c["priority_hint"]
    return "priority" if c.get("mechanism") in ("blast", "gunshot") else "routine"


def mist(c):
    """MIST card as four short lines."""
    s = c.get("signs") or {}
    signs = []
    if "conscious" in s:
        signs.append("conscious" if s["conscious"] else "UNCONSCIOUS")
    if "breathing" in s:
        signs.append("breathing" if s["breathing"] else "BREATHING PROBLEM")
    if s.get("massive_bleeding"):
        signs.append("MASSIVE BLEEDING")
    treat = []
    for t in c.get("treatments") or []:
        part = t.get("type", "")
        if t.get("location"):
            part += f" ({t['location']})"
        if t.get("time"):
            part += f" @ {t['time']}"
        treat.append(part)
    return {
        "M": c.get("mechanism") or "unknown",
        "I": "; ".join(c.get("injuries") or []) or "not reported",
        "S": ", ".join(signs) or "not reported",
        "T": "; ".join(treat) or "none reported",
    }


def merge(old, new):
    """Update a casualty with a follow-up report (new values win, lists grow)."""
    if not old:
        return new
    out = dict(old)
    for k in ("mechanism", "priority_hint"):
        if new.get(k):
            out[k] = new[k]
    if new.get("count") and new["count"] != 1:
        out["count"] = new["count"]
    out["injuries"] = list(dict.fromkeys((old.get("injuries") or []) + (new.get("injuries") or [])))
    # A new value wins, but "not said" (None) never erases what was said before.
    out["signs"] = {**(old.get("signs") or {}), **{k: v for k, v in (new.get("signs") or {}).items() if v is not None}}
    treats = list(old.get("treatments") or [])
    for t in new.get("treatments") or []:
        if t not in treats:
            treats.append(t)
    out["treatments"] = treats
    out["self_report"] = bool(old.get("self_report") or new.get("self_report"))
    if new.get("injury_ago_min") is not None:
        out["injury_ago_min"] = new["injury_ago_min"]
        out["injury_ago_ms"] = new.get("injury_ago_ms")
    return out


def summary(casualties):
    """Fields used by the map, the list and the read-back."""
    if not casualties:
        return {"count": 0, "priority": None, "rank": 9, "tq_time": None, "tq_ms": None}
    pris = [priority(c) for c in casualties]
    best = min(pris, key=lambda p: PRIORITY_RANK[p])
    tq = [t.get("time") for c in casualties for t in c.get("treatments") or []
          if t.get("type") == "tourniquet" and t.get("time")]
    tq_ms = [tourniquet_epoch_ms(t) for t in tq]
    tq_ms = [x for x in tq_ms if x]
    first = min(tq_ms) if tq_ms else None
    return {
        "count": sum(int(c.get("count") or 1) for c in casualties),
        "priority": best, "rank": PRIORITY_RANK[best],
        "tq_time": tq[tq_ms.index(first)] if first else None, "tq_ms": first,
    }
