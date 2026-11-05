"""Medidas reales calculadas desde la malla final + validación topológica."""
import json
import math
import os

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def _gidx(obj, name):
    vg = obj.vertex_groups.get(name)
    return None if vg is None else vg.index


def coords(obj, name=None, thr=0.5, exclude=()):
    """Coordenadas de los vértices del grupo `name` (peso>=thr), excluyendo
    vértices con peso>=0.5 en los grupos `exclude`."""
    gi = _gidx(obj, name) if name else None
    ex = [_gidx(obj, e) for e in exclude]
    ex = [e for e in ex if e is not None]
    out = []
    for v in obj.data.vertices:
        w = {g.group: g.weight for g in v.groups}
        if gi is not None and w.get(gi, 0.0) < thr:
            continue
        if any(w.get(e, 0.0) >= 0.5 for e in ex):
            continue
        out.append(v.co.copy())
    return out


def extent(pts, axis):
    vals = [p[axis] for p in pts]
    return max(vals) - min(vals)


def centroid(pts):
    return sum(pts, Vector()) / len(pts)


LEGS = ("leg_FL", "leg_FR", "leg_HL", "leg_HR", "tail")


def tail_metrics(body):
    cl = body.get("tail_centerline")
    pts = [Vector(cl[i:i + 3]) for i in range(0, len(cl), 3)]
    # polilínea densa con longitud de arco acumulada
    dense, acc = [], []
    for a, b in zip(pts, pts[1:]):
        for k in range(10):
            dense.append(a.lerp(b, k / 10))
    dense.append(pts[-1])
    acc = [0.0]
    for i in range(1, len(dense)):
        acc.append(acc[-1] + (dense[i] - dense[i - 1]).length)
    tv = coords(body, "tail", 0.5)
    base = centroid(coords(body, "tail_base", 0.99))

    def param(p):
        best, bi = 9e9, 0
        for i, d in enumerate(dense):
            dd = (p - d).length_squared
            if dd < best:
                best, bi = dd, i
        return acc[bi]

    s_base = param(base)
    sp = [(param(p) - s_base, p) for p in tv]
    step = 0.025
    bins = {}
    for s, p in sp:
        bins.setdefault(int(s / step), []).append(p)
    cents = [base] + [centroid(bins[k]) for k in sorted(bins) if k > 0]
    tip = max(sp, key=lambda t: t[0])[1]
    poly = cents + [tip]
    length = sum((b - a).length for a, b in zip(poly, poly[1:]))
    # diámetro cerca de la base (5–9 cm a lo largo de la cola)
    near = [p for s, p in sp if 0.05 <= s <= 0.09] or [p for s, p in sp if 0.0 <= s <= 0.12]
    c = centroid(near)
    # el centroide del tramo; radio medio respecto al eje local
    far = [p for s, p in sp if 0.09 < s <= 0.14] or [p for s, p in sp if s > 0.09][:50]
    nearb = [p for s, p in sp if 0.0 <= s < 0.05] or [p for s, p in sp if s < 0.09][:50]
    t_dir = (centroid(far) - centroid(nearb)).normalized()
    radii = []
    for p in near:
        d = p - c
        d = d - t_dir * d.dot(t_dir)
        radii.append(d.length)
    diam = 2 * sum(radii) / len(radii)
    return length, diam, tip


