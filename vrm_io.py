"""vrm_io - read a VRM (0.x or 1.0) file into plain numpy data for Pyxel 3: meshes with skin weights, the node tree,
humanoid bone names, the license (meta) and the base-colour textures (palette-indexed).

Pure Python + numpy; Pillow is used to decode PNG / JPEG textures.  Works in desktop Python and in the browser (Pyodide).
"""
# SPDX-License-Identifier: MIT
import io
import json
import math
import struct

import numpy as np

COMP = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
NCOMP = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}
KEY = 255


# ====================================================================== GLB
def read_glb(data):
    if data[:4] != b"glTF":
        raise ValueError("not a VRM / GLB file")
    off, j, binc = 12, None, b""
    while off < len(data):
        n, kind = struct.unpack("<II", data[off:off + 8])
        chunk = data[off + 8:off + 8 + n]
        if kind == 0x4E4F534A:
            j = json.loads(chunk)
        elif kind == 0x004E4942:
            binc = chunk
        off += 8 + n
    return j, binc


def accessor(j, binc, i):
    a = j["accessors"][i]
    n = NCOMP[a["type"]]
    dt = np.dtype(COMP[a["componentType"]])
    out = np.zeros((a["count"], n), np.float32 if dt == np.float32 else dt)
    if "bufferView" in a:
        bv = j["bufferViews"][a["bufferView"]]
        base = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
        stride = bv.get("byteStride", 0)
        item = dt.itemsize * n
        if stride and stride != item:
            raw = np.frombuffer(binc, np.uint8, stride * (a["count"] - 1) + item, base)
            rows = np.lib.stride_tricks.as_strided(raw, (a["count"], item), (stride, 1))
            out = np.frombuffer(rows.copy().tobytes(), dt).reshape(a["count"], n)
        else:
            out = np.frombuffer(binc, dt, a["count"] * n, base).reshape(a["count"], n)
    if "sparse" in a:
        sp = a["sparse"]
        out = out.copy()
        ib = j["bufferViews"][sp["indices"]["bufferView"]]
        idx = np.frombuffer(binc, COMP[sp["indices"]["componentType"]], sp["count"],
                            ib.get("byteOffset", 0) + sp["indices"].get("byteOffset", 0))
        vb = j["bufferViews"][sp["values"]["bufferView"]]
        vals = np.frombuffer(binc, dt, sp["count"] * n, vb.get("byteOffset", 0) + sp["values"].get("byteOffset", 0))
        out[idx.astype(np.int64)] = vals.reshape(-1, n)
    if a.get("normalized") and dt != np.float32:
        out = out.astype(np.float32) / np.iinfo(dt).max
    return out


def trs_matrix(nd):
    if "matrix" in nd:
        return np.array(nd["matrix"], np.float64).reshape(4, 4).T
    t = np.array(nd.get("translation", (0, 0, 0)), np.float64)
    x, y, z, w = nd.get("rotation", (0, 0, 0, 1))
    s = np.array(nd.get("scale", (1, 1, 1)), np.float64)
    M = np.eye(4)
    M[:3, :3] = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                          [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                          [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]]) * s
    M[:3, 3] = t
    return M


