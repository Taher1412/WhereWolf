"""IGN LiDAR HD elevation for the 3D line of sight (open data, Licence Ouverte 2.0).

Run once (needs internet):   python scripts/fetch_lidar.py
Writes data/twin/lidar.npz with, on a 2 m grid over config.BBOX (row 0 = south):
  mnt   ground altitude (m)                       LiDAR HD MNT
  mnh   height of what stands on the ground (m)   LiDAR HD MNH = surface - ground
        (buildings, trees, street trees, spires down to the pixel size)
Attribution: "Altimétrie © IGN LiDAR HD"
Without this file the app builds a rougher 3D model from building heights + OSM woods.
"""
import io
import math
import sys
from pathlib import Path

import httpx
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_osm import BBOX  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "data" / "twin" / "lidar.npz"
URL = "https://data.geopf.fr/wms-r/wms"
LAYER = "IGNF_LIDAR-HD_{}_ELEVATION.ELEVATIONGRIDCOVERAGE.WGS84G"
RES_M = 2.0
TILE = 1024          # pixels per request side


def get(cl, layer, s, w, n, e, wpx, hpx):
    params = {"SERVICE": "WMS", "VERSION": "1.3.0", "REQUEST": "GetMap", "LAYERS": layer, "STYLES": "",
              "CRS": "EPSG:4326", "BBOX": f"{s},{w},{n},{e}", "WIDTH": wpx, "HEIGHT": hpx,
              "FORMAT": "image/geotiff"}
    r = cl.get(URL, params=params)
    r.raise_for_status()
    if not r.headers.get("content-type", "").startswith("image"):
        raise RuntimeError(r.text[:300])
    a = np.array(Image.open(io.BytesIO(r.content)), np.float32)
    return a[::-1]                     # image row 0 = north -> our row 0 = south


def main():
    s, w, n, e = BBOX
    lat0 = (s + n) / 2
    W = int(math.ceil((e - w) * 111320 * math.cos(math.radians(lat0)) / RES_M))
    H = int(math.ceil((n - s) * 110540 / RES_M))
    out = {}
    with httpx.Client(timeout=120, headers={"User-Agent": "near-hackathon/0.1"}) as cl:
        for kind in ("MNT", "MNH"):
            full = np.zeros((H, W), np.float32)
            for r0 in range(0, H, TILE):
                for c0 in range(0, W, TILE):
                    h, wd = min(TILE, H - r0), min(TILE, W - c0)
                    ts, tn = s + (n - s) * r0 / H, s + (n - s) * (r0 + h) / H
                    tw, te = w + (e - w) * c0 / W, w + (e - w) * (c0 + wd) / W
                    full[r0:r0 + h, c0:c0 + wd] = get(cl, LAYER.format(kind), ts, tw, tn, te, wd, h)
                    print(f"  {kind} tile {r0},{c0} ok")
            out[kind.lower()] = full
    nodata = (out["mnt"] < -100) | (out["mnt"] > 1000)
    out["mnt"][nodata] = np.nan
    out["mnh"] = np.where((out["mnh"] < 0) | (out["mnh"] > 300), 0, out["mnh"]).astype(np.float32)
    np.savez_compressed(OUT, mnt=out["mnt"], mnh=out["mnh"], res=RES_M, bbox=np.array(BBOX))
    print(f"{OUT.name}: {W}x{H} at {RES_M} m | ground {np.nanpercentile(out['mnt'], [1, 50, 99]).round(1)} m"
          f" | objects >2 m on {np.mean(out['mnh'] > 2) * 100:.0f}% of the area, nodata {nodata.mean() * 100:.1f}%")


if __name__ == "__main__":
    main()
