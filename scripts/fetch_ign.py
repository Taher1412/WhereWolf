"""Building footprints with real heights from IGN BD TOPO (open data, Etalab 2.0).

OSM only has heights for a few % of buildings here; IGN has a measured height
(`hauteur`) and ground altitude for almost all of them.

Run once (needs internet):   python scripts/fetch_ign.py
Writes:                      data/twin/buildings.geojson  (replaces the OSM one)
Properties per building:     h (m), hsrc ("ign" | "default"), z (ground altitude m), use
Attribution:                 "Bâtiments © IGN BD TOPO"
"""
import json
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_osm import BBOX  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "data" / "twin" / "buildings.geojson"
URL = "https://data.geopf.fr/wfs/ows"
PAGE = 5000


def main():
    s, w, n, e = BBOX
    feats, start = [], 0
    with httpx.Client(timeout=180, headers={"User-Agent": "near-hackathon/0.1"}) as cl:
        while True:
            page, r = None, None
            for attempt in range(4):   # the service sometimes answers with an empty body
                try:
                    r = cl.get(URL, params={
                        "SERVICE": "WFS", "VERSION": "2.0.0", "REQUEST": "GetFeature",
                        "TYPENAMES": "BDTOPO_V3:batiment", "OUTPUTFORMAT": "application/json",
                        "BBOX": f"{s},{w},{n},{e},urn:ogc:def:crs:EPSG::4326",
                        "COUNT": PAGE, "STARTINDEX": start, "SORTBY": "cleabs"})
                    r.raise_for_status()
                    page = r.json()["features"]
                    break
                except Exception as ex:
                    print(f"  retry {attempt + 1} ({type(ex).__name__}: {(r.text[:120] if r is not None else '')!r})")
                    time.sleep(3 * (attempt + 1))
            if page is None:
                sys.exit("IGN service failed; the OSM buildings file is kept.")
            print(f"  got {len(page)} (from {start})")
            for f in page:
                p, g = f["properties"], f["geometry"]
                if not g:
                    continue
                h = p.get("hauteur")
                src = "ign"
                if not h or h <= 0:
                    h, src = 9.0, "default"
                polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
                for poly in polys:
                    # IGN gives lon, lat (and sometimes z); keep the outer ring, 6 decimals.
                    ring = [[round(c[0], 6), round(c[1], 6)] for c in poly[0]]
                    feats.append({"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [ring]},
                                  "properties": {"h": round(float(h), 1), "hsrc": src,
                                                 "z": p.get("altitude_minimale_sol"),
                                                 "use": p.get("usage_1")}})
            if len(page) < PAGE:
                break
            start += PAGE
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"type": "FeatureCollection", "features": feats},
                              separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    n_ign = sum(1 for f in feats if f["properties"]["hsrc"] == "ign")
    print(f"Wrote {len(feats)} footprints, {n_ign} with IGN height ({100 * n_ign / max(len(feats), 1):.0f} %)")


if __name__ == "__main__":
    main()
