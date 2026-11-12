# VRM RETRO VIEWER

[日本語](README.ja.md)

Open a VRM avatar (0.x or 1.0) and see it as a retro 3D figure in [Pyxel 3](https://github.com/kitao/pyxel). Play it with 231 CC0 motions, then export **2D sprite sheets** (PNG / GIF) or **3D data for Pyxel 3** as a zip.

- **Try it in your browser (free):** [haruka-apps-games.itch.io/vrm-retro-viewer](https://haruka-apps-games.itch.io/vrm-retro-viewer)
- **How it was made (Japanese):** [Qiita article](https://qiita.com/haruka_apps/items/29b897418b601cfacb6c)

![The tool in the browser: a tool bar on top, the avatar's license and the export settings on the right](docs/images/ui.png)

| Sprite sheet export (8 directions) | 3D export, running in Pyxel 3 |
|---|---|
| ![Run motion in 8 directions](docs/images/run_8dir.gif) | ![The exported 3D figure running on a grid](docs/images/pyxel3d_run.gif) |

Your file is never uploaded. Reading and converting happen inside your browser (or your own computer).

## Features

- Reads VRM 0.x and 1.0. Shows the avatar's license (meta) and warns in red when it forbids modification or redistribution
- 231 motions, all CC0 (Quaternius Universal Animation Library 1 & 2, KayKit Character Animations), with search and groups
- **Sprite export:** cell 32–128 px, 8 or 4 directions, 4–12 frames, any set of motions. Transparent background, one shared 256-colour palette, `sheet.json`, and a small Pyxel sample
- **3D export for Pyxel 3:** the converted avatar and all motions, plus `vrm_figure.py` to load and play them. Works on Code & Magic as well
- Screenshot (PNG) and GIF of the screen
- A sample avatar (Sendagaya Shibu, CC0) is included, so you can try it without your own VRM

![All motions at a glance (part of the list)](docs/images/shot4_motions.png)

## Run it yourself

You need Python 3 and Pyxel 3 (`pip install pyxel numpy pillow`).

**Desktop**

```bash
python main.py                 # then drop a .vrm file on the window
python main.py avatar.vrm      # or open a file directly
```

**Browser** (the same build as itch.io)

```bash
cd web
python -m http.server
```

Then open `http://localhost:8000`. The first start takes a while (Pyodide, NumPy and Pillow are loaded).

To rebuild `web/vrm_viewer.pyxapp` and the itch.io zip: `python tools/build_web.py`.

## Controls

| Input | Action |
|---|---|
| Drag / wheel | Turn / zoom |
| ← → / ↑ ↓ | Turn / zoom |
| SPACE | Next motion |
| T | T-pose |
| E | Export sprites with the default set (idle / walk / run / jump / punch / hit / death) |
| D | Export 3D for Pyxel |
| P / G | Screenshot / GIF |
| L | License overlay on / off (desktop) |
| F1 | Timings |

In the browser, the tool bar and the panel do the same and more.

## Sprite export (`<name>_sprites.zip`)

| File | Contents |
|---|---|
| `<name>_<motion>.png` | One sheet per motion. Rows = directions, columns = frames |
| `<name>_<motion>.gif` | Front view animation (2× size) |
| `<name>_all.png` | All motions stacked (only when it is 8192 px tall or less) |
| `sheet.json` | Cell size, direction order, per motion: file, frames, fps, loop, y in `_all.png`, and `palette` (the 256 colours of every PNG) |
| `README.txt` | The format, and the license of the source VRM |
| `pyxel_sample/` | `sample_sprites.py` and `HOW_TO_RUN.txt` (English and Japanese) |

- Direction order (8): down, down-left, left, up-left, up, up-right, right, down-right. (4): down, left, up, right
- Transparent pixels are stored as magenta (0xFF00FF) with alpha 0, so Pyxel can use magenta as the colour key and other tools see normal transparency
- In Pyxel, set `pyxel.colors` to `palette` from `sheet.json` first, then load the PNGs with `Image.from_image`. The colours then match exactly

## 3D export for Pyxel 3 (`<name>_pyxel3d.zip`)

| File | Contents |
|---|---|
| `model.tmx` | Mesh, bones, weights, palette and the source VRM's info (NumPy `.npz`, base64 inside a 1×1 Tiled map) |
| `tex_*.png` | Textures, drawn only with the palette colours |
| `motions.tmx` | The 231 motions (same format, about 2.8 MB) |
| `vrm_figure.py` | Loads and plays them. Uses only pyxel, numpy, json, base64 and io |
| `sample_3d.py` | Walk around on a floor (`pyxel run sample_3d.py`) |
| `README.txt` / `HOW_TO_RUN.txt` | How to use it, the source VRM's license, the disclaimer |

```python
from vrm_figure import Figure

fig = Figure("folder/")      # a pyxel.cube Node
stage.add_child(fig)
fig.play("walk")
fig.animate(1 / 30)          # every frame
```

- Why `.tmx`: Code & Magic accepts only `.py / .png / .tmx / .glb / .ogg / .pyxres`, and a `.tmx` has to be a real Tiled map. The data sits in the map's `data` property
- On Code & Magic, upload every file and rename `sample_3d.py` to `main.py`
- Palette entries 16–255 are used (255 = magenta colour key). Entries 0–15 stay as your game's colours
- Pyxel 3 does not skin GLB meshes, so `vrm_figure.py` skins on the CPU with NumPy

[`examples/shibu_pyxel3d/`](examples/shibu_pyxel3d/) is this export for the sample avatar, ready to run (the same files the author ran on Code & Magic).

## Repository layout

| Path | What it is |
|---|---|
| `main.py` | The viewer (Pyxel 3). CPU skinning, sprite and 3D export |
| `vrm_io.py` | Reads VRM 0.x / 1.0 (GLB) into NumPy data, builds the palette |
| `vrm_figure.py`, `sample_3d.py`, `sample_sprites.py` | Files that go into the exported zips |
| `motions.npz` | The 231 motions, baked by `tools/make_motions.py` |
| `web/` | `index.html` (tool bar and panel), `vrm_viewer.pyxapp`, `sample.vrm` |
| `tools/` | `build_web.py`, `make_motions.py`, `make_sample_vrm.py` |
| `examples/shibu_pyxel3d/` | A 3D export of the sample avatar |
| `docs/images/` | Screenshots |

The source motions for `tools/make_motions.py` are not in this repository. They come from [open-vrma](https://huggingface.co/datasets/Sanami/open-vrma) (only the CC0 clips: Quaternius and KayKit). See the top of `tools/make_motions.py`.

## Tested

- **Cloud Linux, Pyxel 3.0.1 (desktop):** VRM 1.0 (Sendagaya Shibu) and VRM 0.x; motions; sprite and 3D export; the exported 3D runs with `sample_3d.py` alone
- **Browser (the author, on a Mac, Pyxel 3.0.1):** tool bar, panel, sample, search, export and download
- **Code & Magic (the author):** the exported 3D data runs

Not tested: phones, Windows (the `HOW_TO_RUN.txt` steps), browsers other than the author's.

## License

The code is under the [MIT License](LICENSE) (© 2026 haruka_apps).

Assets in this repository have their own licenses:

- Motions in `motions.npz` and in the 3D export: Quaternius "Universal Animation Library" 1 & 2 and Kay Lousberg "KayKit Character Animations" (CC0 1.0), converted to .vrma by the open-vrma project
- `web/sample.vrm` and `examples/shibu_pyxel3d/`: Sendagaya Shibu, a CC0 sample model of VRoid (VRM data by coati). Made smaller for this tool with `tools/make_sample_vrm.py` (smaller textures, no facial blend shapes)

Avatars you load keep their own licenses. Following them is up to you. The tool shows each avatar's terms and writes them into every export.

## Disclaimer

This tool and the files it exports are provided "AS IS", without warranty of any kind. The author (haruka_apps) is not responsible for any damage or trouble caused by using them.

## Credits

- [Pyxel](https://github.com/kitao/pyxel) 3 by Takashi Kitao (MIT License)
- In the browser: Pyodide (MPL-2.0), NumPy (BSD-3-Clause), Pillow (MIT-CMU)
- Motions: [Quaternius](https://quaternius.com/) (CC0), Kay Lousberg / KayKit (CC0), via [open-vrma](https://huggingface.co/datasets/Sanami/open-vrma)
- Sample avatar: Sendagaya Shibu (VRoid, CC0)
