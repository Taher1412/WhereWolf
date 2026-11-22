"""Download landmarks around the venue from OpenStreetMap (Overpass API).

Run once (needs internet):   python scripts/fetch_osm.py
Writes:                      data/landmarks.geojson

Every feature becomes one or more GeoJSON points with {id, type, name}.
- Point-like things (church, tower...) -> one point (the centroid).
- Areas we need the edge of (park, wood) -> points sampled along the edge.
- Lines (railway, river, main road) -> points sampled every ~50 m.
"""
import json
import math
import sys
from pathlib import Path

import httpx

# Search box: south, west, north, east  (same as backend/config.py)
BBOX = (48.830, 2.405, 48.865, 2.465)
OUT = Path(__file__).resolve().parent.parent / "data" / "landmarks.geojson"
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

QUERY = """
[out:json][timeout:120];
(
  nwr["amenity"="place_of_worship"]({b});
  nwr["building"~"^(church|chapel|cathedral)$"]({b});
  nwr["historic"~"^(castle|fort|monument|memorial)$"]({b});
  nwr["man_made"~"^(water_tower|tower|mast)$"]({b});
  way["bridge"="yes"]["highway"~"^(primary|secondary|tertiary|residential|trunk)$"]({b});
  way["bridge"="yes"]["railway"]({b});
  nwr["railway"="station"]({b});
  nwr["amenity"~"^(school|townhall|hospital)$"]({b});
  nwr["leisure"~"^(park|stadium)$"]({b});
  nwr["landuse"~"^(forest|cemetery)$"]({b});
  nwr["natural"="wood"]({b});
  nwr["natural"="water"]["name"]({b});
  way["railway"="rail"]({b});
  way["waterway"~"^(river|canal)$"]({b});
  way["highway"~"^(primary|trunk)$"]({b});
);
out geom;
"""

# Line/edge types are sampled into many points; the rest become one point.
LINE_TYPES = {"railway", "river", "main_road"}
EDGE_TYPES = {"park", "wood", "cemetery", "lake"}
SAMPLE_M = 50


def classify(tags):
    """Return our landmark type for a set of OSM tags (or None)."""
    name = (tags.get("name") or "").lower()
    if tags.get("historic") in ("castle", "fort"):
        return "keep" if ("donjon" in name or "keep" in name) else "castle"
    if tags.get("man_made") == "water_tower":
        return "water_tower"
    if "donjon" in name:
        return "keep"
    if tags.get("man_made") == "tower" and tags.get("tower:type") in ("defensive", "keep"):
        return "castle_tower"          # the corner towers of the château
    if tags.get("amenity") == "place_of_worship" or tags.get("building") in ("church", "chapel", "cathedral"):
        # Only things that look like a church count as "church".
        churchy = any(w in name for w in ("église", "eglise", "chapelle", "church", "basilique",
                                          "notre-dame", "saint", "sainte", "temple"))
        if tags.get("building") in ("church", "chapel", "cathedral") or (
                tags.get("religion") == "christian" and churchy):
            return "church"
        if tags.get("religion") == "muslim":
            return "mosque"
        return None
    if tags.get("man_made") in ("tower", "mast"):
        # Skip floodlights and small towers nobody would call out.
        if tags.get("tower:type") in ("lighting", "cooling", "minaret"):
            return None
        return "tower"
    if tags.get("bridge") == "yes":
        return "bridge"
    if tags.get("railway") == "station":
        return "station"
    if tags.get("amenity") in ("school", "townhall", "hospital"):
        return tags["amenity"]
    if tags.get("historic") in ("monument", "memorial"):
        return "monument"
    if tags.get("leisure") == "stadium":
        return "stadium"
    if tags.get("leisure") == "park":
        return "park"
    if tags.get("landuse") == "forest" or tags.get("natural") == "wood":
        return "wood"
    if tags.get("landuse") == "cemetery":
        return "cemetery"
    if tags.get("natural") == "water":
        return "lake"
    if tags.get("railway") == "rail":
        return "railway"
    if tags.get("waterway") in ("river", "canal"):
        return "river"
    if tags.get("highway") in ("primary", "trunk"):
        return "main_road"
    return None


def dist_m(a, b):
    """Rough distance in metres between two (lat, lon) points."""
    dy = (b[0] - a[0]) * 110540
    dx = (b[1] - a[1]) * 111320 * math.cos(math.radians(a[0]))
    return math.hypot(dx, dy)


def sample_line(coords, step=SAMPLE_M):
    """Points every `step` metres along a polyline of (lat, lon)."""
    if not coords:
        return []
    out = [coords[0]]
    carry = 0.0
    for a, b in zip(coords, coords[1:]):
        seg = dist_m(a, b)
        pos = step - carry
        while pos < seg:
            t = pos / seg
            out.append((a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])))
            pos += step
        carry = (carry + seg) % step
    return out


def element_lines(el):
    """All coordinate lists of an element (a node gives a 1-point list)."""
    if el["type"] == "node":
        return [[(el["lat"], el["lon"])]]
    if el["type"] == "way":
        return [[(p["lat"], p["lon"]) for p in el.get("geometry", [])]]
    lines = []
    for m in el.get("members", []):
        if m.get("geometry") and m.get("role") in ("outer", "", None):
            lines.append([(p["lat"], p["lon"]) for p in m["geometry"]])
    return lines


def inside(p):
    return BBOX[0] <= p[0] <= BBOX[2] and BBOX[1] <= p[1] <= BBOX[3]


def main():
    bbox_str = ",".join(str(v) for v in BBOX)
    query = QUERY.replace("{b}", bbox_str)
    data = None
    for url in OVERPASS_URLS:
        try:
            print(f"Querying {url} ...")
            r = httpx.post(url, data={"data": query}, timeout=180,
                           headers={"User-Agent": "near-hackathon/0.1"})
            r.raise_for_status()
            data = r.json()
            break
        except Exception as e:  # try the next mirror
            print("  failed:", e)
    if data is None:
        sys.exit("All Overpass mirrors failed.")

    features, seen = [], set()
    counts = {}
    for el in data["elements"]:
        tags = el.get("tags", {})
        ltype = classify(tags)
        if ltype is None:
            continue
        name = tags.get("name")
        base_id = f"{el['type'][0]}{el['id']}"
        lines = [ln for ln in element_lines(el) if ln]
        if not lines:
            continue

        if ltype in LINE_TYPES or ltype in EDGE_TYPES:
            pts = [p for ln in lines for p in sample_line(ln)]
        else:
            allp = [p for ln in lines for p in ln]
            pts = [(sum(p[0] for p in allp) / len(allp), sum(p[1] for p in allp) / len(allp))]

        for i, p in enumerate(pts):
            if not inside(p):
                continue
            fid = base_id if len(pts) == 1 else f"{base_id}_{i}"
            key = (ltype, round(p[0], 5), round(p[1], 5))
            if key in seen:
                continue
            seen.add(key)
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [round(p[1], 6), round(p[0], 6)]},
                "properties": {"id": fid, "type": ltype, "name": name},
            })
            counts[ltype] = counts.get(ltype, 0) + 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(features)} points to {OUT}")
    for k, v in sorted(counts.items()):
        print(f"  {k:12s} {v}")


if __name__ == "__main__":
    main()
