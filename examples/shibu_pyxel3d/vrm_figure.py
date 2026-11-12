"""vrm_figure.py - load a figure exported by VRM RETRO VIEWER ("Pyxel 3D" zip) and play its motions in Pyxel 3.

    import pyxel
    from pyxel.cube import Camera, Node
    from vrm_figure import Figure

    fig = Figure("figure/")          # the folder with model.tmx, motions.tmx and tex_*.png
    fig.play("walk")
    ...
    fig.animate(1 / 30)                # every frame: advance the motion and skin the mesh (numpy)
    stage.add_child(fig)               # a pyxel.cube Node: move it with fig.transform

Needs Pyxel 3 and numpy.  No os / sys / file writing, so it also follows the Code & Magic import rules.
The data files are .tmx (base64 text), because Code & Magic accepts .py / .png / .tmx / .glb / .ogg / .pyxres.
The figure uses palette colours 16-255 (its own colours, 255 = magenta colour key); 0-15 stay yours.

Motions: Quaternius Universal Animation Library 1 & 2 and KayKit Character Animations (Kay Lousberg), all CC0,
converted to VRM Animation by the open-vrma project.
Code: MIT (haruka_apps).  Runs on Pyxel 3 by Takashi Kitao (MIT License) and NumPy (BSD-3-Clause).  The avatar data keeps the license of the original VRM: see README.txt.
"""
# SPDX-License-Identifier: MIT
import base64
import io
import json

import numpy as np
import pyxel
from pyxel.cube import Mat4, Node, Primitive, Vec3

KEY = 255


def load_data(path):
    """Read model / motions data: a .tmx file (a 1x1 Tiled map whose "data" property holds the .npz as base64,
    so Code & Magic accepts it) or a plain .npz."""
    if path.endswith(".tmx"):
        with open(path, "r") as f:
            text = f.read()
        i = text.index('value="', text.index('<property name="data"')) + 7     # a Tiled map with the data in a property
        return np.load(io.BytesIO(base64.b64decode(text[i:text.index('"', i)])))
    return np.load(path)


def find_data(folder, name):
    """folder + name + ".tmx" if it is there, otherwise ".npz"."""
    for ext in (".tmx", ".npz"):
        try:
            open(folder + name + ext, "rb").close()
            return folder + name + ext
        except OSError:
            pass
    raise OSError("%s.tmx / %s.npz not found in '%s'" % (name, name, folder))


def qmul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return np.array([aw * bx + ax * bw + ay * bz - az * by, aw * by - ax * bz + ay * bw + az * bx,
                     aw * bz + ax * by - ay * bx + az * bw, aw * bw - ax * bx - ay * by - az * bz])


def qconj(q):
    return np.array([-q[0], -q[1], -q[2], q[3]])


def qrot(q, v):
    u = q[:3]
    return v + 2 * np.cross(u, np.cross(u, v) + q[3] * v)


class Motions:
    """Per humanoid bone and frame (30 fps): the world rotation delta from the T-pose, plus the hips offset."""

    def __init__(self, path):
        d = load_data(path)
        self.bones = [str(b) for b in d["bones"]]
        self.meta = json.loads(bytes(d["meta"]).decode())
        self.by_id = {m["id"]: m for m in self.meta}
        self.D = {m["id"]: d["d_" + m["id"]].astype(np.float32) for m in self.meta}
        self.Hp = {m["id"]: d["h_" + m["id"]].astype(np.float32) for m in self.meta}

    def frame(self, mid, t):
        D, Hp, m = self.D[mid], self.Hp[mid], self.by_id[mid]
        n = len(D)
        f = t * 30.0
        f = f % (n - 1) if m["loop"] else min(f, n - 1.001)
        i = int(f)
        u = f - i
        a, b = D[i], D[min(i + 1, n - 1)]
        b = np.where((np.sum(a * b, 1) < 0)[:, None], -b, b)
        q = a + (b - a) * u
        q /= np.linalg.norm(q, axis=1, keepdims=True)
        return q, Hp[i] + (Hp[min(i + 1, n - 1)] - Hp[i]) * u


