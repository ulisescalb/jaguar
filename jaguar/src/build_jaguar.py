"""Genera la malla base del jaguar a partir de src/params.json.

Uso (desde la carpeta jaguar/):
    blender -b -P src/build_jaguar.py -- --version v01
Opciones:
    --params RUTA      params alternativo (por defecto src/params.json)
    --no-render        sólo construir, validar, medir y guardar el .blend
    --samples N        muestras de Cycles para los renders (por defecto 48)
    --export-glb       exporta además export/jaguar_base_<version>.glb

También funciona con el módulo oficial `bpy` de PyPI:
    python src/build_jaguar.py --version v01
"""
import argparse
import json
import math
import os
import shutil
import sys

import bpy
import bmesh
import numpy as np
from mathutils import Vector, Matrix

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SRC_DIR)
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import geom  # noqa: E402
from geom import (MeshData, section_ring, tube_faces, hole_loop, mirror_hole,  # noqa: E402
                  grid_cap, matched_angles, blended_angles, ellipse_ring,
                  catmull_rom, interp_profile, quad_sphere)

X = Vector((1, 0, 0))
Y = Vector((0, 1, 0))
Z = Vector((0, 0, 1))


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", required=True)
    ap.add_argument("--params", default=os.path.join(SRC_DIR, "params.json"))
    ap.add_argument("--no-render", action="store_true")
    ap.add_argument("--samples", type=int, default=48)
    ap.add_argument("--export-glb", action="store_true")
    ap.add_argument("--preview", action="store_true",
                    help="renders rápidos a media resolución en renders/_preview (sin .blend)")
    return ap.parse_args(argv)


def mirror_x(v):
    return Vector((-v.x, v.y, v.z))


# =========================================================== cuerpo + patas
def body_rings(md, P):
    n = P["body"]["ring_verts"]
    rings = []
    for st in P["body"]["stations"]:
        pts = section_ring(n, st["y"], st["zt"], st["zb"], st["w"], st.get("wz", 0.5),
                           st.get("pt", 2.0), st.get("pb", 2.0), st.get("tilt", 0.0))
        rings.append(md.add_verts(pts))
    return rings


def leg_ring_positions(loop_pts, spec):
    """Calcula los anillos (posiciones) de una pata izquierda emparejados con
    el bucle del agujero del tronco."""
    rs = spec["rings"]
    r1 = rs[0]
    c1 = Vector(((r1["xi"] + r1["xo"]) / 2, (r1["yf"] + r1["yb"]) / 2, r1["z"]))
    su, sv = (r1["xo"] - r1["xi"]) / 2, (r1["yb"] - r1["yf"]) / 2
    ang, sense = matched_angles(loop_pts, c1, X, Y, su, sv)
    blend = spec.get("blend", [0.5])
    out = []
    for k, r in enumerate(rs):
        beta = blend[k] if k < len(blend) else 1.0
        angs = blended_angles(ang, sense, beta)
        c = Vector(((r["xi"] + r["xo"]) / 2, (r["yf"] + r["yb"]) / 2, r["z"]))
        pts = ellipse_ring(c, X, Y, (r["xo"] - r["xi"]) / 2, (r["yb"] - r["yf"]) / 2,
                           angs, r.get("p", 2.0))
        if r.get("tilt", 0.0):  # >0: borde trasero arriba
            rot = Matrix.Rotation(math.radians(r["tilt"]), 3, 'X')
            pts = [c + rot @ (p - c) for p in pts]
        if r.get("roll", 0.0):  # >0: borde externo arriba (axila más baja)
            rot = Matrix.Rotation(math.radians(-r["roll"]), 3, 'Y')
            pts = [c + rot @ (p - c) for p in pts]
        out.append(pts)
    # índice de esquina para la tapa de la planta: lo más cerca de una diagonal
    last = blended_angles(ang, sense, 1.0)
    best, c0 = 9e9, 0
    for j in range(4):
        a = last[j]
        d = min(abs(math.remainder(a - (math.pi / 4 + k * math.pi / 2), 2 * math.pi)) for k in range(4))
        if d < best:
            best, c0 = d, j
    return out, c0


