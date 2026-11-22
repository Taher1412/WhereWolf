"""Render offline map tiles from the data we already have (no internet at run time).

Sources (all local): data/twin/buildings.geojson (IGN), data/twin/forest.geojson (OSM woods,
water, open ground, paths), data/twin/lines.geojson (OSM roads, railways).
Output: data/tiles/{z}/{x}/{y}.png for zooms 13-17 (Leaflet scales z17 up for 18-19).
Each zoom is drawn as one big picture, then cut into 256 px tiles.

    python -m scripts.render_tiles
"""
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
TWIN = ROOT / "data" / "twin"
OUT = ROOT / "data" / "tiles"
S, W, N, E = 48.830, 2.405, 48.865, 2.465      # config.BBOX
ZOOMS = range(13, 18)

BG = (16, 22, 24)
WOOD = (20, 38, 27)
OPEN = (23, 33, 26)
WATER = (18, 46, 72)
BUILD = (44, 51, 56)
BUILD_EDGE = (58, 67, 72)
ROAD = {2: (150, 128, 82), 3: (128, 112, 76), 4: (104, 98, 80)}   # primary, secondary, tertiary
MINOR = (66, 74, 78)
PATH = (58, 76, 62)
RAIL = (96, 96, 104)
FENCE = (40, 48, 44)


def px(lat, lon, z):
    n = 256 * 2 ** z
    x = (lon + 180) / 360 * n
    lr = math.radians(lat)
    y = (1 - math.log(math.tan(lr) + 1 / math.cos(lr)) / math.pi) / 2 * n
    return x, y


def rings(geom):
    if geom["type"] == "Polygon":
        return [geom["coordinates"]]
    if geom["type"] == "MultiPolygon":
        return geom["coordinates"]
    return []


def load(name):
    p = TWIN / name
    return json.load(open(p, encoding="utf-8"))["features"] if p.exists() else []


def main():
    buildings = load("buildings.geojson")
    forest = load("forest.geojson")
    lines = load("lines.geojson")
    print(f"{len(buildings)} buildings, {len(forest)} forest features, {len(lines)} lines")
    for z in ZOOMS:
        x0, y0 = px(N, W, z)
        x1, y1 = px(S, E, z)
        tx0, ty0, tx1, ty1 = int(x0 // 256), int(y0 // 256), int(x1 // 256), int(y1 // 256)
        ox, oy = tx0 * 256, ty0 * 256
        img = Image.new("RGB", ((tx1 - tx0 + 1) * 256, (ty1 - ty0 + 1) * 256), BG)
        d = ImageDraw.Draw(img)
        f = 2 ** (z - 15)                        # line widths scale with zoom

        def P(coords):
            return [(px(la, lo, z)[0] - ox, px(la, lo, z)[1] - oy) for lo, la in coords]

        def poly(feat, fill, outline=None):
            for r in rings(feat["geometry"]):
                if len(r[0]) >= 3:
                    d.polygon(P(r[0]), fill=fill, outline=outline)
                for hole in r[1:]:
                    if len(hole) >= 3:
                        d.polygon(P(hole), fill=BG)

        def line(coords, color, w):
            if len(coords) >= 2:
                d.line(P(coords), fill=color, width=max(1, int(round(w))), joint="curve")

        for ft in forest:
            k = ft["properties"].get("kind")
            if k == "open":
                poly(ft, OPEN)
        for ft in forest:
            if ft["properties"].get("kind") == "wood":
                poly(ft, WOOD)
        for ft in forest:
            if ft["properties"].get("kind") == "water":
                poly(ft, WATER)
        for ft in forest:
            if ft["properties"].get("kind") == "stream" and ft["geometry"]["type"] == "LineString":
                line(ft["geometry"]["coordinates"], WATER, 2 * f)
        if z >= 15:
            for ft in forest:
                if ft["properties"].get("kind") == "fence" and ft["geometry"]["type"] == "LineString":
                    line(ft["geometry"]["coordinates"], FENCE, 0.6 * f)
        for ft in buildings:
            poly(ft, BUILD, BUILD_EDGE if z >= 16 else None)
        for ft in forest:      # small ways: residential streets, footways, paths
            p = ft["properties"]
            if p.get("kind") != "path" or ft["geometry"]["type"] != "LineString":
                continue
            street = p.get("hw") in ("residential", "living_street", "unclassified", "service", "pedestrian")
            if not street and z < 14:
                continue
            line(ft["geometry"]["coordinates"], MINOR if street else PATH, (2.2 if street else 1.0) * f)
        for ft in lines:
            p = ft["properties"]
            if ft["geometry"]["type"] != "LineString" or p.get("tunnel"):
                continue
            if p.get("kind") == "railway":
                line(ft["geometry"]["coordinates"], RAIL, 1.4 * f)
            elif p.get("kind") == "road":
                cls = p.get("cls", 4)
                line(ft["geometry"]["coordinates"], ROAD.get(cls, ROAD[2]), {1: 5, 2: 4.2, 3: 3.6, 4: 3.0}[cls] * f)

        n = 0
        for tx in range(tx0, tx1 + 1):
            folder = OUT / str(z) / str(tx)
            folder.mkdir(parents=True, exist_ok=True)
            for ty in range(ty0, ty1 + 1):
                a, b = (tx - tx0) * 256, (ty - ty0) * 256
                img.crop((a, b, a + 256, b + 256)).save(folder / f"{ty}.png", optimize=True)
                n += 1
        print(f"z{z}: {n} tiles")


if __name__ == "__main__":
    main()
