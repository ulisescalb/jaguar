"""Renders de revisión estilo arcilla del jaguar.

Se llama desde build_jaguar.py, o por separado sobre un .blend ya generado:
    blender -b blend/jaguar_v01.blend -P src/render_views.py -- --version v01

Vistas (1024 px de ancho): front / side / top (ortográficas), three_quarter
(perspectiva), head_closeup, silhouette_side (negro sobre blanco), más
side_guides (lateral con líneas de cotas objetivo) y contact_sheet.
"""
import json
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Vector

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SRC_DIR)

JAGUAR_OBJS = ("Jaguar_Body", "Jaguar_Head", "Jaguar_LowerJaw", "Jaguar_EarL", "Jaguar_EarR",
               "Jaguar_EyeL", "Jaguar_EyeR")

GUIDE_COLORS = {
    "withers_height": (1.0, 0.15, 0.15),
    "croup_height": (1.0, 0.55, 0.0),
    "chest_clearance": (0.2, 0.4, 1.0),
    "belly_clearance": (0.0, 0.85, 0.85),
    "hb": (0.1, 0.8, 0.1),
}


# ------------------------------------------------------------- dispositivo
def setup_device(scene):
    scene.render.engine = 'CYCLES'
    try:
        cprefs = bpy.context.preferences.addons['cycles'].preferences
    except (KeyError, AttributeError):
        scene.cycles.device = 'CPU'
        return 'CPU'
    for dtype in ('OPTIX', 'CUDA'):
        try:
            cprefs.compute_device_type = dtype
        except TypeError:
            continue
        try:
            cprefs.refresh_devices()
        except AttributeError:
            cprefs.get_devices()
        gpus = [d for d in cprefs.devices if d.type == dtype]
        if gpus:
            for d in cprefs.devices:
                d.use = (d.type == dtype)
            scene.cycles.device = 'GPU'
            return dtype
    cprefs.compute_device_type = 'NONE'
    scene.cycles.device = 'CPU'
    return 'CPU'


# --------------------------------------------------------------- escena
def clay_material(name, gray, rough=0.62):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (gray, gray, gray, 1.0)
    bsdf.inputs["Roughness"].default_value = rough
    for key in ("Specular IOR Level", "Specular"):
        if key in bsdf.inputs:
            bsdf.inputs[key].default_value = 0.25
            break
    return m


def black_material():
    m = bpy.data.materials.get("SilhouetteBlack") or bpy.data.materials.new("SilhouetteBlack")
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (0, 0, 0, 1)
    em.inputs["Strength"].default_value = 0.0
    nt.links.new(em.outputs[0], out.inputs[0])
    return m


def set_world(scene, color, strength=1.0):
    w = scene.world or bpy.data.worlds.new("World")
    scene.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (*color, 1.0)
    bg.inputs["Strength"].default_value = strength


def add_light(name, kind, loc, target, energy, size):
    ld = bpy.data.lights.new(name, kind)
    ld.energy = energy
    if kind == 'AREA':
        ld.size = size
    ob = bpy.data.objects.new(name, ld)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    return ob


def bbox(objs):
    pts = [o.matrix_world @ v.co for o in objs for v in o.data.vertices]
    mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return mn, mx


def make_camera(name, loc, rot=None, target=None, ortho=None, lens=50.0):
    cd = bpy.data.cameras.new(name)
    cd.clip_start = 0.01
    cd.clip_end = 100.0
    if ortho:
        cd.type = 'ORTHO'
        cd.ortho_scale = ortho
    else:
        cd.lens = lens
    ob = bpy.data.objects.new(name, cd)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = loc
    if rot is not None:
        ob.rotation_euler = rot
    else:
        ob.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    return ob


def render(scene, cam, path, w, h):
    scene.camera = cam
    scene.render.resolution_x = w
    scene.render.resolution_y = h
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


# ------------------------------------------------------------ post-proceso
def load_rgba(path):
    img = bpy.data.images.load(path, check_existing=False)
    w, h = img.size
    arr = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(arr)
    bpy.data.images.remove(img)
    return arr.reshape(h, w, 4)


def save_rgba(arr, path):
    h, w = arr.shape[:2]
    img = bpy.data.images.new(os.path.basename(path), w, h, alpha=True)
    img.pixels.foreach_set(np.ascontiguousarray(arr, dtype=np.float32).ravel())
    img.filepath_raw = path
    img.file_format = 'PNG'
    img.save()
    bpy.data.images.remove(img)


