"""Transferencia de la escultura SDF a la malla limpia de animación.

Se conserva la topología de la v06 (anillos de sección, injertos de patas y
cola, tapas de rejilla, cuencas con bucles de párpado, comisura), pero las
posiciones salen de la escultura:

1. Cada anillo se coloca en su plano anatómico (tronco: planos verticales;
   cuello: perpendicular al eje del cuello; patas y cola: perpendicular al hueso,
   centrado en el landmark; cabeza y mandíbula: perpendicular al eje del cráneo)
   y sus vértices se lanzan por raycast desde el centro hasta la superficie.
   Así cada bucle cae exactamente en su articulación.
2. Se aplica 1 nivel de Catmull-Clark (fuera de este módulo).
3. Todos los vértices se proyectan a la superficie (Newton sobre la SDF) y se
   relajan tangencialmente unas pocas iteraciones (Laplaciano proyectado al
   plano tangente + reproyección), sin sacar los bucles de su sitio.

Sólo numpy + mathutils (corre dentro de Blender).
"""
import math

import numpy as np
from mathutils import Vector, Matrix

from geom import (MeshData, tube_faces, hole_loop, mirror_hole, grid_cap, matched_angles,
                  blended_angles, quad_sphere)
import sdf as sdfmod

X = np.array([1.0, 0.0, 0.0])
Z = np.array([0.0, 0.0, 1.0])


# ---------------------------------------------------------------- campos
class Field:
    """SDF de un subconjunto de primitivas en pose neutra."""

    def __init__(self, M, comps, keep=None):
        self.M = M
        self.B = M.sk.bones({})
        self.prims = [p for p in M.prims if p.comp in comps and (keep is None or keep(p))]

    def __call__(self, pts):
        pts = np.asarray(pts, float).reshape(-1, 3)
        d = np.full(len(pts), 1.0)
        for pr in self.prims:
            lo, hi = self.M.posed_aabb(pr, self.B)
            sel = np.nonzero(np.all((pts >= lo) & (pts <= hi), 1))[0]
            if len(sel) == 0:
                continue
            p0, P, R = self.B[pr.bone]
            v = pr.sdf(p0 + (pts[sel] - P) @ R)
            d[sel] = sdfmod.smin(d[sel], v, pr.k) if pr.op == "add" else sdfmod.smax(d[sel], -v, pr.k)
        return d

    def grad(self, pts, eps=4e-4):
        g = np.zeros((len(pts), 3))
        for i in range(3):
            e = np.zeros(3)
            e[i] = eps
            g[:, i] = (self(pts + e) - self(pts - e)) / (2 * eps)
        return g


def is_torso(p):
    """Primitivas del tronco y cuello (sin patas, cola ni zarpas)."""
    if p.bone not in ("torso", "neck1", "neck2"):
        return False
    return not p.name.startswith("tail")


def is_trunk(p):
    """Tronco + masas del hombro, brazo y muslo, que forman la pared del cuerpo:
    los anillos del tronco se apoyan sobre ellas (si no, quedarían debajo y la
    proyección final los plegaría)."""
    if p.name.startswith("tail"):
        return False
    return p.bone in ("torso", "neck1", "neck2") or p.bone.split("_")[0] in ("scapula", "femur")


