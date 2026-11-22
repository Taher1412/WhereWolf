"""Download what the 3D view and the acoustic matching need (Overpass API).

Run once (needs internet):   python scripts/fetch_twin.py
Writes:
  data/twin/buildings_osm.geojson  OSM footprints + height (fallback; fetch_ign.py writes
                                   buildings.geojson with real IGN heights)
  data/twin/lines.geojson       railways, roads (with class), rivers  -> 3D lines
  data/twin/sources.geojson     points sampled every 25 m along things that make noise:
                                surface railways, roads by class, industrial areas

Height: OSM `height` if present, else `building:levels` x 3 m, else a default
of 9 m flagged as "default" (the 3D view shows those lighter, so nobody
mistakes a guess for a measurement).
"""
import json
import math
import re
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_osm import BBOX, OVERPASS_URLS, inside, sample_line  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "data" / "twin"

QUERY = """
[out:json][timeout:180];
(
  way["building"]({b});
  relation["building"]["type"="multipolygon"]({b});
  way["railway"~"^(rail|light_rail|tram|subway)$"]({b});
  way["highway"~"^(motorway|trunk|primary|secondary|tertiary)(_link)?$"]({b});
  way["waterway"~"^(river|canal)$"]({b});
  nwr["landuse"~"^(industrial|construction)$"]({b});
);
out geom;
"""

ROAD_CLASS = {"motorway": 1, "trunk": 1, "primary": 2, "secondary": 3, "tertiary": 4}


def num(s):
    m = re.match(r"\s*([\d.]+)", str(s or ""))
    return float(m.group(1)) if m else None


def height_of(tags):
    h = num(tags.get("height"))
    if h and 2 <= h <= 300:
        return round(h, 1), "osm_height"
    lv = num(tags.get("building:levels"))
    if lv and 0 < lv < 80:
        return round(lv * 3.0 + 1.0, 1), "levels"
    if tags.get("building") in ("church", "cathedral"):
        return 18.0, "default"
    return 9.0, "default"


def rings(el):
    """Outer rings of a way/relation as [(lat, lon), ...]."""
    if el["type"] == "way":
        g = el.get("geometry") or []
        return [[(p["lat"], p["lon"]) for p in g]] if len(g) >= 4 else []
    out = []
    for m in el.get("members", []):
        if m.get("role") == "outer" and m.get("geometry") and len(m["geometry"]) >= 4:
            out.append([(p["lat"], p["lon"]) for p in m["geometry"]])
    return out


def poly(ring):
    return [[round(lon, 6), round(lat, 6)] for lat, lon in ring]


def main():
    query = QUERY.replace("{b}", ",".join(str(v) for v in BBOX))
    data = None
    for url in OVERPASS_URLS:
        try:
            print(f"Querying {url} ...")
            r = httpx.post(url, data={"data": query}, timeout=300,
                           headers={"User-Agent": "near-hackathon/0.1"})
            r.raise_for_status()
            data = r.json()
            break
        except Exception as e:
            print("  failed:", e)
    if data is None:
        sys.exit("All Overpass mirrors failed.")

    buildings, lines, sources = [], [], []
    for el in data["elements"]:
        t = el.get("tags", {})
        if "building" in t and el["type"] in ("way", "relation"):
            h, src = height_of(t)
            for ring in rings(el):
                if not any(inside(p) for p in ring):
                    continue
                buildings.append({"type": "Feature",
                                  "geometry": {"type": "Polygon", "coordinates": [poly(ring)]},
                                  "properties": {"h": h, "hsrc": src, "name": t.get("name")}})
            continue

        if "railway" in t and el["type"] == "way":
            g = [(p["lat"], p["lon"]) for p in el.get("geometry", [])]
            under = t.get("tunnel") in ("yes", "building_passage") or t.get("railway") == "subway" \
                or (num(t.get("layer")) or 0) < 0 and t.get("layer", "").startswith("-")
            lines.append({"type": "Feature", "geometry": {"type": "LineString", "coordinates": poly(g)},
                          "properties": {"kind": "railway", "sub": t["railway"], "tunnel": bool(under)}})
            if not under and t["railway"] in ("rail", "light_rail", "tram"):
                kind = "tram" if t["railway"] == "tram" else "railway"
                sources += [(kind, p, 0) for p in sample_line(g, 25)]
            continue

        if "highway" in t and el["type"] == "way":
            g = [(p["lat"], p["lon"]) for p in el.get("geometry", [])]
            cls = ROAD_CLASS.get(t["highway"].replace("_link", ""), 4)
            under = t.get("tunnel") == "yes"
            lines.append({"type": "Feature", "geometry": {"type": "LineString", "coordinates": poly(g)},
                          "properties": {"kind": "road", "cls": cls, "tunnel": under}})
            if not under:
                sources += [("road", p, cls) for p in sample_line(g, 25)]
            continue

        if "waterway" in t and el["type"] == "way":
            g = [(p["lat"], p["lon"]) for p in el.get("geometry", [])]
            lines.append({"type": "Feature", "geometry": {"type": "LineString", "coordinates": poly(g)},
                          "properties": {"kind": "river"}})
            continue

        if t.get("landuse") in ("industrial", "construction"):
            for ring in rings(el):
                sources += [("industrial", p, 0) for p in sample_line(ring, 25)]
                # also the centre, so big areas count inside, not only at the edge
                sources.append(("industrial", (sum(p[0] for p in ring) / len(ring),
                                               sum(p[1] for p in ring) / len(ring)), 0))

    OUT.mkdir(parents=True, exist_ok=True)
    fc = lambda fs: {"type": "FeatureCollection", "features": fs}  # noqa: E731
    (OUT / "buildings_osm.geojson").write_text(json.dumps(fc(buildings), separators=(",", ":"),
                                                      ensure_ascii=False), encoding="utf-8")
    (OUT / "lines.geojson").write_text(json.dumps(fc(lines), separators=(",", ":")), encoding="utf-8")
    pts = [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [round(p[1], 6), round(p[0], 6)]},
            "properties": {"kind": k, "cls": c}} for k, p, c in sources if inside(p)]
    (OUT / "sources.geojson").write_text(json.dumps(fc(pts), separators=(",", ":")), encoding="utf-8")

    hs = [b["properties"]["hsrc"] for b in buildings]
    print(f"{len(buildings)} buildings ({hs.count('osm_height')} with OSM height, "
          f"{hs.count('levels')} from levels, {hs.count('default')} default 9 m)")
    print(f"{len(lines)} lines, {len(pts)} noise-source points:",
          {k: sum(1 for s in pts if s['properties']['kind'] == k) for k in
           ("railway", "tram", "road", "industrial")})


if __name__ == "__main__":
    main()