def attach_leg(md, loop, ring_pts, c0, spec, name, paw_name):
    prev = loop
    leg_idx = []
    paw_from = spec.get("paw_from_ring", len(ring_pts) - 3)
    paw_idx = []
    for k, pts in enumerate(ring_pts):
        idx = md.add_verts(pts)
        md.bridge(prev, idx)
        prev = idx
        leg_idx += idx
        if k >= paw_from:
            paw_idx += idx
    m = len(prev)
    a = m // 4
    G, _ = grid_cap(md, prev, a, m // 2 - a, c0=c0, flatten_z=spec.get("sole_z", 0.0))
    cap_idx = [G[i][j] for i in range(1, a) for j in range(1, m // 2 - a)]
    md.group(name, leg_idx + cap_idx)
    md.group(paw_name, paw_idx + cap_idx)
    md.group("sole_" + name.split("_")[1], cap_idx)


def build_tail(md, loop, P):
    T = P["tail"]
    loop_pts = [md.verts[i] for i in loop]
    base = sum(loop_pts, Vector()) / len(loop_pts)
    ctrl = [base + Vector((0.0, dy, dz)) for dy, dz in T["path"]]
    nr = T["rings"]
    # reescala la trayectoria para que su longitud de arco sea la objetivo
    _, raw_len = catmull_rom(ctrl, 200)
    scale = T["length"] / raw_len
    ctrl = [base + (c - base) * scale for c in ctrl]
    r_tip = interp_profile(T["radius"], 1.0)
    dense, total = catmull_rom(ctrl, 400)
    # anillos hasta (longitud - casquete de la punta)
    usable = total - r_tip * 0.75
    samples = []
    acc = [0.0]
    for i in range(1, len(dense)):
        acc.append(acc[-1] + (dense[i] - dense[i - 1]).length)

    def at(s):
        for i in range(1, len(acc)):
            if acc[i] >= s:
                t = (s - acc[i - 1]) / max(1e-9, acc[i] - acc[i - 1])
                p = dense[i - 1].lerp(dense[i], t)
                tg = (dense[i] - dense[i - 1]).normalized()
                return p, tg
        return dense[-1], (dense[-1] - dense[-2]).normalized()

    for k in range(1, nr + 1):
        s = usable * k / nr
        samples.append((s / total,) + at(s))
    # marco: U = X (lateral), V perpendicular en el plano YZ
    _, p1, t1 = samples[0]
    v1 = t1.cross(X).normalized()
    ang, sense = matched_angles(loop_pts, p1, X, v1)
    blend = T.get("blend", [0.5])
    prev = loop
    tail_idx = []
    for k, (frac, p, tg) in enumerate(samples):
        beta = blend[k] if k < len(blend) else 1.0
        angs = blended_angles(ang, sense, beta)
        v = tg.cross(X).normalized()
        u = v.cross(tg).normalized()
        r = interp_profile(T["radius"], frac)
        pts = ellipse_ring(p, u, v, r, r, angs, 2.0)
        idx = md.add_verts(pts)
        md.bridge(prev, idx)
        prev = idx
        tail_idx += idx
    m = len(prev)
    a = m // 4
    G, _ = grid_cap(md, prev, a, m // 2 - a, c0=0, dome=samples[-1][2] * (r_tip * 0.95),
                    dome_power=0.6)
    cap_idx = [G[i][j] for i in range(1, a) for j in range(1, m // 2 - a)]
    md.group("tail", tail_idx + cap_idx)
    md.group("tail_tip", cap_idx)
    md.group("tail_base", loop)
    centerline = [base] + [p for _, p, _ in samples] + [samples[-1][1] + samples[-1][2] * r_tip]
    return centerline


def build_body(P):
    md = MeshData("Jaguar_Body")
    B = P["body"]
    n = B["ring_verts"]
    rings = body_rings(md, P)
    holes = []
    leg_loops = {}
    for key, tag in (("front", "F"), ("hind", "H")):
        h = P["legs"][key]["hole"]
        s0, la, r0, lr = h["station"], h["along"], h["ring"], h["around"]
        holes.append((s0, la, r0, lr))
        holes.append((s0, la, mirror_hole(n, r0, lr), lr))
        leg_loops[tag + "L"] = hole_loop(rings, s0, la, r0, lr, mirror=False)
        leg_loops[tag + "R"] = hole_loop(rings, s0, la, r0, lr, mirror=True)
    tube_faces(md, rings, holes)
    torso_idx = [i for r in rings for i in r]

    a = n // 4
    c0 = (n - a // 2) % n
    # tapa del cuello (queda dentro de la cabeza)
    Gn, _ = grid_cap(md, rings[0], a, a, c0=c0, dome=-Y * B["neck_cap_dome"])
    # tapa de la grupa con agujero para la cola
    th = B["tail_hole"]
    Gr, tail_loop = grid_cap(md, rings[-1], a, a, c0=c0, dome=Y * B["rump_cap_dome"],
                             hole=(th["i0"], th["ha"], th["j0"], th["hb"]))
    for G in (Gn, Gr):
        torso_idx += [G[i][j] for i in range(1, a) for j in range(1, a) if G[i][j] is not None]
    md.group("torso", torso_idx)
    # musculatura superficial (escápulas, punta del hombro, cadera, glúteos)
    md.apply_bumps(B.get("bumps", []), only=set(torso_idx))
    md.group("neck", [i for r in rings[:4] for i in r] +
             [Gn[i][j] for i in range(1, a) for j in range(1, a)])

    for key, tag in (("front", "F"), ("hind", "H")):
        spec = P["legs"][key]
        loopL = leg_loops[tag + "L"]
        ring_pts, c0l = leg_ring_positions([md.verts[i] for i in loopL], spec)
        attach_leg(md, loopL, ring_pts, c0l, spec, "leg_%sL" % tag, "paw_%sL" % tag)
        ring_pts_r = [[mirror_x(p) for p in r] for r in ring_pts]
        attach_leg(md, leg_loops[tag + "R"], ring_pts_r, c0l, spec, "leg_%sR" % tag, "paw_%sR" % tag)
        # bucle de raíz de la extremidad: hombro (F) / cadera (H)
        md.group("loop_shoulder" if tag == "F" else "loop_hip", loopL + leg_loops[tag + "R"])

    centerline = build_tail(md, tail_loop, P)
    return md, centerline


# ===================================================================== cabeza
def head_matrix(P):
    H = P["head"]
    return Matrix.Translation(Vector(H["pivot"])) @ Matrix.Rotation(math.radians(H["pitch_deg"]), 4, 'X')


def build_eye_socket(md, loop, R, E, A, U, V, eye, slant):
    rot = Matrix.Rotation(math.radians(slant), 3, A)
    U2, V2 = rot @ U, rot @ V
    ox, oy = eye["open_x"], eye["open_y"]
    loop_pts = [md.verts[i] for i in loop]
    ang, sense = matched_angles(loop_pts, E, U2, V2, ox, oy)
    prev = loop
    rings = []
    for k, (rho, h) in enumerate(eye["socket_rings"]):
        beta = 0.5 if k == 0 else 1.0
        angs = blended_angles(ang, sense, beta)
        pts = [E + U2 * (rho * R * ox * math.cos(t)) + V2 * (rho * R * oy * math.sin(t)) + A * (h * R)
               for t in angs]
        idx = md.add_verts(pts)
        md.bridge(prev, idx)
        prev = idx
        rings.append(idx)
    m = len(prev)
    a = 2 if m % 4 == 2 else m // 4
    G, _ = grid_cap(md, prev, a, m // 2 - a, c0=0, dome=-A * (eye["socket_cap_dome"] * R))
    return rings


def build_head(P):
    H = P["head"]
    n = H["ring_verts"]
    md = MeshData("Jaguar_Head")
    rings = []
    for st in H["stations"]:
        pts = section_ring(n, st["y"], st["zt"], st["zb"], st["w"], st.get("wz", 0.5),
                           st.get("pt", 2.0), st.get("pb", 2.0), st.get("tilt", 0.0),
                           drape=st.get("drape", 0.0))
        rings.append(md.add_verts(pts))
    eh = H["eye_hole"]
    s0, la, r0, lr = eh["station"], eh["along"], eh["ring"], eh["around"]
    tube_faces(md, rings, [(s0, la, r0, lr), (s0, la, mirror_hole(n, r0, lr), lr)])
    a = n // 4
    c0 = (n - a // 2) % n
    grid_cap(md, rings[0], a, a, c0=c0, dome=Y * H["back_cap_dome"])
    Gf, _ = grid_cap(md, rings[-1], a, a, c0=c0, dome=-Y * H["nose_cap_dome"])
    md.group("nose_tip", [Gf[a // 2][a // 2]])
    md.group("occiput", [rings[H["occiput_station"]][0]])
    # rasgos faciales (almohadillas de bigotes, pómulos, cejas) antes de los ojos
    md.apply_bumps(H.get("bumps", []))

    # --- cuencas de los ojos con bucles de párpado
    eye = H["eye"]
    R = eye["radius"]
    loopL = hole_loop(rings, s0, la, r0, lr)
    pts = [md.verts[i] for i in loopL]
    Es = sum(pts, Vector()) / len(pts)
    st_mid = H["stations"][s0 + la // 2]
    zc = st_mid["zb"] + st_mid.get("wz", 0.5) * (st_mid["zt"] - st_mid["zb"])
    nrm = Vector((Es.x, 0.0, Es.z - zc)).normalized()
    if "gaze_yaw_deg" in eye:  # dirección de la mirada explícita (local)
        gy, gp = math.radians(eye["gaze_yaw_deg"]), math.radians(eye.get("gaze_pitch_deg", 0.0))
        A = Vector((math.sin(gy) * math.cos(gp), -math.cos(gy) * math.cos(gp), math.sin(gp)))
    else:
        fb = eye["forward_bias"]
        A = (nrm * (1 - fb) + (-Y) * fb).normalized()
    E = Es - nrm * (eye["inset"] * R)
    U = A.cross(Z).normalized()
    if U.x < 0:  # que U apunte hacia afuera/atrás de forma coherente
        U = -U
    V = U.cross(A).normalized()
    if V.z < 0:
        V = -V
    ringsL = build_eye_socket(md, loopL, R, E, A, U, V, eye, eye.get("slant_deg", 0.0))
    # ojo derecho: espejo exacto
    loopR = hole_loop(rings, s0, la, r0, lr, mirror=True)
    prev = loopR
    ringsR = []
    for rl in ringsL:
        idx = md.add_verts([mirror_x(md.verts[i]) for i in rl])
        md.bridge(prev, idx)
        prev = idx
        ringsR.append(idx)
    m = len(prev)
    a2 = 2 if m % 4 == 2 else m // 4
    grid_cap(md, prev, a2, m // 2 - a2, c0=0, dome=-mirror_x(A) * (eye["socket_cap_dome"] * R))
    md.group("eyelid_L", [i for r in ringsL[:3] for i in r] + loopL)
    md.group("eyelid_R", [i for r in ringsR[:3] for i in r] + loopR)
    eyes = {"L": E, "R": mirror_x(E), "A": A}
    return md, eyes


def build_jaw(P):
    J = P["jaw"]
    n = J["ring_verts"]
    md = MeshData("Jaguar_LowerJaw")
    rings = []
    for st in J["stations"]:
        pts = section_ring(n, st["y"], st["zt"], st["zb"], st["w"], st.get("wz", 0.5),
                           st.get("pt", 2.0), st.get("pb", 2.0), st.get("tilt", 0.0))
        rings.append(md.add_verts(pts))
    tube_faces(md, rings)
    # rejilla simétrica: lado superior/inferior con a (par) aristas
    a = 4 if n == 20 else n // 4
    b = n // 2 - a
    c0 = (n - a // 2) % n
    grid_cap(md, rings[0], a, b, c0=c0, dome=Y * J["back_cap_dome"])
    Gc, _ = grid_cap(md, rings[-1], a, b, c0=c0, dome=-Y * J["chin_cap_dome"])
    md.group("chin", [Gc[a // 2][b // 2]])
    md.group("lip_lower", [r[0] for r in rings])
    hinge = Vector(J["hinge"])
    m = (Matrix.Translation(hinge) @ Matrix.Rotation(math.radians(J["open_deg"]), 4, 'X')
         @ Matrix.Translation(-hinge))
    md.transform(m)
    return md


def build_ear(P, side):
    E = P["head"]["ear"]
    verts, faces = quad_sphere(E["res"])
    W, Hh, T = E["width"], E["height"], E["thickness"]
    out = []
    for s in verts:
        sx, sy, sz = s
        x = sx * W / 2 * (1 - E["top_taper"] * max(0.0, sz))
        z = sz * Hh / 2
        y = sy * T / 2
        if sy < 0:  # cara frontal (mira a -Y): ahuecar en forma de concha
            f = max(0.0, 1 - (sx / 0.8) ** 2 - ((sz - 0.15) / 0.85) ** 2)
            y = min(y + E["cup"] * f, abs(sy) * T / 2 - E["min_thickness"])
        out.append(Vector((x, y, z)))
    rot = (Matrix.Rotation(math.radians(E["yaw_deg"]), 3, 'Z')
           @ Matrix.Rotation(math.radians(E["roll_deg"]), 3, 'Y')
           @ Matrix.Rotation(math.radians(-E["pitch_deg"]), 3, 'X'))
    pos = Vector(E["pos"])
    out = [pos + rot @ v for v in out]
    md = MeshData("Jaguar_Ear" + side)
    if side == "R":
        out = [mirror_x(v) for v in out]
    md.verts = out
    md.faces = list(faces)
    return md


def build_eye(P, side, center):
    R = P["head"]["eye"]["radius"]
    verts, faces = quad_sphere(6)
    md = MeshData("Jaguar_Eye" + side)
    md.verts = [center + v * R for v in verts]
    md.faces = list(faces)
    return md


# ======================================================= conversión a Blender
def to_object(md, coll):
    me = bpy.data.meshes.new(md.name)
    me.from_pydata([tuple(v) for v in md.verts], [], md.faces)
    me.validate(clean_customdata=False)
    me.update()
    obj = bpy.data.objects.new(md.name, me)
    coll.objects.link(obj)
    for gname, d in sorted(md.groups.items()):
        vg = obj.vertex_groups.new(name=gname)
        by_w = {}
        for i, w in d.items():
            by_w.setdefault(round(w, 4), []).append(i)
        for w, idx in by_w.items():
            vg.add(idx, w, 'REPLACE')
    bm = bmesh.new()
    bm.from_mesh(me)
    # vértices interiores de los agujeros (injertos) quedan sin caras: fuera
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context='VERTS')
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    return obj


def apply_subsurf(obj, levels):
    if levels <= 0:
        return
    mod = obj.modifiers.new("Subsurf", 'SUBSURF')
    mod.levels = levels
    mod.render_levels = levels
    mod.subdivision_type = 'CATMULL_CLARK'
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    new_me = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=True, depsgraph=dg)
    obj.modifiers.remove(mod)
    old = obj.data
    new_me.name = old.name
    obj.data = new_me
    bpy.data.meshes.remove(old)


def shade_smooth(obj):
    me = obj.data
    me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
    me.update()


def group_coords(obj, name, thr=0.5):
    vg = obj.vertex_groups.get(name)
    if vg is None:
        return []
    gi = vg.index
    out = []
    for v in obj.data.vertices:
        for g in v.groups:
            if g.group == gi and g.weight >= thr:
                out.append(v.co.copy())
                break
    return out


def recenter(objs, body):
    fl = group_coords(body, "paw_FL") + group_coords(body, "paw_FR")
    hl = group_coords(body, "paw_HL") + group_coords(body, "paw_HR")
    cf = sum(fl, Vector()) / len(fl)
    ch = sum(hl, Vector()) / len(hl)
    zmin = min(v.co.z for v in body.data.vertices)
    off = Vector((0.0, (cf.y + ch.y) / 2, zmin))
    m = Matrix.Translation(-off)
    for o in objs:
        o.data.transform(m)
        o.data.update()
    return off


def build_all(P):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0
    coll = bpy.data.collections.new("Jaguar")
    scene.collection.children.link(coll)

    body_md, centerline = build_body(P)
    head_md, eyes = build_head(P)
    jaw_md = build_jaw(P)
    ears = [build_ear(P, s) for s in ("L", "R")]
    eye_mds = [build_eye(P, "L", eyes["L"]), build_eye(P, "R", eyes["R"])]
    hm = head_matrix(P)
    for md in [head_md, jaw_md] + ears + eye_mds:
        md.transform(hm)

    objs = []
    lv = P.get("subdivision_levels", 1)
    for md in [body_md, head_md, jaw_md] + ears:
        o = to_object(md, coll)
        apply_subsurf(o, lv)
        objs.append(o)
    for md in eye_mds:
        objs.append(to_object(md, coll))
    for o in objs:
        shade_smooth(o)
    body = objs[0]
    off = recenter(objs, body)
    # metadatos útiles para etapas posteriores (rig) y para medir
    body["tail_centerline"] = [c for p in centerline for c in (p - off)]
    jaw = bpy.data.objects["Jaguar_LowerJaw"]
    hinge_w = hm @ Vector(P["jaw"]["hinge"]) - off
    jaw["jaw_hinge_world"] = list(hinge_w)
    jaw["jaw_hinge_axis"] = list((hm.to_3x3() @ X).normalized())
    head = bpy.data.objects["Jaguar_Head"]
    head["head_pivot_world"] = list(Vector(P["head"]["pivot"]) - off)
    for side in ("L", "R"):
        e = bpy.data.objects["Jaguar_Eye" + side]
        e["eye_center_world"] = list((hm @ eyes[side]) - off)
    return objs, off


def build_all_conform(P):
    """Etapa 2 (v07+): topología limpia colocada sobre la escultura SDF."""
    import conform
    import sdf as sdfmod
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0
    coll = bpy.data.collections.new("Jaguar")
    scene.collection.children.link(coll)
    M = sdfmod.JaguarSDF(P)
    body_md, centerline = conform.build_body(P, M)
    head_md, eyes = conform.build_head(P, M)
    jaw_md = conform.build_jaw(P, M)
    ears = [conform.build_ear(P, M, s) for s in ("L", "R")]
    R = P["sculpt"]["eye"]["radius"]
    eye_mds = []
    for side in ("L", "R"):
        verts, faces = quad_sphere(6)
        md = MeshData("Jaguar_Eye" + side)
        md.verts = [Vector(eyes[side][0]) + v * R for v in verts]
        md.faces = list(faces)
        eye_mds.append(md)
    # la malla limpia hace los párpados con sus propios bucles: se proyecta sobre
    # la cabeza SIN la resta de la cuenca (que sí está en la escultura)
    fields = {"Jaguar_Body": conform.Field(M, ("body",)),
              "Jaguar_Head": conform.Field(M, ("head",), keep=lambda p: not p.name.startswith("eye_socket")),
              "Jaguar_LowerJaw": conform.Field(M, ("jaw",)), "Jaguar_EarL": conform.Field(M, ("ear_L",)),
              "Jaguar_EarR": conform.Field(M, ("ear_R",))}
    objs = []
    lv = P.get("subdivision_levels", 1)
    it = P["conform"].get("relax_iters", 4)
    residual = {}
    for md in [body_md, head_md, jaw_md] + ears:
        o = to_object(md, coll)
        apply_subsurf(o, lv)
        if o.name.startswith("Jaguar_Ear"):
            # la concha ya sale del marco de su primitiva; proyectar una lámina
            # tan fina sobre la SDF la pliega, así que sólo se relaja
            objs.append(o)
            continue
        residual[o.name] = conform.project_relax(o, fields[o.name], iters=it,
                                                 skip_group="eye_inner" if o.name == "Jaguar_Head" else None)
        bm = bmesh.new()
        bm.from_mesh(o.data)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(o.data)
        bm.free()
        objs.append(o)
    print("Residuo de proyección (media, máx) m:", residual)
    for md in eye_mds:
        objs.append(to_object(md, coll))
    for o in objs:
        shade_smooth(o)
    body = objs[0]
    off = recenter(objs, body)
    body["tail_centerline"] = [c for p in centerline for c in (p - off)]
    B = M.sk.bones({})
    p0, Pj, Rj = B["jaw"]
    jaw = bpy.data.objects["Jaguar_LowerJaw"]
    jaw["jaw_hinge_world"] = list(Vector(p0) - off)
    jaw["jaw_hinge_axis"] = list(Vector(M.sk.head_R @ np.array([1.0, 0, 0])).normalized())
    head = bpy.data.objects["Jaguar_Head"]
    head["head_pivot_world"] = list(Vector(M.sk.head_origin) - off)
    for side in ("L", "R"):
        bpy.data.objects["Jaguar_Eye" + side]["eye_center_world"] = list(Vector(eyes[side][0]) - off)
    for o in objs:
        o["projection_residual_m"] = residual.get(o.name, (0.0, 0.0))[1]
    return objs, off, M


def main():
    args = parse_args()
    with open(args.params, "r", encoding="utf-8") as f:
        P = json.load(f)
    M = None
    if "conform" in P:
        objs, off, M = build_all_conform(P)
    else:
        objs, off = build_all(P)

    import measure
    report = measure.full_report(P, objs)
    if args.preview:
        args.version = "_preview"
    vdir = os.path.join(ROOT_DIR, "renders", args.version)
    os.makedirs(vdir, exist_ok=True)
    dst = os.path.join(vdir, "params_used.json")
    if os.path.abspath(args.params) != os.path.abspath(dst):
        shutil.copyfile(args.params, dst)
    if M is not None:
        import skeleton as skmod
        import silhouette as sil
        exp_dir = os.path.join(ROOT_DIR, "export")
        os.makedirs(exp_dir, exist_ok=True)
        skmod.export_landmarks(M.sk, os.path.join(exp_dir, "landmarks.json"), offset=np.array(off),
                               poses={k: v for k, v in P["poses"].items() if not k.startswith("_")})
        report["extra"].update(measure.sdf_extra(P, M))
        try:
            report["iou"] = sil.evaluate_posed_mesh(P, M, objs, np.array(off), os.path.join(vdir, "iou"),
                                                    args.version)
        except ImportError as e:  # Blender sin OpenCV: el IoU se calcula desde el venv
            print("IoU omitido (falta OpenCV en este Python):", e)
    measure.write_report(report, vdir, args.version)
    print(measure.format_report(report))

    if args.preview:
        import render_views
        render_views.render_all(args.version, samples=12, report=report, targets=P["targets"],
                                preview=True)
        return

    blend_dir = os.path.join(ROOT_DIR, "blend")
    os.makedirs(blend_dir, exist_ok=True)
    blend_path = os.path.join(blend_dir, "jaguar_%s.blend" % args.version)
    bpy.ops.wm.save_as_mainfile(filepath=blend_path, compress=True)
    print("Guardado:", blend_path)

    if args.export_glb:
        exp_dir = os.path.join(ROOT_DIR, "export")
        os.makedirs(exp_dir, exist_ok=True)
        glb = os.path.join(exp_dir, "jaguar_base_%s.glb" % args.version)
        bpy.ops.export_scene.gltf(filepath=glb, export_format='GLB', use_selection=False,
                                  export_apply=True)
        print("GLB:", glb)

    if not args.no_render:
        import render_views
        # cámaras/luces se añaden después de guardar: el .blend queda limpio
        render_views.render_all(args.version, samples=args.samples, report=report,
                                 targets=P["targets"])


if __name__ == "__main__":
    main()