# ----------------------------------------------------------------- raycast
def raycast(field, centers, dirs, rmax, n=48):
    """Primera salida (dentro→fuera) a lo largo de cada rayo. Devuelve t."""
    centers = np.broadcast_to(np.asarray(centers, float), dirs.shape)
    rmax = np.broadcast_to(np.asarray(rmax, float), (len(dirs),))
    ts = np.linspace(0, 1, n)[None, :] * rmax[:, None]
    P = centers[:, None, :] + dirs[:, None, :] * ts[:, :, None]
    d = field(P.reshape(-1, 3)).reshape(len(dirs), n)
    inside = d < 0
    t = rmax * 0.55  # respaldo si no hay cruce
    lo = np.zeros(len(dirs))
    hi = np.zeros(len(dirs))
    ok = np.zeros(len(dirs), bool)
    for i in range(len(dirs)):
        idx = np.nonzero(inside[i, :-1] & ~inside[i, 1:])[0]
        if len(idx):
            k = idx[0]
            lo[i], hi[i], ok[i] = ts[i, k], ts[i, k + 1], True
    for _ in range(16):
        mid = (lo + hi) / 2
        dm = field(centers + dirs * mid[:, None])
        inn = dm < 0
        lo = np.where(inn, mid, lo)
        hi = np.where(inn, hi, mid)
    return np.where(ok, (lo + hi) / 2, t), ok


def inside_span(field, origin, direction, a=-0.6, b=0.6, n=240):
    """Tramo interior más largo a lo largo de una recta (para centrar anillos)."""
    t = np.linspace(a, b, n)
    P = origin[None, :] + direction[None, :] * t[:, None]
    ins = field(P) < 0
    best, cur, start = (0, 0, 0), 0, 0
    for i, v in enumerate(ins):
        if v:
            if cur == 0:
                start = i
            cur += 1
            if cur > best[0]:
                best = (cur, start, i)
        else:
            cur = 0
    if best[0] == 0:
        return origin, 0.0, 0.0
    t0, t1 = t[best[1]], t[best[2]]
    return origin + direction * (t0 + t1) / 2, t0, t1


def plane_frame(normal):
    """u = lateral (X ortogonalizado), v = normal × u."""
    n = np.asarray(normal, float)
    n = n / np.linalg.norm(n)
    u = X - n * n[0]
    if np.linalg.norm(u) < 1e-6:
        u = np.array([0.0, 1.0, 0.0]) - n * n[1]
    u /= np.linalg.norm(u)
    v = np.cross(n, u)
    return u, v


def ring_dirs(normal_tilt_deg, n):
    """Direcciones de un anillo de tronco: índice 0 arriba, crece hacia +X;
    plano vertical girado `tilt` grados alrededor de X."""
    a = math.radians(normal_tilt_deg)
    out = []
    for i in range(n):
        phi = 2 * math.pi * i / n
        d = np.array([math.sin(phi), 0.0, math.cos(phi)])
        # girar alrededor de X
        y = d[1] * math.cos(a) - d[2] * math.sin(a)
        z = d[1] * math.sin(a) + d[2] * math.cos(a)
        out.append([d[0], y, z])
    return np.array(out)


# ------------------------------------------------------------------ cuerpo
def body_stations(C, sk):
    """Estaciones del tronco a partir de los landmarks (siguen las escalas)."""
    p = sk.pts
    st = []
    # cuello: de dentro de la cabeza hacia la base, perpendicular al eje
    c_head = p["condyle"] + np.array([0, -0.02, 0.0])
    c_base = (p["T1"] + p["scap_top_L"] * np.array([0, 1, 1])) / 2 + np.array([0, -0.06, 0.02])
    axis = c_base - c_head
    tilt = math.degrees(math.atan2(axis[2], axis[1]))
    for f in C["neck_fracs"]:
        c = c_head + axis * f
        st.append({"c": c, "tilt": tilt * (1 - f) + 0.0 * f})
    # tronco: posiciones Y entre landmarks
    for (a, b, t) in C["torso_y"]:
        y = p[a][1] + t * (p[b][1] - p[a][1])
        st.append({"y": y, "tilt": 0.0})
    return st


