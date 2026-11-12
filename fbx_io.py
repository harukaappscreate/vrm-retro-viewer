"""fbx_io - read the skeleton animation of a binary FBX (7.x) with plain Python + numpy.

Made for motion files such as Mixamo's ("Without Skin" or with skin: only the bones and their curves are read).
The motion is returned as world-space rotations per bone and frame, so it can be turned into the viewer's format
(rotation delta from the rest pose).  ASCII FBX and FBX 6 are not supported.
"""
# SPDX-License-Identifier: MIT
import math
import struct
import zlib

import numpy as np

TICKS = 46186158000.0            # FBX time unit per second


# ---------------------------------------------------------------------- the node tree
class FbxNode:
    __slots__ = ("name", "props", "children")

    def __init__(self, name, props, children):
        self.name, self.props, self.children = name, props, children

    def find(self, name):
        return next((c for c in self.children if c.name == name), None)

    def all(self, name):
        return [c for c in self.children if c.name == name]


_ARRAY = {b"f": ("<f", 4), b"d": ("<d", 8), b"l": ("<q", 8), b"i": ("<i", 4), b"b": ("<b", 1)}
_NP = {b"f": np.float32, b"d": np.float64, b"l": np.int64, b"i": np.int32, b"b": np.int8}


def _read_prop(d, o):
    t = d[o:o + 1]
    o += 1
    if t == b"Y":
        return struct.unpack_from("<h", d, o)[0], o + 2
    if t == b"C":
        return d[o] != 0, o + 1
    if t == b"I":
        return struct.unpack_from("<i", d, o)[0], o + 4
    if t == b"F":
        return struct.unpack_from("<f", d, o)[0], o + 4
    if t == b"D":
        return struct.unpack_from("<d", d, o)[0], o + 8
    if t == b"L":
        return struct.unpack_from("<q", d, o)[0], o + 8
    if t in _ARRAY:
        n, enc, clen = struct.unpack_from("<III", d, o)
        o += 12
        raw = d[o:o + clen]
        if enc == 1:
            raw = zlib.decompress(raw)
        return np.frombuffer(raw, _NP[t], n), o + clen
    if t in (b"S", b"R"):
        n = struct.unpack_from("<I", d, o)[0]
        o += 4
        raw = d[o:o + n]
        return (raw.decode("utf-8", "replace") if t == b"S" else raw), o + n
    raise ValueError("FBX: unknown property type %r" % t)


def _read_node(d, o, wide):
    if wide:
        end, nprops, _plen = struct.unpack_from("<QQQ", d, o)
        o += 24
    else:
        end, nprops, _plen = struct.unpack_from("<III", d, o)
        o += 12
    nlen = d[o]
    o += 1
    if end == 0:
        return None, o
    name = d[o:o + nlen].decode("ascii", "replace")
    o += nlen
    props = []
    for _ in range(nprops):
        v, o = _read_prop(d, o)
        props.append(v)
    children = []
    null = 25 if wide else 13
    while o < end - null + 1 and o < end:
        if end - o == null and d[o:end] == b"\0" * null:
            break
        c, o = _read_node(d, o, wide)
        if c is None:
            break
        children.append(c)
    return FbxNode(name, props, children), end