def measurements(P, objs):
    body = bpy.data.objects["Jaguar_Body"]
    head = bpy.data.objects["Jaguar_Head"]
    torso = coords(body, "torso", 0.5, exclude=LEGS)
    nose = coords(head, "nose_tip", 0.99)[0]
    occ = coords(head, "occiput", 0.99)[0]
    tb = coords(body, "tail_base", 0.99)
    tb_top = max(tb, key=lambda p: p.z)
    pf = centroid(coords(body, "paw_FL") + coords(body, "paw_FR"))
    ph = centroid(coords(body, "paw_HL") + coords(body, "paw_HR"))

    withers = max(p.z for p in torso if p.y < 0.0)
    croup = max(p.z for p in torso if p.y > 0.15)
    chest = [p for p in torso if pf.y - 0.10 <= p.y <= pf.y + 0.22]
    chest_clear = min(p.z for p in chest)
    waist_y = ph.y - 0.28
    waist = [p for p in torso if abs(p.y - waist_y) <= 0.03 and abs(p.x) < 0.05]
    belly_clear = min(p.z for p in waist)
    # costillar: entre codos y rodillas (sin deltoides ni muslos, que en la v07
    # forman parte de la pared lateral de la malla)
    rib = [p for p in torso if pf.y + 0.05 <= p.y <= ph.y - 0.15] or [p for p in torso if p.y > pf.y - 0.15]
    torso_w = extent(rib, 0)
    pawF = coords(body, "paw_FL")
    pawH = coords(body, "paw_HL")
    fore = [p for p in coords(body, "leg_FL") if 0.175 <= p.z <= 0.195]
    tail_len, tail_diam, tail_tip = tail_metrics(body)
    hb = tb_top.y - nose.y
    head_len = (nose - occ).length
    head_pts = [v.co for v in head.data.vertices]

    m = {
        "head_body_length": hb,
        "withers_height": withers,
        "croup_height": croup,
        "tail_length": tail_len,
        "head_length": head_len,
        "head_width": extent(head_pts, 0),
        "chest_depth": withers - chest_clear,
        "chest_clearance": chest_clear,
        "belly_clearance": belly_clear,
        "torso_width": torso_w,
        "front_paw_width": extent(pawF, 0),
        "hind_paw_width": extent(pawH, 0),
        "forearm_depth": extent(fore, 1) if fore else 0.0,
        "tail_base_diameter": tail_diam,
    }
    # contorno dorsal (línea media) nariz→base de cola: equivale a medir con cinta
    # sobre el lomo, como en campo/museo
    mid = []
    for o in objs:
        if o.name in ("Jaguar_Body", "Jaguar_Head"):
            mid += [v.co.copy() for v in o.data.vertices
                    if abs(v.co.x) < 0.004 and v.normal.z > 0.25]
    bins = {}
    for p in mid:
        if nose.y <= p.y <= tb_top.y:
            k = int((p.y - nose.y) / 0.01)
            if k not in bins or p.z > bins[k].z:
                bins[k] = p
    prof = [nose] + [bins[k] for k in sorted(bins)] + [tb_top]
    contour = sum((b - a).length for a, b in zip(prof, prof[1:]))
    vol = 0.0
    for o in objs:
        if o.name in ("Jaguar_Body", "Jaguar_Head", "Jaguar_LowerJaw"):
            bm = bmesh.new()
            bm.from_mesh(o.data)
            vol += bm.calc_volume(signed=True)
            bm.free()
    extra = {
        "volume_m3": vol,
        "mass_est_kg": vol * 1040.0,
        "hb_dorsal_contour": contour,
        "head_pct_of_hb": 100.0 * head_len / hb,
        "tail_pct_of_hb": 100.0 * tail_len / hb,
        "wheelbase_paws": ph.y - pf.y,
        "nose_tip_yz": [round(nose.y, 4), round(nose.z, 4)],
        "tail_base_yz": [round(tb_top.y, 4), round(tb_top.z, 4)],
        "tail_tip_z": round(tail_tip.z, 4),
        "front_paw_center_y": round(pf.y, 4),
        "hind_paw_center_y": round(ph.y, 4),
        "overall_length_bbox": max(p.y for o in objs for p in [v.co for v in o.data.vertices])
        - min(p.y for o in objs for p in [v.co for v in o.data.vertices]),
        "waist_y": waist_y,
    }
    return m, extra