# ====================================================================== license
def license_lines(j):
    """(version, title, author, lines[], warnings[]) from VRM 0.x `VRM.meta` or VRM 1.0 `VRMC_vrm.meta`."""
    ext = j.get("extensions", {})
    lines, warns = [], []
    if "VRMC_vrm" in ext:
        m = ext["VRMC_vrm"].get("meta", {})
        ver = "VRM 1.0"
        title = m.get("name", "?")
        author = ", ".join(m.get("authors", [])) or "?"
        lines.append("AVATAR USE: %s" % m.get("avatarPermission", "onlyAuthor"))
        lines.append("COMMERCIAL: %s" % m.get("commercialUsage", "personalNonProfit"))
        lines.append("CREDIT: %s" % m.get("creditNotation", "required"))
        lines.append("REDISTRIBUTION: %s" % ("allowed" if m.get("allowRedistribution") else "not allowed"))
        mod = m.get("modification", "prohibited")
        lines.append("MODIFICATION: %s" % mod)
        if mod == "prohibited":
            warns.append("MODIFICATION IS PROHIBITED")
        if not m.get("allowRedistribution"):
            warns.append("DO NOT REDISTRIBUTE THE EXPORT")
        if m.get("avatarPermission", "onlyAuthor") == "onlyAuthor":
            warns.append("ONLY THE AUTHOR MAY USE THIS AVATAR")
        if m.get("licenseUrl"):
            lines.append(m["licenseUrl"][:44])
    elif "VRM" in ext:
        m = ext["VRM"].get("meta", {})
        ver = "VRM 0.x"
        title = m.get("title", "?")
        author = m.get("author", "?")
        lic = m.get("licenseName", "Other")
        lines.append("AVATAR USE: %s" % m.get("allowedUserName", "OnlyAuthor"))
        lines.append("COMMERCIAL: %s" % m.get("commercialUssageName", "Disallow"))
        lines.append("LICENSE: %s" % lic)
        if m.get("otherLicenseUrl"):
            lines.append(m["otherLicenseUrl"][:44])
        if lic in ("Redistribution_Prohibited", "CC_BY_ND", "CC_BY_NC_ND"):
            warns.append("DO NOT REDISTRIBUTE THE EXPORT" if lic == "Redistribution_Prohibited" else "NO DERIVATIVES (ND)")
        if m.get("allowedUserName", "OnlyAuthor") == "OnlyAuthor":
            warns.append("ONLY THE AUTHOR MAY USE THIS AVATAR")
    else:
        ver, title, author = "glTF", "?", "?"
        warns.append("NO VRM META: CHECK THE LICENSE YOURSELF")
    return ver, str(title), str(author), lines, warns


# ====================================================================== humanoid
VRM1_FROM_0 = {}   # VRM 0.x and 1.0 share the bone names (hips, spine, leftUpperArm, ...)


def humanoid(j):
    ext = j.get("extensions", {})
    out = {}
    if "VRMC_vrm" in ext:
        for name, b in ext["VRMC_vrm"].get("humanoid", {}).get("humanBones", {}).items():
            out[name] = b["node"]
    elif "VRM" in ext:
        for b in ext["VRM"].get("humanoid", {}).get("humanBones", []):
            out[b["bone"]] = b["node"]
    return out


# ====================================================================== textures / palette
def decode_image(j, binc, idx, size):
    from PIL import Image
    im = j["images"][idx]
    bv = j["bufferViews"][im["bufferView"]]
    raw = binc[bv.get("byteOffset", 0):bv.get("byteOffset", 0) + bv["byteLength"]]
    img = Image.open(io.BytesIO(raw))
    img.draft("RGB", (size, size))                   # JPEG: decode at a smaller scale (fast)
    img = img.convert("RGBA")
    if max(img.size) > size:
        s = size / max(img.size)
        img = img.resize((max(1, round(img.width * s)), max(1, round(img.height * s))), Image.BILINEAR)
    return np.asarray(img, np.uint8)


def make_palette(images, n=239):
    """Median-cut palette from the opaque pixels of all textures (Pillow).  Returns (n, 3) uint8."""
    from PIL import Image
    pix = []
    for a in images:
        rgb = a[..., :3][a[..., 3] >= 128]
        if len(rgb) > 6000:
            rgb = rgb[np.linspace(0, len(rgb) - 1, 6000).astype(np.int64)]
        pix.append(rgb)
    pix = np.concatenate(pix) if pix else np.zeros((1, 3), np.uint8)
    side = int(math.ceil(math.sqrt(len(pix))))
    sheet = np.zeros((side * side, 3), np.uint8)
    sheet[:len(pix)] = pix
    sheet[len(pix):] = pix[0]
    q = Image.fromarray(sheet.reshape(side, side, 3)).quantize(n, method=Image.Quantize.MEDIANCUT)
    pal = np.array(q.getpalette()[:n * 3], np.uint8).reshape(-1, 3)
    if len(pal) < n:
        pal = np.concatenate([pal, np.repeat(pal[-1:], n - len(pal), 0)])
    return pal


