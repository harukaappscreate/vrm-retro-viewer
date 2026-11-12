"""vrma_io - read a VRM Animation (.vrma) into the viewer's motion format.

The same method as tools/make_motions.py (which baked the bundled motions): per humanoid bone and frame (30 fps), the
world rotation delta from the rest pose, plus the hips movement divided by the hips height, in place.
"""
# SPDX-License-Identifier: MIT
import numpy as np

import vrm_io as V

FPS = 30.0


def _qrot(q, v):
    u = np.array(q[:3])
    return v + 2 * np.cross(u, np.cross(u, v) + q[3] * v)


def _slerp(a, b, f):
    d = float(np.dot(a, b))
    if d < 0:
        b, d = -b, -d
    if d > 0.9995:
        r = a + (b - a) * f
        return r / np.linalg.norm(r)
    th = np.arccos(d)
    return (np.sin((1 - f) * th) * a + np.sin(f * th) * b) / np.sin(th)


def _sample(times, vals, t):
    if t <= times[0]:
        return vals[0]
    if t >= times[-1]:
        return vals[-1]
    i = int(np.searchsorted(times, t)) - 1
    f = (t - times[i]) / (times[i + 1] - times[i])
    return _slerp(vals[i], vals[i + 1], f) if vals.shape[1] == 4 else vals[i] * (1 - f) + vals[i + 1] * f


def read_vrma(data, bones):
    """(D (F, len(bones), 4), hips (F, 3), seconds, name) for the VRM 1.0 bone names in `bones`."""
    j, binc = V.read_glb(data)
    ext = j.get("extensions", {}).get("VRMC_vrm_animation")
    if not ext:
        raise ValueError("not a VRM Animation (no VRMC_vrm_animation)")
    hb = {k: v["node"] for k, v in ext.get("humanoid", {}).get("humanBones", {}).items()}
    if "hips" not in hb:
        raise ValueError("VRMA: no hips bone")
    if not j.get("animations"):
        raise ValueError("no animation in this file")
    nodes = j["nodes"]
    N = len(nodes)
    parent = {c: i for i, n in enumerate(nodes) for c in n.get("children", [])}
    order, seen = [], set()

    def visit(i):
        if i in seen:
            return
        if i in parent:
            visit(parent[i])
        seen.add(i)
        order.append(i)

    for i in range(N):
        visit(i)
    T0 = [np.array(n.get("translation", (0, 0, 0)), float) for n in nodes]
    R0 = [np.array(n.get("rotation", (0, 0, 0, 1)), float) for n in nodes]

    def worlds(Ts, Rs):
        WR, WP = [None] * N, [None] * N
        for i in order:
            p = parent.get(i)
            if p is None:
                WR[i], WP[i] = Rs[i], Ts[i]
            else:
                WR[i] = V.qmul(WR[p], Rs[i])
                WP[i] = WP[p] + _qrot(WR[p], Ts[i])
        return WR, WP

    rWR, rWP = worlds(T0, R0)
    anim = j["animations"][0]
    tracks, dur = {}, 0.0
    for ch in anim["channels"]:
        s = anim["samplers"][ch["sampler"]]
        t = V.accessor(j, binc, s["input"]).reshape(-1).astype(float)
        v = V.accessor(j, binc, s["output"]).astype(float)
        tracks.setdefault(ch["target"]["node"], {})[ch["target"]["path"]] = (t, v)
        dur = max(dur, float(t[-1]))
    F = max(2, int(round(dur * FPS)) + 1)
    D = np.zeros((F, len(bones), 4), np.float32)
    D[..., 3] = 1.0
    hips = np.zeros((F, 3), np.float32)
    hip_h = rWP[hb["hips"]][1] or 1.0
    feet = [hb[b] for b in ("leftFoot", "rightFoot", "leftToes", "rightToes") if b in hb]
    rest_foot = min(rWP[f][1] for f in feet) if feet else 0.0
    lowest = 1e9
    for k in range(F):
        t = k / FPS
        Ts, Rs = list(T0), list(R0)
        for i, tr in tracks.items():
            if "translation" in tr:
                Ts[i] = _sample(*tr["translation"], t)
            if "rotation" in tr:
                q = _sample(*tr["rotation"], t)
                Rs[i] = q / np.linalg.norm(q)
        WR, WP = worlds(Ts, Rs)
        for bi, b in enumerate(bones):
            n = hb.get(b)
            if n is not None:
                D[k, bi] = V.qmul(WR[n], V.qconj(rWR[n]))
        d = WP[hb["hips"]] - rWP[hb["hips"]]
        d[0] = d[2] = 0.0                                       # in place: no travel (the viewer and sprites stay put)
        hips[k] = d / hip_h
        if feet:
            lowest = min(lowest, min(WP[f][1] for f in feet) - rest_foot - (WP[hb["hips"]][1] - rWP[hb["hips"]][1]) + d[1])
    if feet:
        hips[:, 1] += max(0.0, -lowest) / hip_h                 # keep the feet on the ground
    return D, hips, (F - 1) / FPS, anim.get("name", "")
