"""Build the itch.io HTML5 upload: web/index.html + web/vrm_viewer.pyxapp, zipped as vrm_viewer_itch.zip.

    python tools/build_web.py
"""
# SPDX-License-Identifier: MIT
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def main():
    with tempfile.TemporaryDirectory() as tmp:
        app = Path(tmp) / "vrm_viewer"
        app.mkdir()
        for f in ("main.py", "vrm_io.py", "sample_sprites.py", "motions.npz", "vrm_figure.py", "sample_3d.py"):
            shutil.copy(ROOT / f, app / f)
        subprocess.run(["pyxel", "package", str(app), str(app / "main.py")], cwd=tmp, check=True)
        shutil.copy(Path(tmp) / "vrm_viewer.pyxapp", WEB / "vrm_viewer.pyxapp")
    out = ROOT / "vrm_viewer_itch.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in ("index.html", "vrm_viewer.pyxapp", "sample.vrm"):
            z.write(WEB / f, f)
    print(out, out.stat().st_size, "bytes")


if __name__ == "__main__":
    main()