class Lut:
    """Nearest palette entry for any RGB (32 levels per channel)."""

    def __init__(self, pal, base):
        q = np.arange(32, dtype=np.float32) * 8 + 4
        g = np.stack(np.meshgrid(q, q, q, indexing="ij"), -1).reshape(-1, 3)
        P = pal.astype(np.float32)
        best = np.zeros(len(g), np.int64)
        bd = np.full(len(g), 1e12, np.float32)
        for k in range(0, len(P), 32):                   # chunks keep memory small in the browser
            d = ((g[:, None, :] - P[None, k:k + 32]) ** 2).sum(-1)
            m = d.argmin(1)
            v = d[np.arange(len(g)), m]
            upd = v < bd
            best[upd] = m[upd] + k
            bd[upd] = v[upd]
        self.lut = (best + base).astype(np.uint8).reshape(32, 32, 32)

    def index(self, rgba):
        i = rgba[..., :3].astype(np.int32) >> 3
        out = self.lut[i[..., 0], i[..., 1], i[..., 2]]
        if rgba.shape[-1] == 4:
            out = np.where(rgba[..., 3] < 128, KEY, out)
        return out.astype(np.uint8)


# ====================================================================== the model
class VrmModel:
    """Everything the viewer needs, as numpy arrays.

    nodes: parent[], rest local TRS (t, q, s), names
    parts: per primitive dict(pos (n,3), uv (n,2), idx (m,), joints (n,4) global node ids, weights (n,4),
           ibm (n_skin_joints...) folded per vertex slot, tex (image index or None), alpha_cut)
    """

    def __init__(self, data, tex_size=256, progress=None):
        say = progress or (lambda s: None)
        say("READING")
        j, binc = read_glb(data)
        self.version, self.title, self.author, self.license, self.warnings = license_lines(j)
        self.human = humanoid(j)
        nodes = j.get("nodes", [])
        N = len(nodes)
        self.names = [nd.get("name", "node%d" % i) for i, nd in enumerate(nodes)]
        self.parent = np.full(N, -1, np.int64)
        for i, nd in enumerate(nodes):
            for c in nd.get("children", []):
                self.parent[c] = i
        self.rest_t = np.zeros((N, 3), np.float32)
        self.rest_q = np.tile(np.array([0, 0, 0, 1], np.float32), (N, 1))
        self.rest_s = np.ones((N, 3), np.float32)
        self.rest_m = np.zeros((N, 4, 4), np.float64)
        for i, nd in enumerate(nodes):
            if "matrix" in nd:
                M = trs_matrix(nd)
                self.rest_t[i] = M[:3, 3]
                sc = np.linalg.norm(M[:3, :3], axis=0)
                self.rest_s[i] = sc
                self.rest_q[i] = mat_to_quat(M[:3, :3] / sc)
            else:
                self.rest_t[i] = nd.get("translation", (0, 0, 0))
                self.rest_q[i] = nd.get("rotation", (0, 0, 0, 1))
                self.rest_s[i] = nd.get("scale", (1, 1, 1))
            self.rest_m[i] = trs_matrix(nd)
        order, seen = [], set()
        roots = [i for i in range(N) if self.parent[i] < 0]
        stack = list(reversed(roots))
        while stack:
            i = stack.pop()
            if i in seen:
                continue
            seen.add(i)
            order.append(i)
            stack.extend(reversed(nodes[i].get("children", [])))
        self.order = np.array(order, np.int64)
        self.rest_world = self.world(self.rest_m)
        # ---------------------------------------------------------------- meshes
        say("MESHES")
        mats = j.get("materials", [])
        self.parts = []
        used_tex = {}
        self.tris = 0
        for ni, nd in enumerate(nodes):
            if "mesh" not in nd:
                continue
            skin = j["skins"][nd["skin"]] if "skin" in nd else None
            if skin:
                sj = np.array(skin["joints"], np.int64)
                ibm = (accessor(j, binc, skin["inverseBindMatrices"]).reshape(-1, 4, 4).transpose(0, 2, 1)
                       if "inverseBindMatrices" in skin else np.tile(np.eye(4, dtype=np.float32), (len(sj), 1, 1)))
            for pr in j["meshes"][nd["mesh"]]["primitives"]:
                if pr.get("mode", 4) != 4 or "POSITION" not in pr["attributes"]:
                    continue
                at = pr["attributes"]
                pos = accessor(j, binc, at["POSITION"]).astype(np.float32)
                n = len(pos)
                uv = accessor(j, binc, at["TEXCOORD_0"]).astype(np.float32) if "TEXCOORD_0" in at else np.zeros((n, 2), np.float32)
                idx = (accessor(j, binc, pr["indices"]).reshape(-1).astype(np.int64) if "indices" in pr
                       else np.arange(n, dtype=np.int64))
                if skin and "JOINTS_0" in at:
                    jj = accessor(j, binc, at["JOINTS_0"]).astype(np.int64)
                    ww = accessor(j, binc, at["WEIGHTS_0"]).astype(np.float32)
                    ww = ww / np.maximum(ww.sum(1, keepdims=True), 1e-6)
                    ibms = ibm.astype(np.float32)
                    slot = jj
                    skin_nodes = sj
                else:                                      # rigid mesh: hangs off its own node
                    ww = np.zeros((n, 4), np.float32)
                    ww[:, 0] = 1
                    ibms = np.eye(4, dtype=np.float32)[None]
                    slot = np.zeros((n, 4), np.int64)
                    skin_nodes = np.array([ni], np.int64)
                # primitives of one mesh often share one big vertex buffer: keep only the vertices this one uses
                used, inv = np.unique(idx, return_inverse=True)
                pos, uv, slot, ww, idx = pos[used], uv[used], slot[used], ww[used], inv.reshape(-1).astype(np.int64)
                m = mats[pr["material"]] if "material" in pr and pr["material"] < len(mats) else {}
                pbr = m.get("pbrMetallicRoughness", {})
                ti = pbr.get("baseColorTexture", {}).get("index")
                img = j["textures"][ti].get("source") if ti is not None else None
                factor = pbr.get("baseColorFactor", [1, 1, 1, 1])
                key = (img, tuple(round(f, 3) for f in factor[:3]))
                used_tex.setdefault(key, len(used_tex))
                self.parts.append(dict(pos=pos, uv=uv, idx=idx, slot=slot, ww=ww, skin_nodes=skin_nodes,
                                       ibm=ibms, tex=used_tex[key], name=m.get("name", ""),
                                       alpha=m.get("alphaMode", "OPAQUE"), double=bool(m.get("doubleSided"))))
                self.tris += len(idx) // 3
        self.verts = sum(len(p["pos"]) for p in self.parts)
        # ---------------------------------------------------------------- textures
        say("TEXTURES")
        self.tex_keys = sorted(used_tex, key=used_tex.get)
        rgba = []
        for img, factor in self.tex_keys:
            if img is None:
                a = np.zeros((2, 2, 4), np.uint8)
                a[..., :3] = (np.array(factor) ** (1 / 2.2) * 255).clip(0, 255)
                a[..., 3] = 255
            else:
                try:
                    a = decode_image(j, binc, img, tex_size).copy()
                except Exception:
                    a = np.full((2, 2, 4), 200, np.uint8)
                if factor != (1.0, 1.0, 1.0):
                    a[..., :3] = (a[..., :3].astype(np.float32) * np.array(factor)).clip(0, 255).astype(np.uint8)
            rgba.append(a)
        self.rgba = rgba
        say("PALETTE")
        self.palette = make_palette(rgba)
        lut = Lut(self.palette, 16)
        self.tex_index = [lut.index(a) for a in rgba]
        # whether the textures are mostly see-through (for colour-keyed drawing)
        for p in self.parts:
            p["keyed"] = p["alpha"] != "OPAQUE" and bool((self.tex_index[p["tex"]] == KEY).any())
        # ---------------------------------------------------------------- facing
        # VRM 0.x faces -Z, VRM 1.0 faces +Z: turn 0.x by 180 degrees so the viewer can treat them alike
        self.face_yaw = 180.0 if self.version == "VRM 0.x" else 0.0
        lo = np.min([p["pos"].min(0) for p in self.parts], 0) if self.parts else np.zeros(3)
        hi = np.max([p["pos"].max(0) for p in self.parts], 0) if self.parts else np.ones(3)
        self.height = float(hi[1] - lo[1])
        say("DONE")

    # ------------------------------------------------------------------ pose
    def world(self, local):
        W = np.empty_like(local)
        for i in self.order:
            p = self.parent[i]
            W[i] = local[i] if p < 0 else W[p] @ local[i]
        return W

    def local_mats(self, q, t=None):
        """Local matrices from per-node quaternions (rest translation / scale unless t is given)."""
        t = self.rest_t if t is None else t
        x, y, z, w = q[:, 0], q[:, 1], q[:, 2], q[:, 3]
        M = np.zeros((len(q), 4, 4), np.float64)
        M[:, 0, 0] = 1 - 2 * (y * y + z * z)
        M[:, 0, 1] = 2 * (x * y - z * w)
        M[:, 0, 2] = 2 * (x * z + y * w)
        M[:, 1, 0] = 2 * (x * y + z * w)
        M[:, 1, 1] = 1 - 2 * (x * x + z * z)
        M[:, 1, 2] = 2 * (y * z - x * w)
        M[:, 2, 0] = 2 * (x * z - y * w)
        M[:, 2, 1] = 2 * (y * z + x * w)
        M[:, 2, 2] = 1 - 2 * (x * x + y * y)
        M[:, :3, :3] *= self.rest_s[:, None, :]
        M[:, :3, 3] = t
        M[:, 3, 3] = 1
        return M