def draw_side_guides(src, dst, cam, w, h, targets, report):
    arr = load_rgba(src)
    ppm = w / cam.data.ortho_scale
    cy, cz = cam.location.y, cam.location.z

    def row(zv):
        return int(round(h / 2 + (zv - cz) * ppm))

    def col(yv):
        return int(round(w / 2 + (yv - cy) * ppm))

    def hline(zv, color, dashed=False):
        r = row(zv)
        for x in range(w):
            if dashed and (x // 8) % 2:
                continue
            for d in (0, 1):
                if 0 <= r + d < h:
                    arr[r + d, x, :3] = color

    def vline(yv, color):
        c = col(yv)
        for y in range(h):
            if (y // 8) % 2:
                continue
            for d in (0, 1):
                if 0 <= c + d < w:
                    arr[y, c + d, :3] = color

    for key in ("withers_height", "croup_height", "chest_clearance", "belly_clearance"):
        if key in targets:
            hline(targets[key], GUIDE_COLORS[key], dashed=(key != "withers_height"))
    hline(0.0, (1.0, 1.0, 1.0))
    if report:
        ny = report["extra"]["nose_tip_yz"][0]
        vline(ny, GUIDE_COLORS["hb"])
        vline(ny + targets["head_body_length"], GUIDE_COLORS["hb"])
    # regla de 10 cm en la esquina inferior izquierda
    for k in range(11):
        x0 = 20 + int(k * 0.1 * ppm)
        for y in range(10, 18 if k % 5 else 26):
            if x0 < w:
                arr[y, x0, :3] = (1, 1, 1)
    for x in range(20, 20 + int(1.0 * ppm)):
        arr[10, x, :3] = (1, 1, 1)
    save_rgba(arr, dst)


def contact_sheet(paths, dst, tile=512, cols=3):
    rows = (len(paths) + cols - 1) // cols
    sheet = np.full((rows * tile, cols * tile, 4), 0.12, dtype=np.float32)
    sheet[..., 3] = 1.0
    for k, p in enumerate(paths):
        a = load_rgba(p)
        h, w = a.shape[:2]
        f = max(1, int(math.ceil(max(h, w) / tile)))
        h2, w2 = h // f, w // f
        a = a[:h2 * f, :w2 * f].reshape(h2, f, w2, f, 4).mean(axis=(1, 3))
        r, c = rows - 1 - k // cols, k % cols  # filas de abajo arriba
        y0 = r * tile + (tile - h2) // 2
        x0 = c * tile + (tile - w2) // 2
        sheet[y0:y0 + h2, x0:x0 + w2] = a
    save_rgba(sheet, dst)


# ------------------------------------------------------------------ main
def render_all(version, samples=48, report=None, targets=None, preview=False):
    scene = bpy.context.scene
    device = setup_device(scene)
    print("Cycles device:", device)
    scene.cycles.samples = samples
    scene.cycles.use_adaptive_sampling = True
    try:
        import _cycles
        has_oidn = bool(getattr(_cycles, "with_openimagedenoise", True))
    except ImportError:
        has_oidn = True
    if has_oidn:
        scene.cycles.use_denoising = True
        scene.cycles.denoiser = 'OPENIMAGEDENOISE'
    elif device == 'OPTIX':
        scene.cycles.use_denoising = True
        scene.cycles.denoiser = 'OPTIX'
    else:  # build sin denoiser (p.ej. Blender de Ubuntu): más muestras
        scene.cycles.use_denoising = False
        scene.cycles.samples = samples * 4
        print("Aviso: Cycles sin OpenImageDenoise; se usan", samples * 4, "muestras sin denoise")
    scene.render.film_transparent = False
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    try:
        scene.view_settings.view_transform = 'AgX'
    except TypeError:
        scene.view_settings.view_transform = 'Filmic'

    if targets is None:
        with open(os.path.join(SRC_DIR, "params.json"), encoding="utf-8") as f:
            targets = json.load(f)["targets"]
    objs = [bpy.data.objects[n] for n in JAGUAR_OBJS if n in bpy.data.objects]
    clay = clay_material("Clay", 0.50)
    clay_eye = clay_material("ClayEye", 0.12, rough=0.25)
    for o in objs:
        o.data.materials.clear()
        o.data.materials.append(clay_eye if "Eye" in o.name else clay)

    mn, mx = bbox(objs)
    ctr = (mn + mx) / 2
    size = mx - mn
    # suelo neutro
    bpy.ops.mesh.primitive_plane_add(size=20.0, location=(0, 0, 0))
    ground = bpy.context.active_object
    ground.name = "RenderGround"
    ground.data.materials.append(clay_material("Ground", 0.22, rough=0.9))
    set_world(scene, (0.16, 0.16, 0.17), 0.6)
    add_light("Key", 'AREA', ctr + Vector((2.4, -2.6, 2.6)), ctr, 300, 1.6)
    add_light("Fill", 'AREA', ctr + Vector((-3.0, -1.4, 1.2)), ctr, 90, 2.5)
    add_light("Rim", 'AREA', ctr + Vector((-0.6, 3.2, 2.4)), ctr, 260, 1.2)

    out = os.path.join(ROOT_DIR, "renders", version)
    os.makedirs(out, exist_ok=True)
    W, HS = 1024, 576
    far = 6.0
    pad = 1.10
    side_scale = max(size.y * pad, size.z * pad * W / HS)
    cams = {
        "front": (make_camera("CamFront", (ctr.x, mn.y - far, ctr.z), rot=(math.pi / 2, 0, 0),
                              ortho=max(size.x, size.z) * 1.25), W, W),
        "side": (make_camera("CamSide", (mx.x + far, ctr.y, ctr.z), rot=(math.pi / 2, 0, math.pi / 2),
                             ortho=side_scale), W, HS),
        "top": (make_camera("CamTop", (ctr.x, ctr.y, mx.z + far), rot=(0, 0, math.pi / 2),
                            ortho=max(size.y * pad, size.x * pad * W / HS)), W, HS),
    }
    d34 = Vector((0.85, -1.0, 0.55)).normalized()
    rad = size.length / 2
    dist = rad / math.tan(math.radians(39.6 / 2)) * 0.82
    cams["three_quarter"] = (make_camera("Cam34", ctr + d34 * dist, target=ctr, lens=50.0), W, W)
    head = bpy.data.objects["Jaguar_Head"]
    hmn, hmx = bbox([head, bpy.data.objects["Jaguar_LowerJaw"]])
    hc = (hmn + hmx) / 2
    dh = Vector((0.75, -1.0, 0.30)).normalized()
    hrad = (hmx - hmn).length / 2
    hdist = hrad / math.tan(math.atan(18.0 / 85.0)) * 1.15
    cams["head_closeup"] = (make_camera("CamHead", hc + dh * hdist, target=hc, lens=85.0), W, W)

    paths = {}
    names = ("side", "front", "top", "three_quarter", "head_closeup")
    if preview:  # iteración rápida: media resolución, sin silueta ni hojas
        for name in names:
            cam, w, h = cams[name]
            p = os.path.join(out, name + ".png")
            f = 1 if name == "side" else 2
            render(scene, cam, p, w // f, h // f)
        return
    for name in names:
        cam, w, h = cams[name]
        p = os.path.join(out, name + ".png")
        render(scene, cam, p, w, h)
        paths[name] = p

    # silueta: negro puro sobre blanco
    blk = black_material()
    saved = {o.name: list(o.data.materials) for o in objs}
    for o in objs:
        o.data.materials.clear()
        o.data.materials.append(blk)
    ground.hide_render = True
    set_world(scene, (1.0, 1.0, 1.0), 1.0)
    scene.view_settings.view_transform = 'Standard'
    scene.cycles.samples = 16
    cam, w, h = cams["side"]
    p = os.path.join(out, "silhouette_side.png")
    render(scene, cam, p, w, h)
    paths["silhouette_side"] = p
    for o in objs:
        o.data.materials.clear()
        for m in saved[o.name]:
            o.data.materials.append(m)

    draw_side_guides(paths["side"], os.path.join(out, "side_guides.png"), cams["side"][0], W, HS,
                     targets, report)
    contact_sheet([paths[k] for k in ("side", "front", "top", "three_quarter", "head_closeup",
                                      "silhouette_side")], os.path.join(out, "contact_sheet.png"))
    print("Renders en", out)
    return paths


if __name__ == "__main__":
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else argv[1:]
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", required=True)
    ap.add_argument("--samples", type=int, default=48)
    a = ap.parse_args(argv)
    rep = None
    mpath = os.path.join(ROOT_DIR, "renders", a.version, "measurements.json")
    if os.path.exists(mpath):
        with open(mpath, encoding="utf-8") as f:
            rep = json.load(f)
    render_all(a.version, samples=a.samples, report=rep)
