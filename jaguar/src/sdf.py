"""Escultura del jaguar como campo de distancia con signo (SDF).

Unión suave (smooth-min) de elipsoides y conos redondeados ("cápsulas
cónicas") anclados a los landmarks del esqueleto (src/skeleton.py). Cada
primitiva va unida a un hueso: al posar el esqueleto se mueve rígidamente con
él, así la misma escultura sirve en pose neutra y en las poses de las fotos.

Componentes: body (tronco, cuello, patas, cola), head (cráneo y hocico),
jaw (mandíbula), ear_L / ear_R. Los ojos son esferas aparte.

Sólo numpy (funciona dentro de Blender). La extracción de superficie
(marching cubes) está en src/sculpt.py y usa scikit-image.
"""
import math

import numpy as np

from skeleton import Skeleton

COMPONENTS = ("body", "head", "jaw", "ear_L", "ear_R")


# ------------------------------------------------------------- primitivas
def sd_ellipsoid(p, r):
    """Aproximación de iq (exacta en la superficie). p en marco local."""
    q = p / r
    k0 = np.sqrt((q * q).sum(1))
    q2 = p / (r * r)
    k1 = np.sqrt((q2 * q2).sum(1))
    d = k0 * (k0 - 1.0) / np.maximum(k1, 1e-12)
    return np.where(k0 < 1e-9, -float(np.min(r)), d)


def sd_round_cone_y(p, L, r1, r2):
    """Cono redondeado de (0,0,0) a (0,L,0) con radios r1, r2 (iq, exacto)."""
    l2 = L * L
    rr = r1 - r2
    a2 = l2 - rr * rr
    il2 = 1.0 / l2
    y = p[:, 1] * L
    z = y - l2
    vx = p[:, 0] * l2
    vz = p[:, 2] * l2
    vy = p[:, 1] * l2 - y * L
    x2 = vx * vx + vy * vy + vz * vz
    y2 = y * y * l2
    z2 = z * z * l2
    k = math.copysign(1.0, rr) * rr * rr * x2 if rr != 0 else np.zeros_like(x2)
    d3 = (np.sqrt(np.maximum(x2 * a2 * il2, 0)) + y * rr) * il2 - r1
    c1 = np.sign(z) * a2 * z2 > k
    c2 = np.sign(y) * a2 * y2 < k
    return np.where(c1, np.sqrt(x2 + z2) * il2 - r2, np.where(c2, np.sqrt(x2 + y2) * il2 - r1, d3))


def smin(a, b, k):
    if k <= 0:
        return np.minimum(a, b)
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b * (1 - h) + a * h - k * h * (1 - h)


def smax(a, b, k):
    return -smin(-a, -b, k)


def frame_from_axis(axis):
    """Marco local: y = eje del hueso, x = lateral (X del mundo ortogonalizado)."""
    y = np.asarray(axis, float)
    y = y / np.linalg.norm(y)
    x = np.array([1.0, 0.0, 0.0]) - y * y[0]
    if np.linalg.norm(x) < 1e-6:
        x = np.array([0.0, 0.0, 1.0]) - y * y[2]
    x /= np.linalg.norm(x)
    z = np.cross(x, y)
    return np.stack([x, y, z], 1)  # columnas = ejes locales


def rot_xyz(deg):
    rx, ry, rz = [math.radians(a) for a in deg]
    cx, sx, cy, sy, cz, sz = math.cos(rx), math.sin(rx), math.cos(ry), math.sin(ry), math.cos(rz), math.sin(rz)
    Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return Rz @ Ry @ Rx