class Figure(Node):
    """The exported avatar: one textured Primitive per material, skinned on the CPU with numpy."""

    def __init__(self, folder="", motions=None):
        super().__init__()
        folder = folder if folder == "" or folder.endswith("/") else folder + "/"
        d = load_data(find_data(folder, "model"))
        info = json.loads(bytes(d["info"]).decode())
        self.info = info
        self.height = info["height"]
        self.face_yaw = info["face_yaw"]
        self.flip = info["flip"]
        self.bone_parent = d["parent"]
        self.order = d["order"]
        self.rest_t = d["rest_t"].astype(np.float64)
        self.rest_q = d["rest_q"].astype(np.float64)
        self.rest_s = d["rest_s"].astype(np.float64)
        self.rest_wq = d["rest_wq"].astype(np.float64)
        self.bone_nodes = [int(n) for n in d["bone_nodes"]]
        self.node_bone = {n: k for k, n in enumerate(self.bone_nodes) if n >= 0}
        self.hips = info["hips"]
        self.hip_h = info["hip_h"]
        # palette: 16..254 = the avatar's colours, 255 = magenta (colour key); 0..15 are left alone
        pal = [int(c) for c in d["palette"]]
        cols = list(pyxel.colors)
        cols += [0] * (256 - len(cols))
        cols[16:16 + len(pal)] = pal
        cols[KEY] = 0xFF00FF
        pyxel.colors[:] = cols[:256]
        self.textures = [pyxel.Image.from_image(folder + "tex_%d.png" % k) for k in range(info["textures"])]
        self.parts, self.prims, self.p1 = [], [], []
        for k, pinfo in enumerate(info["parts"]):
            p = dict(pinfo)
            for key in ("pos", "uv", "idx", "slot", "ww", "skin_nodes", "ibm"):
                p[key] = d["p%d_%s" % (k, key)]
            p["pos"] = p["pos"].astype(np.float32)
            p["ww"] = p["ww"].astype(np.float32)
            p["slot"] = p["slot"].astype(np.int64)
            p["ibm"] = p["ibm"].astype(np.float32)
            pr = Primitive(Primitive.MODE_TRIANGLES, p["pos"].reshape(-1).tolist(), p["idx"].astype(np.int64).tolist(), [],
                           p["uv"].astype(np.float32).reshape(-1).tolist(),
                           cull=Primitive.CULL_NONE if p["double"] else Primitive.CULL_BACK)
            pr.compute_normals()
            self.parts.append(p)
            self.prims.append(pr)
            self.p1.append(np.hstack([p["pos"], np.ones((len(p["pos"]), 1), np.float32)]))
        self.draw_order = sorted(range(len(self.parts)), key=lambda i: {"OPAQUE": 0, "MASK": 1}.get(self.parts[i]["alpha"], 2))
        self.motions = motions or Motions(find_data(folder, "motions"))
        self.motion = "idle"
        self.t = 0.0
        self.q, self.tr = self.rest_q.copy(), self.rest_t.copy()
        self.animate(0.0)

    # ------------------------------------------------------------------ motions
    def play(self, mid, restart=True):
        """mid: an id from motion_ids() or "tpose"."""
        if mid != self.motion or restart:
            if mid == "tpose" or mid in self.motions.by_id:
                self.motion = mid
                self.t = 0.0

    def motion_ids(self):
        return [m["id"] for m in self.motions.meta]

    def finished(self):
        """True when a one-shot motion (jump, punch, death ...) has reached its last frame."""
        m = self.motions.by_id.get(self.motion)
        return m is not None and not m["loop"] and self.t >= m["seconds"]

    def animate(self, dt):
        self.t += dt
        self.pose()
        self.skin()

    def pose(self):
        q = self.rest_q.copy()
        tr = self.rest_t.copy()
        if self.motion != "tpose" and self.hips >= 0:
            D, hp = self.motions.frame(self.motion, self.t)
            if self.flip:                                     # VRM 0.x faces -Z
                D = D * np.array([-1.0, 1.0, -1.0, 1.0], np.float32)
                hp = hp * np.array([-1.0, 1.0, -1.0], np.float32)
            one = np.array([0.0, 0.0, 0.0, 1.0])
            Wq = {}
            for i in self.order:
                p = self.bone_parent[i]
                pw = Wq.get(p) if p >= 0 else None
                if pw is None:
                    pw = self.rest_wq[p] if p >= 0 else one
                k = self.node_bone.get(int(i))
                if k is not None:
                    w = qmul(D[k], self.rest_wq[i])
                    q[i] = qmul(qconj(pw), w)
                    Wq[i] = w
                else:
                    Wq[i] = qmul(pw, q[i])
            p = self.bone_parent[self.hips]
            pw = Wq.get(p, one) if p >= 0 else one
            tr[self.hips] = self.rest_t[self.hips] + qrot(qconj(pw), hp * self.hip_h)
        self.q, self.tr = q, tr

    # ------------------------------------------------------------------ skinning
    def skin(self):
        x, y, z, w = self.q[:, 0], self.q[:, 1], self.q[:, 2], self.q[:, 3]
        M = np.zeros((len(self.q), 4, 4), np.float64)
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
        M[:, :3, 3] = self.tr
        M[:, 3, 3] = 1
        W = np.empty_like(M)
        for i in self.order:
            p = self.bone_parent[i]
            W[i] = M[i] if p < 0 else W[p] @ M[i]
        W = W.astype(np.float32)
        for p, pr, p1 in zip(self.parts, self.prims, self.p1):
            mats = (W[p["skin_nodes"]] @ p["ibm"])[:, :3, :]
            pos = np.zeros((len(p1), 3), np.float32)
            for k in range(4):
                wk = p["ww"][:, k]
                if not wk.any():
                    continue
                pos += wk[:, None] * np.einsum("nij,nj->ni", mats[p["slot"][:, k]], p1)
            pr.positions[:] = pos.reshape(-1).tolist()
            pr.compute_normals()

    def on_draw(self):
        m = Mat4.from_euler(Vec3(0.0, float(self.face_yaw), 0.0))   # every figure faces +Z (toward the camera at +Z)
        for i in self.draw_order:
            p = self.parts[i]
            if p["keyed"]:
                self.prim(m, self.prims[i], self.textures[p["tex"]], colkey=KEY)
            else:
                self.prim(m, self.prims[i], self.textures[p["tex"]])
