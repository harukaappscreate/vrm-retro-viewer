"""Bake the bundled CC0 motions (.vrma) into motions.npz for the viewer.

    python tools/make_motions.py            # reads vrma/*.vrma, writes motions.npz

For every humanoid bone (VRM 1.0 names) and frame (30 fps) it stores the world-space rotation *delta* from the rest
T-pose, plus the hips movement divided by the hips height.  Any VRM can then be posed with
    world(bone) = delta * rest_world(bone)
(for VRM 0.x the delta is first turned by 180 degrees around Y, because 0.x faces -Z).

Motions: Quaternius Universal Animation Library 1 & 2 and KayKit Character Animations (all CC0), converted to .vrma
by the open-vrma project (https://huggingface.co/datasets/Sanami/open-vrma).  They are not in this repository; put
quaternius/ual1 and quaternius/ual2 into vrma/q/, kaykit/medium into vrma/kk/medium/ and kaykit/large into
vrma/kk/large/ (the CMU clips of open-vrma are not CC0 and are not used).
A list of files is played one after another (the jump = start + in the air + landing); "file:0.4" keeps 0.4 s.
"""
# SPDX-License-Identifier: MIT
import io
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import vrm_io as V  # noqa: E402

# The hand-picked set first (short ids the samples use), then every other CC0 motion found in vrma/.
# (id, label, file(s), loop) - files are relative to vrma/ without ".vrma"
MOTIONS = [
    ("idle", "Idle", "q/Idle_Loop", True),
    ("walk", "Walk", "q/Walk_Loop", True),
    ("run", "Run", "q/Jog_Fwd_Loop", True),
    ("sprint", "Sprint", "q/Sprint_Loop", True),
    ("jump", "Jump", ["q/Jump_Start", "q/Jump_Loop:0.4", "q/Jump_Land"], False),
    ("punch", "Punch", "q/Punch_Jab", False),
    ("sword", "Sword", "q/Sword_Attack", False),
    ("spell", "Spell", "q/Spell_Simple_Shoot", False),
    ("hit", "Hit", "q/Hit_Chest", False),
    ("death", "Death", "q/Death01", False),
    ("roll", "Roll", "q/Roll", False),
    ("crouch", "Crouch", "q/Crouch_Idle_Loop", True),
    ("talk", "Talk", "q/Idle_Talking_Loop", True),
    ("dance", "Dance", "q/Dance_Loop", True),
    ("ninja_jump", "Ninja Jump", ["q/NinjaJump_Start", "q/NinjaJump_Idle_Loop:0.4", "q/NinjaJump_Land"], False),
]
# pieces already used above (they stay out of the automatic list)
USED_PARTS = {"q/Jump_Start", "q/Jump_Loop", "q/Jump_Land", "q/NinjaJump_Start", "q/NinjaJump_Idle_Loop", "q/NinjaJump_Land"}
GROUPS = [("q", "", "Quaternius"), ("kk/medium", "kk_", "KayKit"), ("kk/large", "kkl_", "KayKit Large")]
# left out: transform tests, and monster spawns that start under the ground / in the air (they need effects),
# and the 1 m climb (it leaves the sprite cell)
SKIP = {"EXPERIMENTAL_Medium_Transform", "EXPERIMENTAL_Large_Transform", "Skeletons_Awaken_Floor",
        "Skeletons_Awaken_Floor_Long", "Skeletons_Spawn_Ground", "Spawn_Air", "Spawn_Ground", "ClimbUp_1m_RM"}


ARM_FIX = 28.0       # KayKit characters are chunky: their arms are posed this many degrees further out


def lower_arms(bones, D, deg):
    """Turn both whole arms down by deg around the chest's forward axis (left arm = +X in the VRM 1.0 frame)."""
    D = D.astype(np.float64).copy()
    chest = next((b for b in ("upperChest", "chest", "spine") if b in bones), None)
    for side, sign in (("left", -1.0), ("right", 1.0)):
        r = V.qaxis((0, 0, 1), sign * deg)
        idx = [i for i, b in enumerate(bones) if b.startswith(side) and
               any(k in b for k in ("UpperArm", "LowerArm", "Hand", "Thumb", "Index", "Middle", "Ring", "Little"))]
        for f in range(len(D)):
            c = D[f, bones.index(chest)] if chest else np.array([0.0, 0.0, 0.0, 1.0])
            fix = V.qmul(V.qmul(c, r), V.qconj(c))                 # the turn, in the chest's current frame
            for i in idx:
                D[f, i] = V.qmul(fix, D[f, i])
    return D.astype(np.float32)


def is_loop(stem):
    """Quaternius says "_Loop".  KayKit: idles, poses and "-ing" names repeat (Chopping), the rest play once (Chop)."""
    t = stem.split("_")
    return ("Loop" in t or "Idle" in t or "Pose" in t or t[-1].endswith("ing")
            or t[0] in ("Running", "Walking", "Sneaking", "Crawling", "Crouching") or stem in ("Push_Ups", "Sit_Ups"))