def topology(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    quads = sum(1 for f in bm.faces if len(f.verts) == 4)
    tris = sum(1 for f in bm.faces if len(f.verts) == 3)
    ngons = sum(1 for f in bm.faces if len(f.verts) > 4)
    nonman = sum(1 for e in bm.edges if not e.is_manifold)
    boundary = sum(1 for e in bm.edges if e.is_boundary)
    loose_v = sum(1 for v in bm.verts if not v.link_edges)
    loose_e = sum(1 for e in bm.edges if not e.link_faces)
    flipped = sum(1 for e in bm.edges if e.is_manifold and not e.is_contiguous)
    vol = bm.calc_volume(signed=True)
    # auto-intersecciones (pares de caras no adyacentes que se cruzan)
    tree = BVHTree.FromBMesh(bm)
    pairs = tree.overlap(tree)
    selfx = 0
    seen = set()
    for i, j in pairs:
        if i == j or (j, i) in seen:
            continue
        seen.add((i, j))
        vi = {v.index for v in bm.faces[i].verts}
        vj = {v.index for v in bm.faces[j].verts}
        if vi & vj:
            continue
        selfx += 1
    poles = sum(1 for v in bm.verts if len(v.link_edges) not in (4,) and v.link_edges)
    # calidad de quads: ángulos interiores y caras colapsadas
    angs = []
    collapsed = 0
    for f in bm.faces:
        if f.calc_area() < 1e-9:
            collapsed += 1
        vs = [v.co for v in f.verts]
        n = len(vs)
        for i in range(n):
            a = vs[i - 1] - vs[i]
            b = vs[(i + 1) % n] - vs[i]
            if a.length > 1e-12 and b.length > 1e-12:
                angs.append(math.degrees(a.angle(b)))
    angs = sorted(angs)
    bad = sum(1 for a in angs if a < 25 or a > 155)
    bm.free()
    return {
        "verts": len(obj.data.vertices), "faces": len(obj.data.polygons),
        "quads": quads, "tris": tris, "ngons": ngons, "non_manifold_edges": nonman,
        "boundary_edges": boundary, "loose_verts": loose_v, "loose_edges": loose_e,
        "inconsistent_normals": flipped, "signed_volume": vol,
        "outward_normals": vol > 0, "self_intersections": selfx, "poles": poles,
        "collapsed_faces": collapsed, "angle_min": angs[0] if angs else 0.0,
        "angle_max": angs[-1] if angs else 0.0, "angles_outside_25_155": bad,
        "angle_p01": angs[len(angs) // 100] if angs else 0.0,
        "angle_p99": angs[-len(angs) // 100 - 1] if angs else 0.0,
    }


def sdf_extra(P, M):
    """Volumen real de la unión de la escultura (sin sumar solapes) y masa."""
    import sculpt
    vol = sculpt.union_volume(M, h=0.005)
    dens = 1000.0
    return {"sculpt_union_volume_m3": vol, "mass_union_kg": vol * dens,
            "mass_union_kg_1040": vol * 1040.0}


def full_report(P, objs):
    m, extra = measurements(P, objs)
    m["hb_dorsal_contour"] = extra["hb_dorsal_contour"]
    topo = {o.name: topology(o) for o in objs}
    rows = []
    tol = 100.0 * P.get("targets_tol", 0.05)  # etapa 1: ±5 %; etapa 2: ±8 %
    for k, tgt in P["targets"].items():
        if k.startswith("_"):
            continue
        val = m.get(k)
        dev = 100.0 * (val - tgt) / tgt
        rows.append({"name": k, "target": tgt, "value": val, "dev_pct": dev, "ok": abs(dev) <= tol})
    return {"rows": rows, "extra": extra, "topology": topo}


NAMES_ES = {
    "head_body_length": "Largo cabeza-cuerpo (nariz→base cola, horizontal)",
    "hb_dorsal_contour": "Largo cabeza-cuerpo por contorno dorsal (cinta)",
    "withers_height": "Altura a la cruz",
    "croup_height": "Altura a la grupa",
    "tail_length": "Largo de cola (arco)",
    "head_length": "Largo de cabeza (nariz→occipucio)",
    "head_width": "Ancho de cabeza (cigomático)",
    "chest_depth": "Profundidad de pecho (cruz→esternón)",
    "chest_clearance": "Altura libre bajo el pecho",
    "belly_clearance": "Altura libre en el ijar (remetido)",
    "torso_width": "Ancho máximo del tronco (costillar)",
    "front_paw_width": "Ancho zarpa delantera",
    "hind_paw_width": "Ancho zarpa trasera",
    "forearm_depth": "Grosor antebrazo (fondo, z≈0.185)",
    "tail_base_diameter": "Diámetro cola cerca de la base",
}


def format_report(rep):
    lines = ["| Medida | Objetivo (m) | Malla (m) | Desv. | OK |", "|---|---:|---:|---:|:-:|"]
    for r in rep["rows"]:
        lines.append("| %s | %.3f | %.3f | %+.1f %% | %s |" % (
            NAMES_ES.get(r["name"], r["name"]), r["target"], r["value"], r["dev_pct"],
            "✔" if r["ok"] else "✘"))
    ex = rep["extra"]
    lines.append("")
    lines.append("Cabeza = %.1f %% del cabeza-cuerpo; cola = %.1f %%; distancia entre zarpas "
                 "(del./tras.) = %.3f m; largo total bbox = %.3f m; cabeza-cuerpo por el contorno "
                 "dorsal = %.3f m; masa estimada (vol. × 1040 kg/m³) = %.0f kg" % (
                     ex["head_pct_of_hb"], ex["tail_pct_of_hb"], ex["wheelbase_paws"],
                     ex["overall_length_bbox"], ex["hb_dorsal_contour"], ex["mass_est_kg"]))
    lines.append("")
    if "mass_union_kg" in ex:
        lines.append("")
        lines.append("Masa por volumen real de la unión de la escultura (sin solapes): %.1f kg a 1000 kg/m³ "
                     "(%.1f kg a 1040 kg/m³); volumen %.4f m³." % (
                         ex["mass_union_kg"], ex["mass_union_kg_1040"], ex["sculpt_union_volume_m3"]))
    if "iou" in rep:
        lines.append("")
        lines.append("IoU de la malla final posada como en las fotos: lateral %.3f, frontal %.3f." % (
            rep["iou"].get("side_iou", 0), rep["iou"].get("front_iou", 0)))
    lines.append("")
    lines.append("| Objeto | Quads | Tris | N-gons | No-manifold | Bordes abiertos | Vért. sueltos | "
                 "Normales incoherentes | Normales afuera | Auto-intersec. | Caras colapsadas | "
                 "Ángulos [p1, p99] | Ángulos fuera de 25–155° |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|:-:|---:|---:|---:|---:|")
    tq = 0
    for name, t in rep["topology"].items():
        tq += t["quads"]
        lines.append("| %s | %d | %d | %d | %d | %d | %d | %d | %s | %d | %d | [%.0f°, %.0f°] | %d |" % (
            name, t["quads"], t["tris"], t["ngons"], t["non_manifold_edges"], t["boundary_edges"],
            t["loose_verts"], t["inconsistent_normals"], "sí" if t["outward_normals"] else "NO",
            t["self_intersections"], t.get("collapsed_faces", 0), t.get("angle_p01", 0),
            t.get("angle_p99", 0), t.get("angles_outside_25_155", 0)))
    lines.append("| **Total** | **%d** | | | | | | | | | | | |" % tq)
    return "\n".join(lines)


def write_report(rep, vdir, version):
    with open(os.path.join(vdir, "measurements.json"), "w", encoding="utf-8") as f:
        json.dump(rep, f, indent=2, default=float)
    with open(os.path.join(vdir, "measurements.md"), "w", encoding="utf-8") as f:
        f.write("# Medidas y validación — %s\n\n" % version)
        f.write(format_report(rep))
        f.write("\n")
