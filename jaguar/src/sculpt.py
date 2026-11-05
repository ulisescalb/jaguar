"""Escultura de alta resolución: marching cubes de la SDF por componente.

Requiere scikit-image (venv). Resoluciones de params.json["sculpt"]["res"]:
≤ 8 mm en el cuerpo y ≤ 3 mm en cabeza, mandíbula y orejas.

Funciones:
- surfaces(model, pose): {componente: (verts, faces)}
- union_volume(model): volumen real de la unión (sin contar solapes) en m³
- to_blender(meshes, prefix): crea objetos de Blender (requiere bpy)
"""
import numpy as np

import sdf as sdfmod


def surface(M, comp, h, pose=None, B=None):
    from skimage.measure import marching_cubes
    lo, hi = M.bounds(pose, comps=(comp,), pad=2 * h + 0.01)
    shape = np.ceil((hi - lo) / h).astype(int) + 1
    F, _ = M.eval_grid(lo, h, shape, comps=(comp,), pose=pose, B=B)
    d = F[comp].astype(np.float32)
    # cerrar por el suelo: nada por debajo de z = 0
    if lo[2] < 0:
        kz = int(np.ceil(-lo[2] / h))
        d[:, :, :kz] = np.maximum(d[:, :, :kz], 0.001)
    v, f, _, _ = marching_cubes(d, 0.0, spacing=(h, h, h), gradient_direction="ascent")
    return v + lo, f


def surfaces(M, pose=None, res=None):
    res = res or M.P["sculpt"]["res"]
    B = M.sk.bones(pose)
    out = {}
    for comp in sdfmod.COMPONENTS:
        h = res["body"] if comp == "body" else res["head"]
        out[comp] = surface(M, comp, h, pose, B)
    return out


def union_volume(M, h=0.005, pose=None):
    """Volumen de la unión de todos los componentes (los solapes cuentan una
    vez). Se integra la ocupación (d < 0) en una rejilla común."""
    lo, hi = M.bounds(pose)
    shape = np.ceil((hi - lo) / h).astype(int) + 1
    # por bloques en Y para no gastar memoria
    total = 0.0
    ny = shape[1]
    step = max(8, ny // 8)
    B = M.sk.bones(pose)
    for j0 in range(0, ny, step):
        j1 = min(ny, j0 + step)
        o = lo + np.array([0, j0 * h, 0])
        F, _ = M.eval_grid(o, h, (shape[0], j1 - j0, shape[2]), B=B)
        occ = np.zeros((shape[0], j1 - j0, shape[2]), bool)
        for d in F.values():
            occ |= d < 0
        total += occ.sum() * h ** 3
    return total


def to_blender(meshes, prefix="Sculpt_", coll=None):
    import bpy
    objs = []
    for comp, (v, f) in meshes.items():
        me = bpy.data.meshes.new(prefix + comp)
        me.vertices.add(len(v))
        me.vertices.foreach_set("co", np.ascontiguousarray(v, np.float32).ravel())
        me.loops.add(len(f) * 3)
        me.loops.foreach_set("vertex_index", np.ascontiguousarray(f, np.int32).ravel())
        me.polygons.add(len(f))
        me.polygons.foreach_set("loop_start", np.arange(0, len(f) * 3, 3, dtype=np.int32))
        me.polygons.foreach_set("loop_total", np.full(len(f), 3, np.int32))
        me.update(calc_edges=True)
        me.validate()
        me.polygons.foreach_set("use_smooth", np.ones(len(f), bool))
        ob = bpy.data.objects.new(prefix + comp, me)
        (coll or bpy.context.scene.collection).objects.link(ob)
        objs.append(ob)
    return objs