def parse(data):
    """The whole file as an FbxNode tree (the root has no name)."""
    if data[:20] != b"Kaydara FBX Binary  ":
        head = data[:400].lstrip()
        if head.startswith(b";") or b"FBXHeaderExtension" in head:
            raise ValueError("this is a text (ASCII) FBX. Export it again as FBX Binary")
        raise ValueError("not an FBX file")
    version = struct.unpack_from("<I", data, 23)[0]
    if version < 7000:
        raise ValueError("FBX %d.%d is too old. Export it again as FBX 7 (2011 or later), Binary"
                         % (version // 1000, version % 1000 // 100))
    wide = version >= 7500
    o = 27
    top = []
    while o < len(data):
        n, o2 = _read_node(data, o, wide)
        if n is None:
            break
        top.append(n)
        o = o2
    root = FbxNode("", [], top)
    root.props = [version]
    return root


def props70(node):
    """{name: values} from a Properties70 block."""
    out = {}
    p = node.find("Properties70") if node is not None else None
    for c in (p.children if p else []):
        if c.name == "P" and c.props:
            out[c.props[0]] = c.props[4:]
    return out


# ---------------------------------------------------------------------- rotations
def quat_euler(deg, order=0):
    """FBX Euler angles (degrees) -> quaternion (x, y, z, w).  order 0 = XYZ: X is applied first."""
    axes = {0: "XYZ", 1: "XZY", 2: "YZX", 3: "YXZ", 4: "ZXY", 5: "ZYX"}.get(int(order), "XYZ")
    q = np.array([0.0, 0.0, 0.0, 1.0])
    for ax in axes:
        a = math.radians(float(deg["XYZ".index(ax)])) / 2
        r = np.zeros(4)
        r["XYZ".index(ax)] = math.sin(a)
        r[3] = math.cos(a)
        q = qmul(r, q)                    # the later axis turns after the earlier one
    return q


def qmul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return np.array([aw * bx + ax * bw + ay * bz - az * by,
                     aw * by - ax * bz + ay * bw + az * bx,
                     aw * bz + ax * by - ay * bx + az * bw,
                     aw * bw - ax * bx - ay * by - az * bz])


def qconj(q):
    return np.array([-q[0], -q[1], -q[2], q[3]])


def vmul(a, b):
    """Quaternion product for arrays (..., 4)."""
    ax, ay, az, aw = np.moveaxis(a, -1, 0)
    bx, by, bz, bw = np.moveaxis(b, -1, 0)
    return np.stack([aw * bx + ax * bw + ay * bz - az * by,
                     aw * by - ax * bz + ay * bw + az * bx,
                     aw * bz + ax * by - ay * bx + az * bw,
                     aw * bw - ax * bx - ay * by - az * bz], -1)


def vrot(q, v):
    """Rotate vectors (..., 3) by quaternions (..., 4)."""
    u = q[..., :3]
    return v + 2 * np.cross(u, np.cross(u, v) + q[..., 3:4] * v)


def veuler(deg, order=0):
    """FBX Euler angles (F, 3) in degrees -> quaternions (F, 4); same convention as quat_euler."""
    axes = {0: "XYZ", 1: "XZY", 2: "YZX", 3: "YXZ", 4: "ZXY", 5: "ZYX"}.get(int(order), "XYZ")
    a = np.radians(np.asarray(deg, np.float64)) / 2
    q = np.zeros(a.shape[:-1] + (4,))
    q[..., 3] = 1.0
    for ax in axes:
        k = "XYZ".index(ax)
        r = np.zeros_like(q)
        r[..., k] = np.sin(a[..., k])
        r[..., 3] = np.cos(a[..., k])
        q = vmul(r, q)
    return q


def qrot(q, v):
    u = np.array(q[:3])
    return v + 2 * np.cross(u, np.cross(u, v) + q[3] * v)


# ---------------------------------------------------------------------- the skeleton and its animations
class FbxFile:
    """The bones of an FBX and its animation stacks (takes).  motion(i) samples take i."""

    def __init__(self, data):
        root = parse(data)
        self.version = root.props[0]
        objects = root.find("Objects")
        conns = root.find("Connections")
        if objects is None or conns is None:
            raise ValueError("FBX: no Objects / Connections")
        models, curvenodes, curves, layers, stacks = {}, {}, {}, {}, {}
        for n in objects.children:
            if n.name == "Model":
                models[n.props[0]] = n
            elif n.name == "AnimationCurveNode":
                curvenodes[n.props[0]] = n
            elif n.name == "AnimationLayer":
                layers[n.props[0]] = n
            elif n.name == "AnimationStack":
                stacks[n.props[0]] = n
            elif n.name == "AnimationCurve":
                kt, kv = n.find("KeyTime"), n.find("KeyValueFloat")
                if kt is not None and kv is not None:
                    curves[n.props[0]] = (np.asarray(kt.props[0], np.float64) / TICKS, np.asarray(kv.props[0], np.float64))
        parent_of, cn_target, curve_target, layer_of, stack_of = {}, {}, {}, {}, {}
        for c in conns.children:
            if c.name != "C":
                continue
            kind, src, dst = c.props[0], c.props[1], c.props[2]
            if kind == "OO" and src in models and dst in models:
                parent_of[src] = dst
            elif kind == "OP" and src in curvenodes and dst in models:
                cn_target[src] = (dst, c.props[3])
            elif kind == "OP" and src in curves and dst in curvenodes:
                curve_target.setdefault(dst, {})[c.props[3]] = src
            elif kind == "OO" and src in curvenodes and dst in layers:
                layer_of[src] = dst
            elif kind == "OO" and src in layers and dst in stacks:
                stack_of[src] = dst

        # bones: LimbNode models, with the Null / Root nodes above them (a Blender "Armature" carries the axes)
        def mtype(m):
            return m.props[2] if len(m.props) > 2 else ""

        keep = {i for i, m in models.items() if mtype(m) in ("LimbNode", "Root", "Null", "Limb")}
        ids, seen = [], set()

        def visit(i):
            if i in seen or i not in keep:
                return
            p = parent_of.get(i)
            if p in keep:
                visit(p)
            seen.add(i)
            ids.append(i)

        for i in sorted(keep):
            visit(i)
        self.ids = ids
        self.bones = [models[i].props[1].split("\x00")[0] for i in ids]
        index = {i: k for k, i in enumerate(ids)}
        self.parent = [index.get(parent_of.get(i), -1) for i in ids]
        self.T0, self.R0, self.pre, self.post, self.order = [], [], [], [], []
        for i in ids:
            p = props70(models[i])
            self.T0.append(np.array(p.get("Lcl Translation", [0, 0, 0])[:3], float))
            self.R0.append(np.array(p.get("Lcl Rotation", [0, 0, 0])[:3], float))
            self.pre.append(quat_euler(p.get("PreRotation", [0, 0, 0])[:3]))
            self.post.append(quat_euler(p.get("PostRotation", [0, 0, 0])[:3]))
            self.order.append(int(p.get("RotationOrder", [0])[0]))

        # the curves of each take: {(bone, "Lcl Translation" / "Lcl Rotation"): [3 channels]}
        take_ids = sorted(stacks, key=lambda s: list(stacks).index(s)) or [None]
        self.takes = []
        for st in take_ids:
            tracks, dur = {}, 0.0
            for cn, (mid, prop) in cn_target.items():
                if mid not in index or prop not in ("Lcl Translation", "Lcl Rotation"):
                    continue
                if st is not None and stack_of.get(layer_of.get(cn)) != st:
                    continue
                defaults = props70(curvenodes[cn])
                chans = []
                for axis in "XYZ":
                    cid = curve_target.get(cn, {}).get("d|" + axis)
                    if cid is not None:
                        t, v = curves[cid]
                        chans.append((t, v))
                        if len(t):
                            dur = max(dur, float(t[-1]))
                    else:
                        chans.append(float(defaults.get("d|" + axis, [0.0])[0]))
                tracks[(index[mid], prop)] = chans
            name = stacks[st].props[1].split("\x00")[0] if st is not None else "Take"
            self.takes.append((name.split("|")[-1], tracks, dur))     # Blender writes "Armature|Walk"

    def sample(self, tracks, times):
        """World rotations (F, B, 4) and positions (F, B, 3) at the given times."""
        F, B = len(times), len(self.ids)
        Ts = [np.tile(v, (F, 1)) for v in self.T0]
        Rs = [np.tile(v, (F, 1)) for v in self.R0]
        for (b, prop), chans in tracks.items():
            v = np.stack([np.interp(times, c[0], c[1]) if isinstance(c, tuple) else np.full(F, c) for c in chans], -1)
            if prop == "Lcl Translation":
                Ts[b] = v
            else:
                Rs[b] = v
        W = np.zeros((F, B, 4))
        P = np.zeros((F, B, 3))
        for b in range(B):
            # local rotation = PreRotation * Lcl Rotation * PostRotation^-1 (pivots, offsets and scaling are ignored)
            lr = vmul(vmul(self.pre[b], veuler(Rs[b], self.order[b])), qconj(self.post[b]))
            p = self.parent[b]
            if p < 0:
                W[:, b], P[:, b] = lr, Ts[b]
            else:
                W[:, b] = vmul(W[:, p], lr)
                P[:, b] = P[:, p] + vrot(W[:, p], Ts[b])
        return W, P

    def rest(self):
        """The rest pose of the bones: (B, 4) world rotations and (B, 3) positions."""
        W, P = self.sample({}, np.zeros(1))
        return W[0], P[0]

    def motion(self, k, fps=30.0):
        """Take k as an FbxMotion (sampled at fps)."""
        return FbxMotion(self, k, fps)


class FbxMotion:
    """One take: rest_world / rest_pos (B, 4) / (B, 3) and world / pos (F, B, 4) / (F, B, 3), in the file's axes."""

    def __init__(self, data, take=0, fps=30.0):
        f = data if isinstance(data, FbxFile) else FbxFile(data)
        self.file, self.bones, self.parent = f, f.bones, f.parent
        self.name, tracks, dur = f.takes[take]
        self.fps, self.duration = fps, dur
        self.frames = max(2, int(round(dur * fps)) + 1)
        self.rest_world, self.rest_pos = f.rest()
        self.world, self.pos = f.sample(tracks, np.arange(self.frames) / fps)


# ---------------------------------------------------------------------- bone names -> VRM humanoid
def _sides(table, left, right):
    """table of (name with {s}, vrm name with {S}) -> both sides."""
    out = {}
    for src, dst in table:
        out[src.format(s=left)] = dst.format(S="left")
        out[src.format(s=right)] = dst.format(S="right")
    return out


_MIXAMO = {"Hips": "hips", "Spine": "spine", "Spine1": "chest", "Spine2": "upperChest", "Neck": "neck", "Head": "head"}
_MIXAMO.update(_sides([
    ("{s}Shoulder", "{S}Shoulder"), ("{s}Arm", "{S}UpperArm"), ("{s}ForeArm", "{S}LowerArm"), ("{s}Hand", "{S}Hand"),
    ("{s}UpLeg", "{S}UpperLeg"), ("{s}Leg", "{S}LowerLeg"), ("{s}Foot", "{S}Foot"), ("{s}ToeBase", "{S}Toes"),
    ("{s}Eye", "{S}Eye"),
    ("{s}HandThumb1", "{S}ThumbMetacarpal"), ("{s}HandThumb2", "{S}ThumbProximal"), ("{s}HandThumb3", "{S}ThumbDistal"),
] + [("{s}Hand%s%d" % (f, k), "{S}%s%s" % (v, j)) for f, v in (("Index", "Index"), ("Middle", "Middle"), ("Ring", "Ring"),
                                                              ("Pinky", "Little"))
     for k, j in ((1, "Proximal"), (2, "Intermediate"), (3, "Distal"))], "Left", "Right"))

# Unreal Engine mannequin names (also Quaternius' Universal Animation Library and many game rigs)
_UNREAL = {"pelvis": "hips", "spine_01": "spine", "spine_02": "chest", "spine_03": "upperChest", "neck_01": "neck",
           "head": "head"}
_UNREAL.update(_sides([
    ("clavicle_{s}", "{S}Shoulder"), ("upperarm_{s}", "{S}UpperArm"), ("lowerarm_{s}", "{S}LowerArm"),
    ("hand_{s}", "{S}Hand"), ("thigh_{s}", "{S}UpperLeg"), ("calf_{s}", "{S}LowerLeg"), ("foot_{s}", "{S}Foot"),
    ("ball_{s}", "{S}Toes"),
    ("thumb_01_{s}", "{S}ThumbMetacarpal"), ("thumb_02_{s}", "{S}ThumbProximal"), ("thumb_03_{s}", "{S}ThumbDistal"),
] + [("%s_0%d_{s}" % (f, k), "{S}%s%s" % (v, j)) for f, v in (("index", "Index"), ("middle", "Middle"), ("ring", "Ring"),
                                                             ("pinky", "Little"))
     for k, j in ((1, "Proximal"), (2, "Intermediate"), (3, "Distal"))], "l", "r"))

# VRoid / VRM 0.x bone names (J_Bip_...)
_VROID = {"J_Bip_C_Hips": "hips", "J_Bip_C_Spine": "spine", "J_Bip_C_Chest": "chest", "J_Bip_C_UpperChest": "upperChest",
          "J_Bip_C_Neck": "neck", "J_Bip_C_Head": "head"}
_VROID.update(_sides([
    ("J_Bip_{s}_Shoulder", "{S}Shoulder"), ("J_Bip_{s}_UpperArm", "{S}UpperArm"), ("J_Bip_{s}_LowerArm", "{S}LowerArm"),
    ("J_Bip_{s}_Hand", "{S}Hand"), ("J_Bip_{s}_UpperLeg", "{S}UpperLeg"), ("J_Bip_{s}_LowerLeg", "{S}LowerLeg"),
    ("J_Bip_{s}_Foot", "{S}Foot"), ("J_Bip_{s}_ToeBase", "{S}Toes"),
    ("J_Bip_{s}_Thumb1", "{S}ThumbMetacarpal"), ("J_Bip_{s}_Thumb2", "{S}ThumbProximal"), ("J_Bip_{s}_Thumb3", "{S}ThumbDistal"),
] + [("J_Bip_{s}_%s%d" % (f, k), "{S}%s%s" % (v, j)) for f, v in (("Index", "Index"), ("Middle", "Middle"),
                                                                   ("Ring", "Ring"), ("Little", "Little"))
     for k, j in ((1, "Proximal"), (2, "Intermediate"), (3, "Distal"))], "L", "R"))

RIGS = [("Mixamo", _MIXAMO), ("Unreal", _UNREAL), ("VRoid", _VROID)]


def humanoid(names):
    """({vrm bone: index}, rig name) for the naming scheme that matches the most bones.  Prefixes such as
    "mixamorig:" or "Armature|" are ignored, and so is the case of the letters."""
    keys = [n.split(":")[-1].split("|")[-1].lower() for n in names]
    best = ({}, "")
    for rig, table in RIGS:
        low = {k.lower(): v for k, v in table.items()}
        out = {}
        for i, k in enumerate(keys):
            if k in low and low[k] not in out:
                out[low[k]] = i
        if len(out) > len(best[0]):
            best = (out, rig)
    return best


def mixamo_humanoid(names):
    return humanoid(names)[0]


# ---------------------------------------------------------------------- into the viewer's frame and format
def _axis_basis(fm, human):
    """A rotation (3 x 3, axis-aligned) that turns the file's axes into the viewer's: +Y up, +X the character's left,
    +Z forward.  Read from the rest pose (hips -> head is up, right -> left upper arm is left)."""
    def snap(v):
        k = int(np.argmax(np.abs(v)))
        out = np.zeros(3)
        out[k] = np.sign(v[k])
        return out
    P = fm.rest_pos
    up = snap(P[human["head"]] - P[human["hips"]])
    left = snap(P[human["leftUpperArm"]] - P[human["rightUpperArm"]])
    if abs(np.dot(up, left)) > 0.5:
        raise ValueError("FBX: cannot tell up from left in the rest pose")
    fwd = np.cross(left, up)
    return np.array([left, up, fwd])           # rows: new X, Y, Z in old axes


def arm_droop(fm, human, rest=None):
    """How far (degrees) the upper arms point down in the rest pose: about 0 for a T-pose, 30-50 for an A-pose.
    The motions are measured from the rest pose, so an A-pose rest makes the arms look wrong on a VRM (T-pose)."""
    rp = rest[1] if rest is not None else fm.rest_pos
    M = _axis_basis(type("R", (), {"rest_pos": rp})(), human)
    out = []
    for side in ("left", "right"):
        a, b = human.get(side + "UpperArm"), human.get(side + "LowerArm")
        if a is None or b is None:
            continue
        v = (rp[b] - rp[a]) @ M.T
        out.append(math.degrees(math.atan2(-v[1], math.hypot(v[0], v[2]))))
    return max(out) if out else 0.0


def _mat_quat(M):
    """Rotation matrix -> quaternion (x, y, z, w)."""
    t = np.trace(M)
    if t > 0:
        s = math.sqrt(t + 1.0) * 2
        return np.array([(M[2, 1] - M[1, 2]) / s, (M[0, 2] - M[2, 0]) / s, (M[1, 0] - M[0, 1]) / s, 0.25 * s])
    i = int(np.argmax(np.diag(M)))
    j, k = (i + 1) % 3, (i + 2) % 3
    s = math.sqrt(1.0 + M[i, i] - M[j, j] - M[k, k]) * 2
    q = np.zeros(4)
    q[i] = 0.25 * s
    q[j] = (M[j, i] + M[i, j]) / s
    q[k] = (M[k, i] + M[i, k]) / s
    q[3] = (M[k, j] - M[j, k]) / s
    return q


def to_viewer(fm, bones, human=None, in_place=True, rest=None):
    """The viewer's motion format: (F, len(bones), 4) world deltas from the rest pose and (F, 3) hips offset / hips
    height, for the VRM 1.0 bone names in `bones`.  Bones the file lacks stay still (identity).
    rest: (world rotations, positions) to measure from, instead of the file's rest pose (e.g. a T-pose take)."""
    human = human or humanoid(fm.bones)[0]
    for b in ("hips", "head", "leftUpperArm", "rightUpperArm"):
        if b not in human:
            raise ValueError("bone names not recognized (the %s is missing). Supported: Mixamo, Unreal-style "
                             "(Quaternius ...) and VRoid humanoid skeletons" % b)
    rw, rp = rest if rest is not None else (fm.rest_world, fm.rest_pos)
    M = _axis_basis(type("R", (), {"rest_pos": rp})(), human)
    C = _mat_quat(M)
    F = fm.frames
    D = np.zeros((F, len(bones), 4), np.float32)
    D[..., 3] = 1.0
    for k, b in enumerate(bones):
        i = human.get(b)
        if i is None:
            continue
        d = vmul(fm.world[:, i], qconj(rw[i]))                 # world delta in the file's axes
        D[:, k] = vmul(vmul(C, d), qconj(C))                    # the same turn in the viewer's axes
    h = human["hips"]
    pos = fm.pos[:, h] @ M.T
    rpos = rp[h] @ M.T
    hip_h = abs(rpos[1]) or 1.0                                 # the floor is y = 0, as in the bundled motions
    d = pos - rpos
    if in_place:
        d[:, 0] = d[:, 2] = 0.0
    return D, (d / hip_h).astype(np.float32)
