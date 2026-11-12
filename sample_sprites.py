"""Play with the sprite sheets exported from VRM RETRO VIEWER (Pyxel 3, 2D).

    pip install pyxel
    pyxel run pyxel_sample/sample_sprites.py      (or: python sample_sprites.py path/to/sheet.json)

Arrows: walk (8 directions).  Hold X: run.  Z: the first attack motion in the export (punch / sword / spell).
sheet.json describes the files: cell size, direction rows, per motion its file, frames, fps and loop flag, and the
256 colours every PNG is drawn in ("palette": set pyxel.colors to it, then load any PNG with Image.from_image).
"""
# SPDX-License-Identifier: MIT
import json
import math
import os
import sys

import pyxel

STEP = {(0, 1): "down", (-1, 1): "down_left", (-1, 0): "left", (-1, -1): "up_left",
        (0, -1): "up", (1, -1): "up_right", (1, 0): "right", (1, 1): "down_right"}
FALLBACK4 = {"down_left": "left", "up_left": "left", "up_right": "right", "down_right": "right"}


class App:
    def __init__(self, path):
        info = json.load(open(path))
        folder = os.path.dirname(os.path.abspath(path))
        pyxel.init(256, 192, title="SPRITE SAMPLE")
        self.cell, self.dirs, self.mot = info["cell"], info["directions"], info["motions"]
        if "palette" in info:
            # every PNG is drawn in the same 256 colours: set them, then each motion's PNG loads as it is
            pyxel.colors[:] = [int(c, 16) for c in info["palette"]]
            self.imgs = {}
            for mid in ("idle", "walk", "run", "punch", "sword", "spell"):     # only what this sample uses
                if mid in self.mot:
                    self.imgs[mid] = pyxel.Image.from_image(os.path.join(folder, self.mot[mid]["file"]))
                    self.mot[mid]["y"] = 0
        else:                                                                   # older sheets: one combined PNG
            img = pyxel.Image.from_image(os.path.join(folder, info["all_in_one"]), include_colors=True)
            self.imgs = {mid: img for mid in self.mot}
        self.mot = {mid: m for mid, m in self.mot.items() if mid in self.imgs}
        cols = list(pyxel.colors)
        self.key = cols.index(0xFF00FF)
        self.bg = self.nearest(cols, 70, 120, 80)
        self.white = self.nearest(cols, 255, 255, 255)
        self.attack = next((m for m in ("punch", "sword", "spell") if m in self.mot), None)
        self.x, self.y, self.face = 128.0 - self.cell / 2, 96.0 - self.cell / 2, "down"
        self.motion, self.t = "idle" if "idle" in self.mot else next(iter(self.mot)), 0.0
        pyxel.run(self.update, self.draw)

    @staticmethod
    def nearest(c, r, g, b):
        return min(range(len(c)), key=lambda i: abs((c[i] >> 16) - r) + abs((c[i] >> 8 & 255) - g) + abs((c[i] & 255) - b))

    def set(self, m):
        if m in self.mot and m != self.motion:
            self.motion, self.t = m, 0.0

    def update(self):
        self.t += 1 / 30
        busy = self.motion == self.attack and self.t < self.mot[self.motion]["frames"] / self.mot[self.motion]["fps"]
        if busy:
            return
        if self.attack and pyxel.btnp(pyxel.KEY_Z):
            self.set(self.attack)
            return
        dx = pyxel.btn(pyxel.KEY_RIGHT) - pyxel.btn(pyxel.KEY_LEFT)
        dy = pyxel.btn(pyxel.KEY_DOWN) - pyxel.btn(pyxel.KEY_UP)
        if dx or dy:
            self.face = STEP[(dx, dy)]
            run = pyxel.btn(pyxel.KEY_X) and "run" in self.mot
            self.set("run" if run else "walk")
            s = (2.4 if run else 1.2) / math.hypot(dx, dy)
            self.x = max(-self.cell / 4, min(pyxel.width - self.cell * 3 / 4, self.x + dx * s))
            self.y = max(-self.cell / 4, min(pyxel.height - self.cell, self.y + dy * s * 0.7))
        else:
            self.set("idle")

    def draw(self):
        pyxel.cls(self.bg)
        m = self.mot[self.motion]
        n = m["frames"]
        f = int(self.t * m["fps"])
        f = f % n if m["loop"] else min(f, n - 1)
        face = self.face if self.face in self.dirs else FALLBACK4.get(self.face, "down")
        row = self.dirs.index(face)
        c = self.cell
        pyxel.blt(self.x, self.y, self.imgs[self.motion], f * c, m["y"] + row * c, c, c, self.key)
        pyxel.text(4, 4, "ARROWS WALK  X RUN  Z ATTACK", self.white)


def find_sheet():
    """sheet.json given on the command line, or next to / one folder above this script."""
    here = os.path.dirname(os.path.abspath(__file__))
    for p in [a for a in sys.argv[1:] if a.lower().endswith(".json")] + [
            os.path.join(here, "sheet.json"), os.path.join(here, "..", "sheet.json"), "sheet.json"]:
        if os.path.exists(p):
            return p
    sys.exit("sheet.json not found: run  python sample_sprites.py path/to/sheet.json")


App(find_sheet())
