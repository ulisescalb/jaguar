"""Primitivas de construcción de mallas quad para el jaguar.

Todo se construye como listas de vértices/caras en Python puro (MeshData) y
luego se convierte a objetos de Blender. Así controlamos exactamente la
topología: anillos (bucles de aristas) por sección transversal, agujeros
rectangulares para injertar patas/cola/ojos, y tapas de rejilla quad
(Coons patch) para cerrar tubos sin triángulos ni n-gons.
"""
import math

from mathutils import Vector, Matrix


# ---------------------------------------------------------------- utilidades
def sgnpow(v, e):
    return math.copysign(abs(v) ** e, v)


def lerp(a, b, t):
    return a + (b - a) * t


def smoothstep(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def catmull_rom(points, samples):
    """Muestrea una spline Catmull-Rom centrípeta por longitud de arco.

    points: lista de Vector. Devuelve `samples` puntos equiespaciados en arco.
    """
    pts = [Vector(p) for p in points]
    ext = [pts[0] + (pts[0] - pts[1])] + pts + [pts[-1] + (pts[-1] - pts[-2])]
    dense = []
    for i in range(1, len(ext) - 2):
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
        for k in range(40):
            t = k / 40.0
            t2, t3 = t * t, t * t * t
            dense.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2
                                + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    dense.append(pts[-1].copy())
    acc = [0.0]
    for i in range(1, len(dense)):
        acc.append(acc[-1] + (dense[i] - dense[i - 1]).length)
    total = acc[-1]
    out = []
    j = 0
    for s in range(samples):
        target = total * s / (samples - 1)
        while j < len(acc) - 2 and acc[j + 1] < target:
            j += 1
        seg = acc[j + 1] - acc[j]
        t = 0.0 if seg < 1e-12 else (target - acc[j]) / seg
        out.append(dense[j].lerp(dense[j + 1], t))
    return out, total


def interp_profile(keys, t):
    """Interpolación suave de una lista [[t, valor], ...] ordenada por t."""
    if t <= keys[0][0]:
        return keys[0][1]
    for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
        if t <= t1:
            u = smoothstep((t - t0) / (t1 - t0))
            return lerp(v0, v1, u)
    return keys[-1][1]


# ------------------------------------------------------------------ MeshData
class MeshData:
    def __init__(self, name):
        self.name = name
        self.verts = []
        self.faces = []
        self.groups = {}

    def add_vert(self, co):
        self.verts.append(Vector(co))
        return len(self.verts) - 1

    def add_verts(self, pts):
        return [self.add_vert(p) for p in pts]

    def quad(self, a, b, c, d):
        self.faces.append((a, b, c, d))

    def bridge(self, l1, l2):
        n = len(l1)
        assert n == len(l2), (n, len(l2))
        for j in range(n):
            self.quad(l1[j], l1[(j + 1) % n], l2[(j + 1) % n], l2[j])

    def group(self, name, idxs, w=1.0):
        g = self.groups.setdefault(name, {})
        for i in idxs:
            g[i] = max(g.get(i, 0.0), w)

    def transform(self, mat):
        self.verts = [mat @ v for v in self.verts]

    def apply_bumps(self, bumps, only=None):
        """Desplazamientos gaussianos ("esculpido" paramétrico) sobre la jaula.

        Cada bump: c (centro), r (radios x,y,z), a (amplitud en m), dir
        (vector de empuje), mirror (aplica también en -X). `only`: conjunto
        de índices a los que se limita (p.ej. sólo el tronco).
        """
        idx = range(len(self.verts)) if only is None else only
        for b in bumps:
            c, r = Vector(b["c"]), b["r"]
            d = Vector(b.get("dir", (0, 0, 1))).normalized()
            copies = [(c, d)]
            if b.get("mirror", True) and abs(c.x) > 1e-6:
                copies.append((Vector((-c.x, c.y, c.z)), Vector((-d.x, d.y, d.z))))
            disp = {}
            for cc, dd in copies:
                for i in idx:
                    v = self.verts[i]
                    q = (((v.x - cc.x) / r[0]) ** 2 + ((v.y - cc.y) / r[1]) ** 2
                         + ((v.z - cc.z) / r[2]) ** 2)
                    if q < 9.0:
                        disp[i] = disp.get(i, Vector()) + dd * (b["a"] * math.exp(-q))
            for i, dv in disp.items():
                self.verts[i] = self.verts[i] + dv


# -------------------------------------------------------------- secciones
def section_ring(n, y, zt, zb, w, wz=0.5, pt=2.0, pb=2.0, tilt_deg=0.0,
                 x_off=0.0, drape=0.0):
    """Anillo de n vértices en un plano vertical (Y = cte), girado `tilt`.

    Índice 0 = línea media dorsal; crece hacia +X (lado izquierdo del animal,
    que mira a -Y). La sección es una superelipse partida: mitad superior con
    exponente pt, inferior con pb; el ancho máximo w está a la altura
    zc = zb + wz*(zt-zb). `drape` baja los laterales de la mitad inferior
    (p.ej. el labio superior que cae sobre la mandíbula).
    """
    zc = zb + wz * (zt - zb)
    pts = []
    for i in range(n):
        phi = 2.0 * math.pi * i / n
        s, c = math.sin(phi), math.cos(phi)
        if c >= 0:
            x = w * sgnpow(s, 2.0 / pt)
            z = zc + (zt - zc) * abs(c) ** (2.0 / pt)
        else:
            x = w * sgnpow(s, 2.0 / pb)
            z = zc - (zc - zb) * abs(c) ** (2.0 / pb)
            z -= drape * abs(math.sin(2 * phi))
        pts.append(Vector((x + x_off, y, z)))
    if tilt_deg:
        rot = Matrix.Rotation(math.radians(tilt_deg), 3, 'X')
        ctr = Vector((0.0, y, zc))
        pts = [ctr + rot @ (p - ctr) for p in pts]
    return pts


def tube_faces(md, rings, holes=()):
    """Caras quad entre anillos consecutivos, saltando celdas de agujeros.

    holes: lista de (s0, la, r0, lr): celdas (s, r) con s0<=s<s0+la y r en
    [r0, r0+lr) (cíclico) se omiten.
    """
    n = len(rings[0])
    skip = set()
    for (s0, la, r0, lr) in holes:
        for s in range(s0, s0 + la):
            for k in range(lr):
                skip.add((s, (r0 + k) % n))
    for s in range(len(rings) - 1):
        for i in range(n):
            if (s, i) in skip:
                continue
            md.quad(rings[s][i], rings[s][(i + 1) % n],
                    rings[s + 1][(i + 1) % n], rings[s + 1][i])


def hole_loop(rings, s0, la, r0, lr, mirror=False):
    """Bucle ordenado (2*(la+lr) vértices) del borde de un agujero."""
    n = len(rings[0])

    def R(s, r):
        r %= n
        if mirror:
            r = (n - r) % n
        return rings[s][r]

    loop = []
    for s in range(s0, s0 + la):
        loop.append(R(s, r0))
    for k in range(lr):
        loop.append(R(s0 + la, r0 + k))
    for s in range(s0 + la, s0, -1):
        loop.append(R(s, r0 + lr))
    for k in range(lr, 0, -1):
        loop.append(R(s0, r0 + k))
    return loop


def mirror_hole(n, r0, lr):
    return (n - r0 - lr) % n


def grid_cap(md, loop, a, b, c0=0, dome=None, hole=None, flatten_z=None,
             dome_power=1.0):
    """Cierra un bucle de 2(a+b) vértices con una rejilla a×b de quads.

    Posiciones interiores por Coons patch; `dome` (Vector) empuja el centro.
    `hole` = (i0, ha, j0, hb) deja un agujero ha×hb y devuelve su bucle.
    Devuelve (G, hole_loop) donde G[i][j] son índices.
    """
    L = len(loop)
    assert L == 2 * (a + b), (L, a, b)
    lp = [loop[(c0 + k) % L] for k in range(L)]
    S0 = lp[0:a + 1]
    S1 = lp[a:a + b + 1]
    S2 = lp[a + b:2 * a + b + 1]
    S3 = lp[2 * a + b:] + [lp[0]]
    G = [[None] * (b + 1) for _ in range(a + 1)]
    for i in range(a + 1):
        G[i][0] = S0[i]
        G[i][b] = S2[a - i]
    for j in range(b + 1):
        G[a][j] = S1[j]
        G[0][j] = S3[b - j]
    V = md.verts
    P00, Pa0, Pab, P0b = V[G[0][0]], V[G[a][0]], V[G[a][b]], V[G[0][b]]
    for i in range(1, a):
        for j in range(1, b):
            u, v = i / a, j / b
            p = ((1 - v) * V[G[i][0]] + v * V[G[i][b]] + (1 - u) * V[G[0][j]] + u * V[G[a][j]]
                 - ((1 - u) * (1 - v) * P00 + u * (1 - v) * Pa0 + u * v * Pab + (1 - u) * v * P0b))
            if dome is not None:
                f = (math.sin(math.pi * u) * math.sin(math.pi * v)) ** dome_power
                p = p + dome * f
            if flatten_z is not None:
                p.z = flatten_z
            G[i][j] = md.add_vert(p)
    skip = set()
    hl = None
    if hole:
        i0, ha, j0, hb = hole
        for i in range(i0, i0 + ha):
            for j in range(j0, j0 + hb):
                skip.add((i, j))
        hl = []
        for i in range(i0, i0 + ha):
            hl.append(G[i][j0])
        for j in range(j0, j0 + hb):
            hl.append(G[i0 + ha][j])
        for i in range(i0 + ha, i0, -1):
            hl.append(G[i][j0 + hb])
        for j in range(j0 + hb, j0, -1):
            hl.append(G[i0][j])
    for i in range(a):
        for j in range(b):
            if (i, j) in skip:
                continue
            md.quad(G[i][j], G[i + 1][j], G[i + 1][j + 1], G[i][j + 1])
    return G, hl


# --------------------------------------------------- anillos con emparejado
def unwrap(angles):
    out = [angles[0]]
    for a in angles[1:]:
        prev = out[-1]
        while a - prev > math.pi:
            a -= 2 * math.pi
        while a - prev < -math.pi:
            a += 2 * math.pi
        out.append(a)
    return out


def matched_angles(loop_pts, center, ax_u, ax_v, su=1.0, sv=1.0):
    """Ángulos de los puntos de un bucle alrededor de `center` en el plano
    (ax_u, ax_v), normalizados por semiejes su/sv. Devuelve (ángulos
    desenrollados, sentido +1/-1)."""
    ang = []
    for p in loop_pts:
        d = p - center
        ang.append(math.atan2(d.dot(ax_v) / sv, d.dot(ax_u) / su))
    ang = unwrap(ang)
    span = ang[-1] - ang[0]
    sense = 1.0 if span > 0 else -1.0
    return ang, sense


def blended_angles(base_angles, sense, beta):
    n = len(base_angles)
    uni = [base_angles[0] + sense * 2 * math.pi * j / n for j in range(n)]
    # corrige el desfase medio para que la distribución uniforme quede
    # centrada respecto a la del bucle original (minimiza torsión)
    off = sum(b - u for b, u in zip(base_angles, uni)) / n
    uni = [u + off for u in uni]
    return [lerp(b, u, beta) for b, u in zip(base_angles, uni)]


def ellipse_ring(center, ax_u, ax_v, ru, rv, angles, p=2.0):
    pts = []
    for a in angles:
        c, s = math.cos(a), math.sin(a)
        pts.append(center + ax_u * (ru * sgnpow(c, 2.0 / p)) + ax_v * (rv * sgnpow(s, 2.0 / p)))
    return pts


# ------------------------------------------------------------ quad sphere
def quad_sphere(res):
    """Esfera de quads (cubo subdividido proyectado). Devuelve verts, faces."""
    verts = []
    index = {}
    faces = []

    def vid(p):
        key = tuple(round(c, 6) for c in p)
        if key not in index:
            index[key] = len(verts)
            verts.append(Vector(p).normalized())
        return index[key]

    axes = [((1, 0, 0), (0, 1, 0), (0, 0, 1)), ((-1, 0, 0), (0, 0, 1), (0, 1, 0)),
            ((0, 1, 0), (0, 0, 1), (1, 0, 0)), ((0, -1, 0), (1, 0, 0), (0, 0, 1)),
            ((0, 0, 1), (1, 0, 0), (0, 1, 0)), ((0, 0, -1), (0, 1, 0), (1, 0, 0))]
    for n, u, v in axes:
        n, u, v = Vector(n), Vector(u), Vector(v)
        grid = [[None] * (res + 1) for _ in range(res + 1)]
        for i in range(res + 1):
            for j in range(res + 1):
                # proyección equiangular: celdas más uniformes
                a = math.tan((i / res - 0.5) * math.pi / 2)
                b = math.tan((j / res - 0.5) * math.pi / 2)
                grid[i][j] = vid(n + u * a + v * b)
        for i in range(res):
            for j in range(res):
                faces.append((grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]))
    return verts, faces
