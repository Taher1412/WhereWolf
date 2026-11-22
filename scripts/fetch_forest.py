"""Download what we need to locate someone inside a wood (Overpass API).

Run once (needs internet):   python scripts/fetch_forest.py
Writes data/twin/forest.geojson with:
  polygons  kind = wood | water | open (grass, meadow, pitch, playground)
            wood keeps leaf_type (broadleaved / needleleaved / mixed) when tagged
  lines     kind = path, with hw (OSM highway value), surface, paved (bool)
            kind = stream (small waterways), fence
  points    kind = guidepost | bench | shelter | info

Everything is optional for the app: if the file is missing, forest cues are off.
"""
import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_osm import BBOX, OVERPASS_URLS  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "data" / "twin" / "forest.geojson"

QUERY = """
[out:json][timeout:180];
(
  nwr["landuse"="forest"]({b});
  nwr["natural"~"^(wood|scrub|water)$"]({b});
  nwr["landuse"~"^(grass|meadow|recreation_ground)$"]({b});
  nwr["leisure"~"^(pitch|playground|park|garden)$"]({b});
  way["highway"~"^(path|track|footway|bridleway|cycleway|pedestrian|service|unclassified|residential|living_street)$"]({b});
  way["waterway"~"^(stream|ditch|drain|canal)$"]({b});
  way["barrier"~"^(fence|wall)$"]({b});
  node["tourism"="information"]({b});
  node["amenity"~"^(bench|shelter)$"]({b});
);
out geom;
"""

PAVED = {"asphalt", "paved", "concrete", "paving_stones", "sett", "concrete:plates"}


def coords(el):
    g = el.get("geometry") or []
    return [[round(p["lon"], 6), round(p["lat"], 6)] for p in g]


def outer_rings(el):
    if el["type"] == "way":
        c = coords(el)
        return [c] if len(c) >= 4 else []
    out = []
    for m in el.get("members", []):
        if m.get("role") == "outer" and m.get("geometry") and len(m["geometry"]) >= 4:
            out.append([[round(p["lon"], 6), round(p["lat"], 6)] for p in m["geometry"]])
    return out


def poly_kind(t):
    if t.get("landuse") == "forest" or t.get("natural") in ("wood", "scrub"):
        return "wood"
    if t.get("natural") == "water":
        return "water"
    if t.get("landuse") in ("grass", "meadow", "recreation_ground") or \
            t.get("leisure") in ("pitch", "playground"):
        return "open"
    return None


def main():
    query = QUERY.replace("{b}", ",".join(str(v) for v in BBOX))
    data = None
    for url in OVERPASS_URLS:
        try:
            print(f"Querying {url} ...")
            r = httpx.post(url, data={"data": query}, timeout=300,
                           headers={"User-Agent": "pothenot-hackathon/0.1"})
            r.raise_for_status()
            data = r.json()
            break
        except Exception as e:
            print("  failed:", e)
    if data is None:
        sys.exit("All Overpass mirrors failed.")

    feats = []
    for el in data["elements"]:
        t = el.get("tags", {})
        if el["type"] == "node":
            if t.get("tourism") == "information":
                kind = "guidepost" if t.get("information") in ("guidepost", "route_marker") else "info"
            else:
                kind = t.get("amenity")
            feats.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [el["lon"], el["lat"]]},
                          "properties": {"kind": kind, "name": t.get("name")}})
            continue
        pk = poly_kind(t)
        if pk and el["type"] in ("way", "relation") and "highway" not in t:
            for ring in outer_rings(el):
                if ring[0] != ring[-1]:
                    continue
                feats.append({"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [ring]},
                              "properties": {"kind": pk, "leaf": t.get("leaf_type"), "name": t.get("name")}})
            continue
        if el["type"] != "way":
            continue
        c = coords(el)
        if len(c) < 2:
            continue
        if "highway" in t:
            surf = t.get("surface")
            hw = t["highway"]
            # Untagged surface: city footways and park roads are paved, paths/tracks are not.
            paved = surf in PAVED if surf else hw not in ("path", "track", "bridleway")
            feats.append({"type": "Feature", "geometry": {"type": "LineString", "coordinates": c},
                          "properties": {"kind": "path", "hw": hw, "surface": surf, "paved": paved,
                                         "name": t.get("name"),
                                         "cars": t.get("motor_vehicle") not in ("no", "private")
                                         and hw in ("service", "unclassified", "residential")}})
        elif "waterway" in t:
            feats.append({"type": "Feature", "geometry": {"type": "LineString", "coordinates": c},
                          "properties": {"kind": "stream", "name": t.get("name")}})
        elif "barrier" in t:
            feats.append({"type": "Feature", "geometry": {"type": "LineString", "coordinates": c},
                          "properties": {"kind": "fence"}})

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"type": "FeatureCollection", "features": feats}, separators=(",", ":"),
                              ensure_ascii=False), encoding="utf-8")
    from collections import Counter
    print(len(feats), "features:", dict(Counter(f["properties"]["kind"] for f in feats)))


if __name__ == "__main__":
    main()
