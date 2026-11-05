"""Métrica de silueta: proyección rápida de una malla (o de la escultura SDF) a
una máscara binaria, alineada con las fotos de referencia, IoU y superposición.

No usa Cycles: rasteriza triángulos con OpenCV (fillPoly) sobre la rejilla de
píxeles de la foto (reducida a la mitad para ir rápido).

Alineación:
- Lateral (ortográfica): la foto se refleja para que la cabeza quede a la
  izquierda como en nuestra vista lateral (+Y a la derecha). La escala sale de
  igualar la distancia horizontal nariz–base de la cola de la malla con la de la
  foto; la línea del suelo (z = 0) se hace coincidir con la de la foto.
- Frontal (perspectiva): la foto es una toma de cerca con perspectiva marcada.
  Se ajusta una cámara estenopeica (distancia, altura, punto de mira, focal y
  desplazamiento lateral) maximizando el IoU, con los mismos límites para todas
  las versiones, de modo que «antes» y «después» se comparan igual.

CLI (venv con bpy):
    python src/silhouette.py --blend blend/jaguar_v06.blend --out renders/v06/iou
"""
import argparse
import json
import math
import os
import sys

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF = os.path.join(ROOT, "reference")

# Puntos medidos a mano sobre las fotos originales (px, ver iteration_log.md)
REF_META = {
    "side": {
        "mask": "masks/side_mask.png", "photo": "photo_side_walk.jpg",
        "nose": [1835, 505], "tail_base": [490, 350], "ground_y": 1000,
        "mirror": True, "tail_base_uncert_px": 15,
    },
    "front": {
        "mask": "masks/front_mask.png", "photo": "photo_front_walk.jpg",
        "ground_y": 1258,
    },
}
SCALE = 0.5  # resolución de trabajo respecto a la foto


def load_ref(view, scale=SCALE):
    meta = dict(REF_META[view])
    m = cv2.imread(os.path.join(REF, meta["mask"]), 0)
    if meta.get("mirror"):
        m = m[:, ::-1]
    h, w = m.shape
    m = cv2.resize(m, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA) > 127
    meta["mask_arr"] = m
    meta["scale"] = scale
    W = w
    for k in ("nose", "tail_base"):
        if k in meta:
            x, y = meta[k]
            if meta.get("mirror"):
                x = W - x
            meta[k + "_px"] = (x * scale, y * scale)
    meta["ground_px"] = meta["ground_y"] * scale
    meta["shape"] = m.shape
    return meta


def raster(P2, tris, shape):
    """Rellena los triángulos proyectados (P2: (n,2) px) en una máscara."""
    img = np.zeros(shape, np.uint8)
    if len(tris) == 0:
        return img.astype(bool)
    pts = np.round(P2[tris] * 4).astype(np.int32)  # 2 bits de subpíxel
    # fillPoly con muchos polígonos usa la regla par-impar (los solapes se
    # anulan): hay que rellenar cada triángulo por separado
    fill = cv2.fillConvexPoly
    for t in pts:
        fill(img, t, 1, cv2.LINE_8, 2)
    return img.astype(bool)


def project_side(V, ref, nose_y, tail_y):
    """Ortográfica lateral: (Y, Z) → px de la foto reflejada."""
    nx, ny = ref["nose_px"]
    tx, _ = ref["tail_base_px"]
    s = (tx - nx) / (tail_y - nose_y)  # px por metro
    u = nx + (V[:, 1] - nose_y) * s
    v = ref["ground_px"] - V[:, 2] * s
    return np.stack([u, v], 1), s


def project_persp(V, cam, shape):
    """Cámara estenopeica mirando hacia +Y (desde delante del animal).

    cam: dict(dist, height, aim_z, aim_y, f, dx) en metros / px (f en px de la
    imagen de trabajo)."""
    h, w = shape
    C = np.array([cam["dx"], cam["aim_y"] - cam["dist"], cam["height"]])
    T = np.array([0.0, cam["aim_y"], cam["aim_z"]])
    fwd = T - C
    fwd /= np.linalg.norm(fwd)
    right = np.cross(fwd, [0.0, 0.0, 1.0])
    right /= np.linalg.norm(right)
    up = np.cross(right, fwd)
    d = V - C
    zc = d @ fwd
    zc = np.maximum(zc, 1e-3)
    u = w / 2 + cam["f"] * (d @ right) / zc
    v = h / 2 + cam.get("cy", 0.0) - cam["f"] * (d @ up) / zc
    return np.stack([u, v], 1)


