"""sample_3d.py - walk your avatar around in Pyxel 3 (3D).  Exported by VRM RETRO VIEWER.

    pip install pyxel numpy
    pyxel run sample_3d.py

Arrows: walk.  Hold X: run.  Z: punch.  SPACE: try every motion.  T: T-pose.
The avatar is loaded by vrm_figure.py (in this folder) from model.tmx, motions.tmx and tex_*.png.
On Code & Magic: upload every file of this folder, with this one renamed to main.py.
"""
# SPDX-License-Identifier: MIT
import math

import pyxel
from pyxel.cube import Camera, Mat4, Node, Shading, Vec3

from vrm_figure import Figure

W, H = 256, 192
try:                                     # the folder of this file ("" where __file__ is not set)
    _f = __file__.replace("\\", "/")
    HERE = _f.rsplit("/", 1)[0] + "/" if "/" in _f else ""
except NameError:
    HERE = ""


class Ground(Node):
    """A grid on the floor, so you can see the avatar move."""

    def on_draw(self):
        for i in range(-10, 11):
            col = 5 if i % 5 else 6
            self.line(Vec3(i, 0, -10), Vec3(i, 0, 10), col)
            self.line(Vec3(-10, 0, i), Vec3(10, 0, i), col)


class App:
    def __init__(self):
        pyxel.init(W, H, title="VRM 3D SAMPLE", fps=30)
        self.stage = Node()
        cam = Camera()
        cam.fov = 35.0
        cam.near = 0.05
        cam.far = 60.0
        cam.clear_color = 1
        self.stage.camera = cam
        self.stage.add_child(Ground())
        self.fig = Figure(HERE)                                 # sets palette colours 16-255
        sh = Shading(list(pyxel.colors))
        sh.direction = Vec3(-0.4, -0.8, -0.5)
        self.stage.shading = sh
        self.stage.add_child(self.fig)
        self.x, self.z, self.angle = 0.0, 0.0, 0.0             # angle 0 = facing the camera (+Z)
        self.showcase = -1

    def update(self):
        fig = self.fig
        ids = fig.motion_ids()
        dx = (pyxel.btn(pyxel.KEY_RIGHT) - pyxel.btn(pyxel.KEY_LEFT))
        dz = (pyxel.btn(pyxel.KEY_DOWN) - pyxel.btn(pyxel.KEY_UP))
        busy = fig.motion == "punch" and not fig.finished()
        if pyxel.btnp(pyxel.KEY_SPACE):
            self.showcase = (self.showcase + 1) % len(ids)
            fig.play(ids[self.showcase])
        elif pyxel.btnp(pyxel.KEY_T):
            self.showcase = -2
            fig.play("tpose")
        elif pyxel.btnp(pyxel.KEY_Z) and "punch" in ids:
            self.showcase = -1
            fig.play("punch")
        elif (dx or dz) and not busy:
            self.showcase = -1
            run = pyxel.btn(pyxel.KEY_X)
            speed = 0.09 if run else 0.035
            n = math.hypot(dx, dz)
            self.x = max(-9.5, min(9.5, self.x + dx / n * speed))
            self.z = max(-9.5, min(9.5, self.z + dz / n * speed))
            self.angle = math.degrees(math.atan2(dx, dz))
            fig.play("run" if run else "walk", restart=False)
        elif self.showcase == -1 and not busy:
            fig.play("idle", restart=False)
        fig.transform = Mat4.from_translation(Vec3(self.x, 0.0, self.z)) * Mat4.from_euler(Vec3(0.0, self.angle, 0.0))
        fig.animate(1 / 30)

    def draw(self):
        pyxel.cls(1)
        h = self.fig.height
        tgt = Vec3(self.x, h * 0.5, self.z)
        self.stage.camera.transform = Mat4.look_at(Vec3(self.x, h * 1.6, self.z + h * 2.6), tgt, Vec3.UP)
        self.stage.draw(0, 0, W, H)
        pyxel.text(4, 4, "ARROWS WALK  X RUN  Z PUNCH  SPACE MOTIONS", 7)
        pyxel.text(4, H - 10, self.fig.motion.upper(), 6)


app = App()
pyxel.run(app.update, app.draw)