def build_body(P, M):
    C = P["conform"]
    sk = M.sk
    n = C["ring_verts"]
    torso = Field(M, ("body",), keep=is_trunk)
    md = MeshData("Jaguar_Body")
    rings = []
    for s in body_stations(C, sk):
        if "c" in s:
            a = math.radians(s["tilt"])
            up = np.array([0.0, -math.sin(a), math.cos(a)])
            ctr, _, _ = inside_span(torso, s["c"], up, -0.3, 0.3)
        else:
            ctr, _, _ = inside_span(torso, np.array([0.0, s["y"], 0.5]), Z, -0.45, 0.45)
        dirs = ring_dirs(s["tilt"], n)
        t, _ = raycast(torso, ctr, dirs, 0.35)
        rings.append(md.add_verts([Vector(ctr + d * ti) for d, ti in zip(dirs, t)]))
    holes, loops = [], {}
    for key, tag in (("front", "F"), ("hind", "H")):
        h = C["holes"][key]
        s0, la, r0, lr = h["station"], h["along"], h["ring"], h["around"]
        holes += [(s0, la, r0, lr), (s0, la, mirror_hole(n, r0, lr), lr)]
        loops[tag + "L"] = hole_loop(rings, s0, la, r0, lr)
        loops[tag + "R"] = hole_loop(rings, s0, la, r0, lr, mirror=True)
    tube_faces(md, rings, holes)
    torso_idx = [i for r in rings for i in r]
    a = n // 4
    c0 = (n - a // 2) % n
    Gn, _ = grid_cap(md, rings[0], a, a, c0=c0, dome=Vector((0, -1, 0.15)).normalized() * 0.03)
    th = C["tail_hole"]
    Gr, tail_loop = grid_cap(md, rings[-1], a, a, c0=c0, dome=Vector((0, 1, 0)) * C["rump_dome"],
                             hole=(th["i0"], th["ha"], th["j0"], th["hb"]))
    for G in (Gn, Gr):
        torso_idx += [G[i][j] for i in range(1, a) for j in range(1, a) if G[i][j] is not None]
    md.group("torso", torso_idx)
    md.group("neck", [i for r in rings[:len(C["neck_fracs"])] for i in r])

    limbs = Field(M, ("body",), keep=lambda p: not is_torso(p) and not p.name.startswith("tail"))
    tailf = Field(M, ("body",), keep=lambda p: p.name.startswith("tail"))
    for key, tag in (("front", "F"), ("hind", "H")):
        loopL = loops[tag + "L"]
        rp, c0l = leg_rings(md, loopL, C["legs"][key], sk, limbs, "L")
        attach_leg(md, loopL, rp, c0l, C["legs"][key], "leg_%sL" % tag, "paw_%sL" % tag)
        rpr = [[Vector((-v.x, v.y, v.z)) for v in r] for r in rp]
        attach_leg(md, loops[tag + "R"], rpr, c0l, C["legs"][key], "leg_%sR" % tag, "paw_%sR" % tag)
        md.group("loop_shoulder" if tag == "F" else "loop_hip", loopL + loops[tag + "R"])
    centerline = build_tail(md, tail_loop, C["tail"], sk, tailf, trunk=torso)
    return md, centerline


def leg_rings(md, loop, spec, sk, field, side):
    """Anillos de una pata izquierda: perpendiculares al hueso en cada estación
    y horizontales en la zarpa, emparejados angularmente con el injerto."""
    p = sk.pts
    rings_spec = spec["rings"]
    frames = []
    for r in rings_spec:
        if "paw_z" in r:
            a, b = p[r["paw"][0] + "_L"], p[r["paw"][1] + "_L"]
            c = a + r["paw"][2] * (b - a)
            c = np.array([c[0], c[1], r["paw_z"]])
            nrm = np.array([0.0, 0.0, -1.0])
        elif "z_at" in r:  # corte horizontal (muslo/rodilla), z entre dos landmarks
            a, b, f = r["z_at"]
            z = p[a + "_L"][2] + f * (p[b + "_L"][2] - p[a + "_L"][2])
            a, b, t = r["c"]
            c = p[a + "_L"] + t * (p[b + "_L"] - p[a + "_L"]) + np.array(r.get("off", [0, 0, 0]))
            c = np.array([c[0], c[1], z])
            nrm = np.array([0.0, 0.0, -1.0])
        else:
            a, b = p[r["a"] + "_L"], p[r["b"] + "_L"]
            c = a + r["t"] * (b - a)
            nrm = b - a
            if "blend_next" in r:
                a2, b2 = p[r["blend_next"][0] + "_L"], p[r["blend_next"][1] + "_L"]
                nrm = nrm / np.linalg.norm(nrm) + (b2 - a2) / np.linalg.norm(b2 - a2)
            c = c + np.array(r.get("off", [0, 0, 0]))
        u, v = plane_frame(nrm)
        frames.append((c, u, v, r))
    c1, u1, v1, _ = frames[0]
    loop_pts = [Vector(md.verts[i]) for i in loop]
    ang, sense = matched_angles(loop_pts, Vector(c1), Vector(u1), Vector(v1))
    blend = spec.get("blend", [0.5])
    out = []
    for k, (c, u, v, r) in enumerate(frames):
        beta = blend[k] if k < len(blend) else 1.0
        angs = np.array(blended_angles(ang, sense, beta))
        dirs = np.cos(angs)[:, None] * u[None, :] + np.sin(angs)[:, None] * v[None, :]
        t, _ = raycast(field, c, dirs, r.get("rmax", 0.14))
        pts = c[None, :] + dirs * t[:, None]
        if "paw_z" in r:
            pts[:, 2] = r["paw_z"]
        out.append([Vector(q) for q in pts])
    last = blended_angles(ang, sense, 1.0)
    best, c0 = 9e9, 0
    for j in range(4):
        dd = min(abs(math.remainder(last[j] - (math.pi / 4 + kk * math.pi / 2), 2 * math.pi)) for kk in range(4))
        if dd < best:
            best, c0 = dd, j
    return out, c0


def attach_leg(md, loop, ring_pts, c0, spec, name, paw_name):
    prev = loop
    leg_idx, paw_idx = [], []
    paw_from = spec.get("paw_from_ring", len(ring_pts) - 3)
    for k, pts in enumerate(ring_pts):
        idx = md.add_verts(pts)
        md.bridge(prev, idx)
        prev = idx
        leg_idx += idx
        if k >= paw_from:
            paw_idx += idx
    m = len(prev)
    a = m // 4
    G, _ = grid_cap(md, prev, a, m // 2 - a, c0=c0, flatten_z=0.0)
    cap_idx = [G[i][j] for i in range(1, a) for j in range(1, m // 2 - a)]
    md.group(name, leg_idx + cap_idx)
    md.group(paw_name, paw_idx + cap_idx)
    md.group("sole_" + name.split("_")[1], cap_idx)


def build_tail(md, loop, T, sk, field, trunk=None):
    chain = [np.array(q) for q in sk.tail_points(sk.tail_neutral)]
    acc = [0.0]
    for a, b in zip(chain, chain[1:]):
        acc.append(acc[-1] + np.linalg.norm(b - a))
    total = acc[-1]

    def at(s):
        for i in range(1, len(acc)):
            if acc[i] >= s:
                f = (s - acc[i - 1]) / (acc[i] - acc[i - 1])
                return chain[i - 1] + f * (chain[i] - chain[i - 1]), (chain[i] - chain[i - 1]) / (acc[i] - acc[i - 1])
        return chain[-1], (chain[-1] - chain[-2]) / np.linalg.norm(chain[-1] - chain[-2])

    nr = T["rings"]
    s0 = T.get("start", 0.03)
    if trunk is not None:  # primer punto de la cadena fuera de la grupa
        for s in np.linspace(0.0, 0.25, 51):
            if trunk(at(s)[0][None, :])[0] > 0:
                s0 = max(s0, s + 0.005)
                break
    usable = total - T.get("tip_cap", 0.025)
    loop_pts = [Vector(md.verts[i]) for i in loop]
    c1, t1 = at(s0 + (usable - s0) / nr)
    u1, v1 = plane_frame(t1)
    ang, sense = matched_angles(loop_pts, Vector(c1), Vector(u1), Vector(v1))
    prev = loop
    tail_idx = []
    for k in range(1, nr + 1):
        s = s0 + (usable - s0) * k / nr
        c, tg = at(s)
        u, v = plane_frame(tg)
        beta = T.get("blend", [0.5])[k - 1] if k - 1 < len(T.get("blend", [0.5])) else 1.0
        angs = np.array(blended_angles(ang, sense, beta))
        dirs = np.cos(angs)[:, None] * u[None, :] + np.sin(angs)[:, None] * v[None, :]
        t, _ = raycast(field, c, dirs, 0.09)
        idx = md.add_verts([Vector(c + d * ti) for d, ti in zip(dirs, t)])
        md.bridge(prev, idx)
        prev = idx
        tail_idx += idx
    m = len(prev)
    a = m // 4
    c_end, t_end = at(usable)
    G, _ = grid_cap(md, prev, a, m // 2 - a, c0=0, dome=Vector(t_end) * 0.022, dome_power=0.6)
    cap = [G[i][j] for i in range(1, a) for j in range(1, m // 2 - a)]
    md.group("tail", tail_idx + cap)
    md.group("tail_tip", cap)
    md.group("tail_base", loop)
    return [Vector(q) for q in chain]


# ------------------------------------------------------------------- cabeza
def head_frame(sk):
    return sk.head_origin, sk.head_R


def build_head(P, M):
    C = P["conform"]["head"]
    sk = M.sk
    O, R = head_frame(sk)
    field = Field(M, ("head",))
    n = C["ring_verts"]
    md = MeshData("Jaguar_Head")
    rings = []
    for yl in C["stations_y"]:
        o = O + R @ np.array([0.0, yl, 0.0])
        up = R @ Z
        ctr, _, _ = inside_span(field, o, up, -0.15, 0.2)
        dirs = np.array([R @ d for d in ring_dirs(0.0, n)])
        t, _ = raycast(field, ctr, dirs, 0.16)
        rings.append(md.add_verts([Vector(ctr + d * ti) for d, ti in zip(dirs, t)]))
    eh = C["eye_hole"]
    s0, la, r0, lr = eh["station"], eh["along"], eh["ring"], eh["around"]
    tube_faces(md, rings, [(s0, la, r0, lr), (s0, la, mirror_hole(n, r0, lr), lr)])
    a = n // 4
    c0 = (n - a // 2) % n
    back = Vector(R @ np.array([0, 1.0, 0]))
    fwd = Vector(R @ np.array([0, -1.0, 0]))
    grid_cap(md, rings[0], a, a, c0=c0, dome=back * 0.02)
    Gf, _ = grid_cap(md, rings[-1], a, a, c0=c0, dome=fwd * 0.006)
    md.group("nose_tip", [Gf[a // 2][a // 2]])
    md.group("occiput", [rings[C["occiput_station"]][0]])
    # cuencas: bucles de párpado alrededor del globo ocular
    E = P["sculpt"]["eye"]
    eyes = {}
    for side, sx in (("L", 1.0), ("R", -1.0)):
        gy, gp = math.radians(E["gaze_yaw_deg"]), math.radians(E["gaze_pitch_deg"])
        A = R @ np.array([sx * math.sin(gy) * math.cos(gp), -math.cos(gy) * math.cos(gp), math.sin(gp)])
        Ec = sk.pts["orbit_" + side] - A * E["inset"]
        eyes[side] = (Ec, A)
    loopL = hole_loop(rings, s0, la, r0, lr)
    skin = Field(M, ("head",), keep=lambda p: not p.name.startswith("eye_socket"))
    ringsL = eye_socket(md, loopL, eyes["L"], E, C, R, field=skin)
    loopR = hole_loop(rings, s0, la, r0, lr, mirror=True)
    prev, ringsR = loopR, []
    for rl in ringsL:
        idx = md.add_verts([Vector((-md.verts[i].x, md.verts[i].y, md.verts[i].z)) for i in rl])
        md.bridge(prev, idx)
        prev, ringsR = idx, ringsR + [idx]
    m = len(prev)
    a2 = 2 if m % 4 == 2 else m // 4
    Ec, A = eyes["R"]
    G, _ = grid_cap(md, prev, a2, m // 2 - a2, c0=0, dome=Vector(-A) * 0.004)
    md.group("eye_inner", [G[i][j] for i in range(1, a2) for j in range(1, m // 2 - a2)])
    md.group("eyelid_L", [i for r in ringsL[:3] for i in r] + loopL)
    md.group("eyelid_R", [i for r in ringsR[:3] for i in r] + loopR)
    fx = C.get("eye_fixed_from", 2)
    md.group("eye_inner", [i for r in ringsL[fx:] + ringsR[fx:] for i in r])
    return md, eyes


def eye_socket(md, loop, eye, E, C, R, field=None):
    Ec, A = eye
    Rr = E["radius"]
    U = np.cross(A, R @ Z)
    U /= np.linalg.norm(U)
    if U[0] < 0:
        U = -U
    V = np.cross(U, A)
    V /= np.linalg.norm(V)
    if (V @ (R @ Z)) < 0:
        V = -V
    sl = math.radians(C.get("eye_slant_deg", 8.0))
    U2, V2 = U * math.cos(sl) + V * math.sin(sl), -U * math.sin(sl) + V * math.cos(sl)
    ox, oy = C.get("eye_open", [1.05, 0.72])
    loop_pts = [Vector(md.verts[i]) for i in loop]
    ang, sense = matched_angles(loop_pts, Vector(Ec), Vector(U2), Vector(V2), ox, oy)
    prev, rings = loop, []
    snap = C.get("socket_snap", {})
    for k, (rho, h) in enumerate(C["socket_rings"]):
        angs = blended_angles(ang, sense, 0.5 if k == 0 else 1.0)
        P = np.array([Ec + U2 * (rho * Rr * ox * math.cos(t)) + V2 * (rho * Rr * oy * math.sin(t)) + A * (h * Rr)
                      for t in angs])
        if field is not None and str(k) in snap:
            # apoyar el anillo sobre la piel de la cabeza a lo largo del eje del ojo
            ts = np.linspace(-0.03, 0.03, 61)
            Q = P[:, None, :] + A[None, None, :] * ts[None, :, None]
            d = field(Q.reshape(-1, 3)).reshape(len(P), len(ts))
            for i in range(len(P)):
                idx = np.nonzero((d[i, :-1] < 0) & (d[i, 1:] >= 0))[0]
                if len(idx):
                    j = idx[np.argmin(np.abs(ts[idx]))]
                    P[i] = P[i] + A * (ts[j] + snap[str(k)])
        pts = [Vector(q) for q in P]
        idx = md.add_verts(pts)
        md.bridge(prev, idx)
        prev, rings = idx, rings + [idx]
    m = len(prev)
    a = 2 if m % 4 == 2 else m // 4
    G, _ = grid_cap(md, prev, a, m // 2 - a, c0=0, dome=Vector(-A) * 0.004)
    md.group("eye_inner", [G[i][j] for i in range(1, a) for j in range(1, m // 2 - a)])
    return rings


def build_jaw(P, M):
    C = P["conform"]["jaw"]
    sk = M.sk
    O, R = head_frame(sk)
    field = Field(M, ("jaw",))
    n = C["ring_verts"]
    md = MeshData("Jaguar_LowerJaw")
    rings = []
    for yl in C["stations_y"]:
        o = O + R @ np.array([0.0, yl, -0.075])
        ctr, _, _ = inside_span(field, o, R @ Z, -0.06, 0.06)
        dirs = np.array([R @ d for d in ring_dirs(0.0, n)])
        t, _ = raycast(field, ctr, dirs, 0.10)
        rings.append(md.add_verts([Vector(ctr + d * ti) for d, ti in zip(dirs, t)]))
    tube_faces(md, rings)
    a = 4 if n == 20 else n // 4
    b = n // 2 - a
    c0 = (n - a // 2) % n
    grid_cap(md, rings[0], a, b, c0=c0, dome=Vector(R @ np.array([0, 1.0, 0])) * 0.006)
    Gc, _ = grid_cap(md, rings[-1], a, b, c0=c0, dome=Vector(R @ np.array([0, -1.0, 0])) * 0.005)
    md.group("chin", [Gc[a // 2][b // 2]])
    md.group("lip_lower", [r[0] for r in rings])
    return md


def build_ear(P, M, side):
    """Concha de oreja: esfera de quads aplastada y ahuecada, colocada con el
    marco de la primitiva ear_shell y luego proyectada sobre la SDF."""
    pr = next(p for p in M.prims if p.name == "ear_shell_" + side)
    verts, faces = quad_sphere(P["conform"]["ear_res"])
    out = []
    for s in verts:
        q = np.array([s[0] * pr.r[0], s[1] * pr.r[1], s[2] * pr.r[2]])
        if s[1] < 0:  # cara frontal: hueco
            f = max(0.0, 1 - (s[0] / 0.8) ** 2 - ((s[2] - 0.15) / 0.85) ** 2)
            q[1] = min(q[1] + 0.006 * f, abs(s[1]) * pr.r[1] - 0.002)
        out.append(Vector(pr.c + pr.M @ q))
    md = MeshData("Jaguar_Ear" + side)
    md.verts = out
    md.faces = list(faces)
    return md


# -------------------------------------------------------- proyección final
def vertex_neighbors(me):
    n = len(me.vertices)
    nb = [set() for _ in range(n)]
    for e in me.edges:
        a, b = e.vertices
        nb[a].add(b)
        nb[b].add(a)
    return [np.array(sorted(s)) for s in nb]


def project_relax(obj, field, iters=4, lam=0.45, skip_group=None, newton=4):
    """Proyecta los vértices de `obj` a la superficie de `field` y relaja
    tangencialmente. `skip_group`: vértices que no se tocan (párpado interior)."""
    me = obj.data
    V = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", V)
    V = V.reshape(-1, 3)
    fixed = np.zeros(len(V), bool)
    if skip_group and skip_group in obj.vertex_groups:
        gi = obj.vertex_groups[skip_group].index
        for v in me.vertices:
            for g in v.groups:
                if g.group == gi and g.weight > 0.5:
                    fixed[v.index] = True
    free = ~fixed
    nb = vertex_neighbors(me)

    def project(P, steps):
        for _ in range(steps):
            d = field(P)
            g = field.grad(P)
            gg = np.maximum((g * g).sum(1), 1e-8)
            step = (d / gg)[:, None] * g
            # limitar saltos grandes (regiones mal condicionadas)
            ln = np.linalg.norm(step, axis=1)
            step *= np.minimum(1.0, 0.02 / np.maximum(ln, 1e-9))[:, None]
            P = P - step
        return P

    V[free] = project(V[free], newton)
    for _ in range(iters):
        avg = np.array([V[n].mean(0) if len(n) else V[i] for i, n in enumerate(nb)])
        g = field.grad(V)
        nrm = g / np.maximum(np.linalg.norm(g, axis=1, keepdims=True), 1e-9)
        delta = avg - V
        delta -= (delta * nrm).sum(1, keepdims=True) * nrm
        V[free] += lam * delta[free]
        V[free] = project(V[free], 2)
    me.vertices.foreach_set("co", V.ravel())
    me.update()
    res = np.abs(field(V[free]))
    return float(res.mean()), float(res.max())
