"""Make the bundled sample avatar smaller: shrink every texture (the viewer uses 256 px anyway), drop the facial
blend shapes (not used by the viewer) and re-pack the GLB.

    python tools/make_sample_vrm.py samples/CC0_Sendagaya_Shibu.vrm web/sample.vrm [max_px]

Only for avatars whose license allows modification and redistribution (the bundled one is CC0).
"""
# SPDX-License-Identifier: MIT
import io
import json
import struct
import sys

from PIL import Image


def read_glb(data):
    j_len = struct.unpack_from("<I", data, 12)[0]
    j = json.loads(data[20:20 + j_len])
    off = 20 + j_len
    b_len = struct.unpack_from("<I", data, off)[0]
    return j, data[off + 8:off + 8 + b_len]


def strip_morphs(j):
    """Drop the blend shapes (facial expressions): this viewer does not use them, and they are most of the file."""
    for m in j.get("meshes", []):
        m.pop("weights", None)
        for p in m["primitives"]:
            p.pop("targets", None)
            p.get("extras", {}).pop("targetNames", None)
        m.get("extras", {}).pop("targetNames", None)
    ext = j.get("extensions", {})
    for e in ext.get("VRMC_vrm", {}).get("expressions", {}).values():
        for x in e.values():
            if isinstance(x, dict):
                x.pop("morphTargetBinds", None)
    for g in ext.get("VRM", {}).get("blendShapeMaster", {}).get("blendShapeGroups", []):
        g["binds"] = []
    # keep only the accessors still in use, renumbered
    used = []
    for m in j.get("meshes", []):
        for p in m["primitives"]:
            used += list(p["attributes"].values()) + ([p["indices"]] if "indices" in p else [])
    used += [s["inverseBindMatrices"] for s in j.get("skins", []) if "inverseBindMatrices" in s]
    keep = sorted(set(used))
    remap = {a: k for k, a in enumerate(keep)}
    j["accessors"] = [j["accessors"][a] for a in keep]
    for m in j.get("meshes", []):
        for p in m["primitives"]:
            p["attributes"] = {k: remap[v] for k, v in p["attributes"].items()}
            if "indices" in p:
                p["indices"] = remap[p["indices"]]
    for s in j.get("skins", []):
        if "inverseBindMatrices" in s:
            s["inverseBindMatrices"] = remap[s["inverseBindMatrices"]]


def main(src, dst, max_px=512):
    j, binc = read_glb(open(src, "rb").read())
    strip_morphs(j)
    views = j["bufferViews"]
    new_data = {}
    for img in j.get("images", []):
        if "bufferView" not in img:
            continue
        bv = views[img["bufferView"]]
        raw = binc[bv.get("byteOffset", 0):bv.get("byteOffset", 0) + bv["byteLength"]]
        im = Image.open(io.BytesIO(raw))
        im.load()
        if max(im.size) > max_px:
            s = max_px / max(im.size)
            im = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS)
        b = io.BytesIO()
        im.save(b, "PNG", optimize=True)
        new_data[img["bufferView"]] = b.getvalue()
        img["mimeType"] = "image/png"
    # re-pack the buffer views still in use, 4-byte aligned
    live = sorted({a["bufferView"] for a in j["accessors"] if "bufferView" in a} |
                  {im["bufferView"] for im in j.get("images", []) if "bufferView" in im})
    vmap = {v: k for k, v in enumerate(live)}
    for a in j["accessors"]:
        if "bufferView" in a:
            a["bufferView"] = vmap[a["bufferView"]]
        if "sparse" in a:
            raise SystemExit("sparse accessors are not handled here")
    for im in j.get("images", []):
        if "bufferView" in im:
            im["bufferView"] = vmap[im["bufferView"]]
    new_data = {vmap[k]: v for k, v in new_data.items() if k in vmap}
    old_views, views = views, [views[v] for v in live]
    j["bufferViews"] = views
    out = bytearray()
    for i, bv in enumerate(views):
        raw = new_data.get(i)
        if raw is None:
            o = bv.get("byteOffset", 0)
            raw = binc[o:o + bv["byteLength"]]
        while len(out) % 4:
            out.append(0)
        bv["byteOffset"] = len(out)
        bv["byteLength"] = len(raw)
        bv["buffer"] = 0
        out += raw
    while len(out) % 4:
        out.append(0)
    j["buffers"] = [{"byteLength": len(out)}]
    js = json.dumps(j, separators=(",", ":")).encode()
    js += b" " * (-len(js) % 4)
    glb = struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(out))
    glb += struct.pack("<II", len(js), 0x4E4F534A) + js + struct.pack("<II", len(out), 0x004E4942) + bytes(out)
    open(dst, "wb").write(glb)
    print(dst, len(glb), "bytes")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 512)