class Prim:
    """Primitiva resuelta en pose neutra: forma en un marco local (M, c)."""

    def __init__(self, name, comp, kind, bone, op, k, c, M, r=None, L=None, r1=None, r2=None,
                 flat=(1.0, 1.0)):
        self.name, self.comp, self.kind, self.bone, self.op, self.k = name, comp, kind, bone, op, k
        self.c, self.M = np.asarray(c, float), np.asarray(M, float)
        self.r = None if r is None else np.asarray(r, float)
        self.L, self.r1, self.r2 = L, r1, r2
        self.flat = flat

    def local(self, p):
        q = (p - self.c) @ self.M
        if self.kind == "cone":
            q[:, 0] /= self.flat[0]
            q[:, 2] /= self.flat[1]
        return q

    def sdf(self, p_neutral):
        q = self.local(p_neutral)
        if self.kind == "ell":
            return sd_ellipsoid(q, self.r)
        d = sd_round_cone_y(q, self.L, self.r1, self.r2)
        return d * min(1.0, self.flat[0], self.flat[1])

    def aabb(self):
        """Caja envolvente en pose neutra."""
        if self.kind == "ell":
            ext = np.sqrt(((self.M * self.r[None, :]) ** 2).sum(1))
            return self.c - ext, self.c + ext
        rmax = max(self.r1, self.r2)
        ends = [self.c, self.c + self.M[:, 1] * self.L]
        fl = max(self.flat)
        lo = np.min(ends, 0) - rmax * fl
        hi = np.max(ends, 0) + rmax * fl
        return lo, hi