def all_motions():
    """The hand-picked list, then every other .vrma in vrma/ (sorted, grouped by source)."""
    out = [m + ("Basic",) for m in MOTIONS]
    used = USED_PARTS | {m[2] for m in MOTIONS if isinstance(m[2], str)}
    ids = {m[0] for m in MOTIONS}
    for folder, prefix, group in GROUPS:
        for f in sorted((ROOT / "vrma" / folder).glob("*.vrma")):
            stem = folder + "/" + f.stem
            if stem in used or f.stem in SKIP:
                continue
            mid = prefix + f.stem.lower()
            if mid in ids:
                continue
            ids.add(mid)
            label = f.stem.replace("_Loop", "").replace("_", " ")
            loop = is_loop(f.stem)
            out.append((mid, label, stem, loop, group))
    return out


FPS = 30.0


def qrot(q, v):
    x, y, z, w = q
    u = np.array((x, y, z))
    return v + 2 * np.cross(u, np.cross(u, v) + w * v)


def slerp(a, b, f):
    d = float(np.dot(a, b))
    if d < 0:
        b, d = -b, -d
    if d > 0.9995:
        r = a + (b - a) * f
        return r / np.linalg.norm(r)
    th = np.arccos(d)
    return (np.sin((1 - f) * th) * a + np.sin(f * th) * b) / np.sin(th)


def sample(times, vals, t):
    if t <= times[0]:
        return vals[0]
    if t >= times[-1]:
        return vals[-1]
    i = int(np.searchsorted(times, t)) - 1
    f = (t - times[i]) / (times[i + 1] - times[i])
    return slerp(vals[i], vals[i + 1], f) if vals.shape[1] == 4 else vals[i] * (1 - f) + vals[i + 1] * f


def bake(path, loop):
    j, binc = V.read_glb(path.read_bytes())
    hb = {k: v["node"] for k, v in j["extensions"]["VRMC_vrm_animation"]["humanoid"]["humanBones"].items()}
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
                WP[i] = WP[p] + qrot(WR[p], Ts[i])
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
    bones = sorted(hb)
    D = np.zeros((F, len(bones), 4), np.float32)
    hips = np.zeros((F, 3), np.float32)
    hip_h = rWP[hb["hips"]][1]
    feet = [hb[b] for b in ("leftFoot", "rightFoot", "leftToes", "rightToes") if b in hb]
    rest_foot = min(rWP[f][1] for f in feet)
    lowest = 1e9
    for k in range(F):
        t = k / FPS
        Ts, Rs = list(T0), list(R0)
        for i, tr in tracks.items():
            if "translation" in tr:
                Ts[i] = sample(*tr["translation"], t)
            if "rotation" in tr:
                q = sample(*tr["rotation"], t)
                Rs[i] = q / np.linalg.norm(q)
        WR, WP = worlds(Ts, Rs)
        for bi, b in enumerate(bones):
            n = hb[b]
            D[k, bi] = V.qmul(WR[n], V.qconj(rWR[n]))
        d = WP[hb["hips"]] - rWP[hb["hips"]]
        d[0] = d[2] = 0.0                                       # in place: no travel (the viewer and sprites stay put)
        hips[k] = d / hip_h
        lowest = min(lowest, min(WP[f][1] for f in feet) - rest_foot - (WP[hb["hips"]][1] - rWP[hb["hips"]][1]) + d[1])
    # keep the feet on the ground: shift the whole clip up if a foot went below the rest height
    ground = max(0.0, -lowest) / hip_h
    hips[:, 1] += ground
    return bones, D, hips, F / FPS


def main():
    out = {}
    meta = []
    all_bones = None
    for mid, label, stem, loop, group in all_motions():
        parts = []
        for s in (stem if isinstance(stem, list) else [stem]):
            name, _, limit = s.partition(":")                  # "file:0.4" = only the first 0.4 seconds
            b, d, h, _ = bake(ROOT / "vrma" / (name + ".vrma"), loop)
            n = int(float(limit) * FPS) + 1 if limit else len(d)
            if name.startswith("kk/"):
                d = lower_arms(b, d, ARM_FIX)
            parts.append((b, d[:n], h[:n]))
        bones = parts[0][0]
        D = np.concatenate([p[1] for p in parts])
        hips = np.concatenate([p[2] for p in parts])
        dur = (len(D) - 1) / FPS
        if all_bones is None:
            all_bones = bones
        idx = [bones.index(b) if b in bones else -1 for b in all_bones]
        Dn = np.zeros((len(D), len(all_bones), 4), np.float32)
        Dn[..., 3] = 1
        for k, i in enumerate(idx):
            if i >= 0:
                Dn[:, k] = D[:, i]
        out["d_" + mid] = Dn.astype(np.float16)
        out["h_" + mid] = hips.astype(np.float16)
        meta.append(dict(id=mid, label=label, group=group, source=stem if isinstance(stem, str) else "+".join(stem), loop=loop,
                         frames=len(D), seconds=round(dur, 3)))
        print(mid, len(D), "frames", round(dur, 2), "s", "loop" if loop else "")
    out["bones"] = np.array(all_bones)
    out["meta"] = np.frombuffer(json.dumps(meta).encode(), np.uint8)
    b = io.BytesIO()
    np.savez_compressed(b, **out)
    (ROOT / "motions.npz").write_bytes(b.getvalue())
    print("motions.npz", len(b.getvalue()), "bytes")


if __name__ == "__main__":
    main()