def mat_to_quat(R):
    tr = R[0, 0] + R[1, 1] + R[2, 2]
    if tr > 0:
        s = math.sqrt(tr + 1.0) * 2
        return np.array([(R[2, 1] - R[1, 2]) / s, (R[0, 2] - R[2, 0]) / s, (R[1, 0] - R[0, 1]) / s, 0.25 * s])
    i = int(np.argmax([R[0, 0], R[1, 1], R[2, 2]]))
    if i == 0:
        s = math.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2]) * 2
        return np.array([0.25 * s, (R[0, 1] + R[1, 0]) / s, (R[0, 2] + R[2, 0]) / s, (R[2, 1] - R[1, 2]) / s])
    if i == 1:
        s = math.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2]) * 2
        return np.array([(R[0, 1] + R[1, 0]) / s, 0.25 * s, (R[1, 2] + R[2, 1]) / s, (R[0, 2] - R[2, 0]) / s])
    s = math.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1]) * 2
    return np.array([(R[0, 2] + R[2, 0]) / s, (R[1, 2] + R[2, 1]) / s, 0.25 * s, (R[1, 0] - R[0, 1]) / s])


def qmul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return np.array([aw * bx + ax * bw + ay * bz - az * by, aw * by - ax * bz + ay * bw + az * bx,
                     aw * bz + ax * by - ay * bx + az * bw, aw * bw - ax * bx - ay * by - az * bz])


def qaxis(axis, deg):
    a = np.asarray(axis, np.float64)
    a = a / np.linalg.norm(a)
    h = math.radians(deg) / 2
    return np.array([*(a * math.sin(h)), math.cos(h)])


def qconj(q):
    return np.array([-q[0], -q[1], -q[2], q[3]])