# ------------------------------------------------------- modelo completo
class JaguarSDF:
    def __init__(self, P, scales=None, groups=None):
        self.P = P
        S = P["skeleton"]
        self.sk = Skeleton(S, scales)
        sc = P["sculpt"]
        self.groups = dict(sc.get("groups", {}))
        if groups:
            self.groups.update(groups)
        self.prims = []
        for spec in sc["prims"]:
            self.prims.append(self._resolve(spec, "L"))
            if spec.get("mirror"):
                self.prims.append(self._resolve(spec, "R"))

    # --- resolución de puntos y marcos en pose neutra
    def _pt(self, spec, side):
        pts = self.sk.pts

        def nm(n):
            return n.replace("_L", "_" + side) if side == "R" else n

        off = np.array(spec.get("off", [0, 0, 0]), float)
        if side == "R":
            off[0] = -off[0]
        if "abs" in spec:  # posición absoluta del tronco, sigue a las escalas globales
            x, y, z = spec["abs"]
            sc = self.sk.sc
            base = np.array([x, y * sc.get("torso_length", 1.0), z * sc.get("height", 1.0)])
        elif "lm" in spec:
            base = pts[nm(spec["lm"])]
        elif "at" in spec:
            a, b, t = spec["at"]
            base = pts[nm(a)] + t * (pts[nm(b)] - pts[nm(a)])
        elif "hl" in spec:
            h = np.array(spec["hl"], float)
            if side == "R":
                h[0] = -h[0]
            base = self.sk.head_origin + self.sk.head_R @ (h * self.sk.head_scale)
            off = self.sk.head_R @ (off * self.sk.head_scale)
        elif "tail" in spec:
            base = self.sk.tail_points(self.sk.tail_neutral)[spec["tail"]]
        else:
            raise KeyError(spec)
        return base + off

    def _resolve(self, s, side):
        name = s["name"] + ("_R" if side == "R" else ("_L" if s.get("mirror") else ""))
        bone = s.get("bone", "torso")
        if side == "R":
            bone = bone.replace("_L", "_R")
        comp = s["comp"]
        if side == "R":
            comp = comp.replace("_L", "_R")
        g = self.groups.get(s.get("g", ""), [1.0, 1.0, 1.0])
        k = s.get("k", 0.02)
        head_like = "hl" in s.get("c", s.get("a", {}))
        if s["type"] == "ell":
            c = self._pt(s["c"], side)
            if "axis" in s:
                a, b = s["axis"]
                nm = (lambda n: n.replace("_L", "_R")) if side == "R" else (lambda n: n)
                M = frame_from_axis(self.sk.pts[nm(b)] - self.sk.pts[nm(a)])
            else:
                M = np.eye(3)
            if "rot" in s:
                rx, ry, rz = s["rot"]
                if side == "R":
                    ry, rz = -ry, -rz
                M = M @ rot_xyz([rx, ry, rz])
            if head_like:
                M = self.sk.head_R @ M
            r = np.array(s["r"], float) * np.array(g)
            if "abs" in s["c"]:
                sc = self.sk.sc
                r = r * np.array([1.0, sc.get("torso_length", 1.0), sc.get("height", 1.0)])
            if head_like:
                r = r * self.sk.head_scale
            return Prim(name, comp, "ell", bone, s.get("op", "add"), k, c, M, r=r)
        a = self._pt(s["a"], side)
        b = self._pt(s["b"], side)
        L = float(np.linalg.norm(b - a))
        M = frame_from_axis(b - a)
        hs = self.sk.head_scale if head_like else 1.0
        return Prim(name, comp, "cone", bone, s.get("op", "add"), k, a, M, L=L,
                    r1=s["ra"] * g[0] * hs, r2=s["rb"] * g[0] * hs,
                    flat=tuple(s.get("flat", (1.0, 1.0))))

    # --- evaluación
    def posed_aabb(self, prim, B):
        lo, hi = prim.aabb()
        corners = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
        p0, P, R = B[prim.bone]
        w = P + (corners - p0) @ R.T
        m = prim.k + 1e-3
        return w.min(0) - m, w.max(0) + m

    def eval_points(self, pts, comps=COMPONENTS, pose=None, B=None):
        """SDF en puntos arbitrarios (N,3). Devuelve dict comp → distancias."""
        B = B or self.sk.bones(pose)
        pts = np.asarray(pts, float)
        out = {c: np.full(len(pts), 1.0) for c in comps}
        for pr in self.prims:
            if pr.comp not in out:
                continue
            lo, hi = self.posed_aabb(pr, B)
            sel = np.nonzero(np.all((pts >= lo) & (pts <= hi), 1))[0]
            if len(sel) == 0:
                continue
            p0, P, R = B[pr.bone]
            pn = p0 + (pts[sel] - P) @ R
            d = pr.sdf(pn)
            cur = out[pr.comp][sel]
            if pr.op == "add":
                out[pr.comp][sel] = smin(cur, d, pr.k)
            else:
                out[pr.comp][sel] = smax(cur, -d, pr.k)
        return out

    def eval_grid(self, origin, h, shape, comps=COMPONENTS, pose=None, B=None):
        """SDF en una rejilla regular (x, y, z). Devuelve dict comp → array 3D."""
        B = B or self.sk.bones(pose)
        origin = np.asarray(origin, float)
        shape = tuple(int(s) for s in shape)
        axes = [origin[i] + h * np.arange(shape[i]) for i in range(3)]
        out = {c: np.full(shape, 1.0) for c in comps}
        for pr in self.prims:
            if pr.comp not in out:
                continue
            lo, hi = self.posed_aabb(pr, B)
            i0 = np.maximum(np.floor((lo - origin) / h).astype(int), 0)
            i1 = np.minimum(np.ceil((hi - origin) / h).astype(int) + 1, shape)
            if np.any(i1 <= i0):
                continue
            gx, gy, gz = np.meshgrid(axes[0][i0[0]:i1[0]], axes[1][i0[1]:i1[1]], axes[2][i0[2]:i1[2]],
                                     indexing="ij")
            pts = np.stack([gx.ravel(), gy.ravel(), gz.ravel()], 1)
            p0, P, R = B[pr.bone]
            pn = p0 + (pts - P) @ R
            d = pr.sdf(pn).reshape(gx.shape)
            blk = out[pr.comp][i0[0]:i1[0], i0[1]:i1[1], i0[2]:i1[2]]
            if pr.op == "add":
                blk[...] = smin(blk, d, pr.k)
            else:
                blk[...] = smax(blk, -d, pr.k)
        return out, axes

    def bounds(self, pose=None, comps=COMPONENTS, pad=0.02):
        B = self.sk.bones(pose)
        los, his = [], []
        for pr in self.prims:
            if pr.comp in comps and pr.op == "add":
                lo, hi = self.posed_aabb(pr, B)
                los.append(lo)
                his.append(hi)
        lo = np.min(los, 0) - pad
        hi = np.max(his, 0) + pad
        lo[2] = max(lo[2], -0.01)
        return lo, hi


def union(fields, k=0.0):
    it = iter(fields)
    d = next(it).copy()
    for f in it:
        d = smin(d, f, k) if k > 0 else np.minimum(d, f)
    return d
