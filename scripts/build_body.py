"""Build the casualty body mesh from a local SMPL-X model.

    python -m scripts.build_body [path/to/SMPLX_NEUTRAL.npz]

Default input: the old image-to-3D project, "3D POSE EST/expose/data/models/smplx/".
Output: data/body/body.npz (git-ignored: the SMPL-X licence forbids redistribution).

What it stores:
  faces      (F, 3)  triangles
  seg        (V,)    anatomical segment of each vertex (SEGMENTS in backend/body.py),
                     from the joint that moves it most (SMPL-X skinning weights)
  front      (V,)    1 = front surface (for "back" vs "chest" wounds)
  verts_<p>  (V, 3)  vertices posed in each posture (standard linear blend skinning)
  joints_<p> (22, 3) body joints in that posture (for the tourniquet ring)
Coordinates: metres, y up, the body's front facing +z, x = the casualty's LEFT.
"""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
DEFAULT = ROOT / "3D POSE EST" / "expose" / "data" / "models" / "smplx" / "SMPLX_NEUTRAL.npz"
OUT = ROOT / "data" / "body" / "body.npz"

sys.path.insert(0, str(ROOT))
from backend.body import JOINT_SEG, POSTURES, SEGMENTS  # noqa: E402


def rot(axis, deg):
    a = np.radians(deg)
    c, s = np.cos(a), np.sin(a)
    if axis == "x":
        return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
    if axis == "y":
        return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


# Local joint rotations per posture (SMPL-X joint ids: 0 pelvis, 1/2 L/R hip,
# 4/5 L/R knee, 16/17 L/R shoulder, 18/19 L/R elbow). T-pose arms point along +-x.
ARMS_DOWN = {16: rot("z", -65), 17: rot("z", 65)}
POSE_DEF = {
    "standing": {**ARMS_DOWN},
    "supine": {0: rot("x", -90), **ARMS_DOWN},                     # lying on the back, face up
    "prone": {0: rot("x", 90), **ARMS_DOWN},                       # face down
    "sitting": {1: rot("x", -90), 2: rot("x", -90), 4: rot("x", 90), 5: rot("x", 90),
                16: rot("z", -70), 17: rot("z", 70), 18: rot("y", 40), 19: rot("y", -40)},
    # On the right side, top (left) leg bent forward, top arm forward.
    "recovery": {0: rot("z", 90), 1: rot("x", -70), 4: rot("x", 80),
                 16: rot("z", -10) @ rot("y", -70), 17: rot("z", 65), 18: rot("y", -60)},
}


def lbs(v, J, W, parents, R):
    """Linear blend skinning with local rotations R {joint: 3x3}, no shape change."""
    n = len(parents)
    G = np.zeros((n, 4, 4))
    for j in range(n):
        T = np.eye(4)
        T[:3, :3] = R.get(j, np.eye(3))
        T[:3, 3] = J[j] - (J[parents[j]] if parents[j] >= 0 else 0)
        G[j] = T if parents[j] < 0 else G[parents[j]] @ T
    A = G.copy()
    for j in range(n):                          # remove the rest-pose joint position
        A[j, :3, 3] -= G[j, :3, :3] @ J[j]
    T = np.einsum("vj,jab->vab", W, A)          # (V, 4, 4) per-vertex transform
    vh = np.c_[v, np.ones(len(v))]
    out = np.einsum("vab,vb->va", T, vh)[:, :3]
    joints = G[:, :3, 3]
    return out, joints


def main():
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT
    if not src.exists():
        raise SystemExit(f"SMPL-X model not found: {src}")
    z = np.load(src, allow_pickle=True)
    v = z["v_template"].astype(np.float64)
    W = z["weights"].astype(np.float64)
    J = z["J_regressor"] @ v
    parents = z["kintree_table"][0].astype(np.int64)
    parents[0] = -1
    faces = z["f"].astype(np.int32)
    assert J[1, 0] > 0, "expected the left hip on +x"

    dom = W.argmax(axis=1)
    seg = np.array([SEGMENTS.index(JOINT_SEG.get(int(j), "head")) for j in dom], np.uint8)
    # Front surface: in front of the segment's mean depth (rest pose faces +z).
    front = np.zeros(len(v), np.uint8)
    for s in range(len(SEGMENTS)):
        m = seg == s
        if m.any():
            front[m] = v[m, 2] >= np.median(v[m, 2])

    out = {"faces": faces, "seg": seg, "front": front}
    for p in POSTURES:
        pv, pj = lbs(v, J, W, parents, POSE_DEF[p])
        floor = pv[:, 1].min()                   # stand / lie on the ground (y = 0)
        pv[:, 1] -= floor
        pj[:, 1] -= floor
        out[f"verts_{p}"] = pv.astype(np.float32)
        out[f"joints_{p}"] = pj[:22].astype(np.float32)
        print(f"{p:9s} size x {np.ptp(pv[:, 0]):.2f}  y {np.ptp(pv[:, 1]):.2f}  z {np.ptp(pv[:, 2]):.2f} m")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(OUT, **out)
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB), {len(v)} vertices, {len(faces)} faces")
    for s, name in enumerate(SEGMENTS):
        print(f"  {name:12s} {(seg == s).sum():5d} vertices")


if __name__ == "__main__":
    main()