def iou(a, b):
    inter = np.logical_and(a, b).sum()
    uni = np.logical_or(a, b).sum()
    return float(inter) / max(1, float(uni))


def overlay(model, refm, path, title=None):
    """Blanco = fondo; gris = coincide; rojo = sobra (modelo sin foto);
    azul = falta (foto sin modelo)."""
    h, w = refm.shape
    img = np.full((h, w, 3), 255, np.uint8)
    both = model & refm
    img[both] = (170, 170, 170)
    img[model & ~refm] = (40, 40, 230)     # BGR rojo
    img[~model & refm] = (230, 120, 30)    # BGR azul
    if title:
        cv2.putText(img, title, (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
    cv2.imwrite(path, img)


# ------------------------------------------------------------------ frontal
FRONT_CAM_BOUNDS = {  # límites físicos razonables para la toma frontal
    "dist": (1.5, 8.0), "height": (0.15, 1.2), "aim_z": (0.2, 0.7),
    "aim_y": (-0.6, 0.2), "f": (300.0, 6000.0), "dx": (-0.3, 0.3), "cy": (-200.0, 200.0),
}
FRONT_CAM0 = {"dist": 3.0, "height": 0.55, "aim_z": 0.45, "aim_y": -0.3, "f": 1500.0,
              "dx": 0.0, "cy": 0.0}


def fit_front_camera(V, tris, ref, cam0=None, iters=220, seed=1):
    import cma
    keys = list(FRONT_CAM_BOUNDS)
    lo = np.array([FRONT_CAM_BOUNDS[k][0] for k in keys])
    hi = np.array([FRONT_CAM_BOUNDS[k][1] for k in keys])
    c0 = cam0 or FRONT_CAM0
    x0 = np.array([(c0[k] - lo[i]) / (hi[i] - lo[i]) for i, k in enumerate(keys)])
    refm = ref["mask_arr"]

    def cam_of(x):
        x = np.clip(x, 0, 1)
        return {k: lo[i] + x[i] * (hi[i] - lo[i]) for i, k in enumerate(keys)}

    def loss(x):
        m = raster(project_persp(V, cam_of(x), refm.shape), tris, refm.shape)
        return 1.0 - iou(m, refm)

    es = cma.CMAEvolutionStrategy(x0, 0.15, {"bounds": [0, 1], "maxfevals": iters, "verbose": -9,
                                              "seed": seed})
    es.optimize(loss)
    cam = cam_of(es.result.xbest)
    return cam, 1.0 - es.result.fbest


# ------------------------------------------------------------- desde bpy
def mesh_arrays(objs):
    """Vértices y triángulos (mundo) de una lista de objetos de Blender."""
    import bpy
    Vs, Ts, off = [], [], 0
    dg = bpy.context.evaluated_depsgraph_get()
    for o in objs:
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        me.calc_loop_triangles()
        n = len(me.vertices)
        V = np.empty(n * 3, np.float64)
        me.vertices.foreach_get("co", V)
        V = V.reshape(-1, 3) @ np.array(o.matrix_world)[:3, :3].T + np.array(o.matrix_world)[:3, 3]
        T = np.empty(len(me.loop_triangles) * 3, np.int64)
        me.loop_triangles.foreach_get("vertices", T)
        Vs.append(V)
        Ts.append(T.reshape(-1, 3) + off)
        off += n
        ev.to_mesh_clear()
    return np.concatenate(Vs), np.concatenate(Ts)


def blend_landmarks(objs):
    """Nariz (punto más adelantado) y base dorsal de la cola de la malla v0x."""
    import bpy
    body = bpy.data.objects["Jaguar_Body"]
    gi = body.vertex_groups["tail_base"].index
    tb = [v.co for v in body.data.vertices for g in v.groups if g.group == gi and g.weight > 0.99]
    tail = max(tb, key=lambda p: p.z)
    nose_y = min(v.co.y for o in objs for v in o.data.vertices)
    return nose_y, tail.y


def evaluate_mesh(V, T, nose_y, tail_y, out_dir, label, front_cam=None):
    os.makedirs(out_dir, exist_ok=True)
    res = {}
    ref = load_ref("side")
    P2, s = project_side(V, ref, nose_y, tail_y)
    m = raster(P2, T, ref["shape"])
    res["side_iou"] = iou(m, ref["mask_arr"])
    res["side_px_per_m"] = s / ref["scale"]
    overlay(m, ref["mask_arr"], os.path.join(out_dir, "iou_side.png"),
            "%s lateral IoU %.3f" % (label, res["side_iou"]))
    reff = load_ref("front")
    cam, _ = fit_front_camera(V, T, reff, front_cam)
    mf = raster(project_persp(V, cam, reff["shape"]), T, reff["shape"])
    res["front_iou"] = iou(mf, reff["mask_arr"])
    res["front_cam"] = cam
    overlay(mf, reff["mask_arr"], os.path.join(out_dir, "iou_front.png"),
            "%s frontal IoU %.3f" % (label, res["front_iou"]))
    with open(os.path.join(out_dir, "iou.json"), "w") as f:
        json.dump(res, f, indent=2)
    return res


# --------------------------------------- malla limpia posada (skinning rígido)
def skin_pose(V, comp_of_obj, M, pose, sigma=0.012):
    """Posa vértices (marco de diseño) con pesos suaves por hueso: cada hueso
    pesa según la distancia de sus primitivas al vértice."""
    B = M.sk.bones(pose)
    B0 = M.sk.bones({})
    if comp_of_obj != "body":
        bone = "jaw" if comp_of_obj == "jaw" else "head"
        p0, P, R = B[bone]
        return P + (V - p0) @ R.T
    import sdf as sdfmod
    bones = sorted({pr.bone for pr in M.prims if pr.comp == "body" and pr.op == "add"})
    D = np.full((len(V), len(bones)), 1.0)
    for j, b in enumerate(bones):
        for pr in M.prims:
            if pr.comp != "body" or pr.op != "add" or pr.bone != b:
                continue
            lo, hi = M.posed_aabb(pr, B0)
            lo, hi = lo - 0.05, hi + 0.05
            sel = np.nonzero(np.all((V >= lo) & (V <= hi), 1))[0]
            if len(sel):
                D[sel, j] = np.minimum(D[sel, j], pr.sdf(V[sel]))
    dmin = D.min(1, keepdims=True)
    W = np.exp(-np.maximum(D - dmin, 0) / sigma)
    W[D - dmin > 4 * sigma] = 0.0
    W /= W.sum(1, keepdims=True)
    out = np.zeros_like(V)
    for j, b in enumerate(bones):
        p0, P, R = B[b]
        out += W[:, j:j + 1] * (P + (V - p0) @ R.T)
    return out


def evaluate_posed_mesh(P, M, objs, off, out_dir, label):
    """IoU de la malla limpia final en las poses de las fotos."""
    import bpy  # noqa: F401
    os.makedirs(out_dir, exist_ok=True)
    comp = {"Jaguar_Body": "body", "Jaguar_LowerJaw": "jaw"}
    res = {}
    for view, pose in (("side", P["poses"]["side_photo"]), ("front", P["poses"]["front_photo"])):
        Vs, Ts, n0 = [], [], 0
        for o in objs:
            V, T = mesh_arrays([o])
            V = V + off  # al marco de diseño (el de la escultura)
            V = skin_pose(V, comp.get(o.name, "head"), M, pose)
            Vs.append(V)
            Ts.append(T + n0)
            n0 += len(V)
        V, T = np.concatenate(Vs), np.concatenate(Ts)
        ref = load_ref(view)
        if view == "side":
            tail_y = M.sk.posed_points(pose)["tail_base"][1]
            P2, _ = project_side(V, ref, V[:, 1].min(), tail_y)
        else:
            P2 = project_persp(V, P["fit"]["front_cam"], ref["shape"])
        m = raster(P2, T, ref["shape"])
        res[view + "_iou"] = iou(m, ref["mask_arr"])
        overlay(m, ref["mask_arr"], os.path.join(out_dir, "iou_%s.png" % view),
                "%s %s IoU %.3f" % (label, "lateral" if view == "side" else "frontal", res[view + "_iou"]))
    with open(os.path.join(out_dir, "iou.json"), "w") as f:
        json.dump(res, f, indent=2)
    print("IoU malla final:", res)
    return res


def main():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--blend", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--label", default="")
    a = ap.parse_args(argv)
    import bpy
    bpy.ops.wm.open_mainfile(filepath=a.blend)
    objs = [o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith("Jaguar_")]
    V, T = mesh_arrays(objs)
    nose_y, tail_y = blend_landmarks(objs)
    res = evaluate_mesh(V, T, nose_y, tail_y, a.out, a.label or os.path.basename(a.blend))
    print(json.dumps({k: v for k, v in res.items() if k != "front_cam"}))


if __name__ == "__main__":
    main()
