"""Ajuste de la escultura contra las siluetas de las fotos (CMA-ES).

Optimiza, por etapas:
  A) pose de la foto lateral + escalas del esqueleto        → IoU lateral
  B) tamaños de los grupos musculares + escalas             → IoU lateral + frontal
     con restricciones: medidas en pose neutra dentro de ±8 % de medidas.md,
     masa 80–95 kg, escalas del esqueleto dentro de ±12 %
  C) pose de la foto frontal + cámara frontal               → IoU frontal
Cada evaluación: rejilla SDF gruesa → marching cubes → rasterizado (sin
renders). Guarda el mejor conjunto en params.json y el registro en
logs/fit_<tag>.jsonl.

Uso:  python src/fit_silhouette.py --stages A B C B --evals 400 --tag v07
"""
import argparse
import copy
import json
import math
import os
import sys
import time

import numpy as np

SRC = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SRC)
ROOT = os.path.dirname(SRC)

import sdf as sdfmod  # noqa: E402
import silhouette as sil  # noqa: E402

DENSITY = 1000.0  # kg/m³ (cuerpo entero con pulmones ≈ agua; ver bitácora)
MASS_RANGE = (80.0, 95.0)
TOL = 0.08

LEGS_SIDE = ["scap_top_L", "shoulder_L", "elbow_L", "carpus_L", "scap_top_R", "shoulder_R", "elbow_R",
             "carpus_R", "hip_L", "knee_L", "hock_L", "hip_R", "knee_R", "hock_R"]
TAILS = ["tail%d" % i for i in range(6)]
GROUPS_XZ = ["chest", "loin", "belly", "croup", "neck"]
GROUPS_U = ["back", "fold", "shoulder", "arm", "forearm", "thigh", "shank", "paw_f", "paw_h", "tail",
            "muzzle", "jaw", "tuck"]


# regiones de la foto lateral reflejada (px originales) para ajustar la pose por
# zonas: un IoU global diluye los errores de piezas finas (patas, cola)
REGIONS = {
    "tail": ((1530, 1965, 320, 690), TAILS),
    "front_legs": ((230, 860, 630, 1010), ["scap_top_L", "shoulder_L", "elbow_L", "carpus_L",
                                          "scap_top_R", "shoulder_R", "elbow_R", "carpus_R"]),
    "hind_legs": ((1010, 1650, 630, 1010), ["hip_L", "knee_L", "hock_L", "hip_R", "knee_R", "hock_R"]),
    "head": ((140, 560, 240, 620), ["neck1", "neck2", "head"]),
}


def param_space(stage):
    if stage.startswith("P:"):
        reg = stage[2:]
        lim = 70.0 if reg == "tail" else 45.0
        return [("pose_side", j, -lim, lim) for j in REGIONS[reg][1]]
    ps = []
    if stage in ("A", "B"):
        ps += [("scale", "height", 0.92, 1.08), ("scale", "torso_length", 0.88, 1.12),
               ("scale", "neck_length", 0.88, 1.12), ("scale", "head", 0.90, 1.10),
               ("scale", "head_pitch", -8.0, 8.0)]
    if stage == "A":
        for j in LEGS_SIDE:
            ps.append(("pose_side", j, -45.0, 45.0))
        for j in ("neck1", "neck2", "head"):
            ps.append(("pose_side", j, -25.0, 25.0))
        for j in TAILS:
            ps.append(("pose_side", j, -70.0, 70.0))
    if stage == "B":
        for g in GROUPS_XZ:
            ps += [("group_x", g, 0.75, 1.30), ("group_z", g, 0.75, 1.30)]
        for g in GROUPS_U:
            lo, hi = (0.4, 1.8) if g in ("fold", "tuck") else (0.75, 1.30)
            ps.append(("group_u", g, lo, hi))
    if stage == "C":
        for j in ("shoulder_L", "elbow_L", "carpus_L", "shoulder_R", "elbow_R", "carpus_R",
                  "hip_L", "hip_R", "neck1", "head"):
            ps.append(("pose_front", j, -35.0, 35.0))
        for k, (lo, hi) in sil.FRONT_CAM_BOUNDS.items():
            ps.append(("cam", k, lo, hi))
    return ps


class State:
    """Conjunto de parámetros ajustables (lo que se guarda en params.json)."""

    def __init__(self, P):
        S = P["skeleton"]
        self.scales = dict(S.get("scales", {}))
        self.groups = {k: list(v) for k, v in P["sculpt"].get("groups", {}).items()}
        self.pose_side = dict(P["poses"]["side_photo"])
        self.pose_front = dict(P["poses"]["front_photo"])
        self.cam = dict(P.get("fit", {}).get("front_cam", sil.FRONT_CAM0))

    def get(self, kind, key):
        if kind == "scale":
            return self.scales.get(key, 0.0 if key == "head_pitch" else 1.0)
        if kind in ("group_x", "group_z", "group_u"):
            g = self.groups.get(key, [1.0, 1.0, 1.0])
            return g[0] if kind != "group_z" else g[2]
        if kind == "pose_side":
            return self.pose_side.get(key, 0.0)
        if kind == "pose_front":
            return self.pose_front.get(key, 0.0)
        return self.cam[key]

    def set(self, kind, key, v):
        v = float(v)
        if kind == "scale":
            self.scales[key] = v
        elif kind in ("group_x", "group_z", "group_u"):
            g = self.groups.setdefault(key, [1.0, 1.0, 1.0])
            if kind == "group_x":
                g[0] = v
            elif kind == "group_z":
                g[2] = v
            else:
                g[0] = g[1] = g[2] = v
        elif kind == "pose_side":
            self.pose_side[key] = v
        elif kind == "pose_front":
            self.pose_front[key] = v
        else:
            self.cam[key] = v

    def write(self, P):
        P["skeleton"]["scales"] = {k: round(v, 5) for k, v in self.scales.items()}
        P["sculpt"]["groups"] = {k: [round(x, 5) for x in v] for k, v in self.groups.items()}
        P["poses"]["side_photo"] = {k: round(v, 3) for k, v in self.pose_side.items()}
        P["poses"]["front_photo"] = {k: round(v, 3) for k, v in self.pose_front.items()}
        P.setdefault("fit", {})["front_cam"] = {k: round(v, 5) for k, v in self.cam.items()}


# ------------------------------------------------------------ evaluación
class Evaluator:
    def __init__(self, P, h=0.012):
        self.P = P
        self.h = h
        self.ref_side = sil.load_ref("side")
        self.ref_front = sil.load_ref("front")
        T = P["targets"]
        self.targets = {k: v for k, v in T.items() if not k.startswith("_")}

    def model(self, st):
        return sdfmod.JaguarSDF(self.P, scales=st.scales, groups=st.groups)

    def union_mesh(self, M, pose, h=None):
        from skimage.measure import marching_cubes
        h = h or self.h
        B = M.sk.bones(pose)
        lo, hi = M.bounds(pose, pad=2 * h)
        shape = np.ceil((hi - lo) / h).astype(int) + 1
        F, _ = M.eval_grid(lo, h, shape, B=B)
        d = np.minimum.reduce([F[c] for c in F]).astype(np.float32)
        if lo[2] < 0:
            kz = int(np.ceil(-lo[2] / h))
            d[:, :, :kz] = np.maximum(d[:, :, :kz], 0.001)
        V, Fc, _, _ = marching_cubes(d, 0.0, spacing=(h, h, h))
        return V + lo, Fc, F, lo

    def side(self, M, st, keep=False, region=None):
        pose = st.pose_side
        V, Fc, _, _ = self.union_mesh(M, pose)
        pts = M.sk.posed_points(pose)
        nose_y = V[:, 1].min()
        tail_y = pts["tail_base"][1]
        P2, s = sil.project_side(V, self.ref_side, nose_y, tail_y)
        m = sil.raster(P2, Fc, self.ref_side["shape"])
        ref = self.ref_side["mask_arr"]
        if region:
            k = self.ref_side["scale"]
            x0, x1, y0, y1 = [int(v * k) for v in region]
            iou = sil.iou(m[y0:y1, x0:x1], ref[y0:y1, x0:x1])
        else:
            iou = sil.iou(m, ref)
        return (iou, m) if keep else iou

    def front(self, M, st, keep=False):
        V, Fc, _, _ = self.union_mesh(M, st.pose_front)
        m = sil.raster(sil.project_persp(V, st.cam, self.ref_front["shape"]), Fc, self.ref_front["shape"])
        iou = sil.iou(m, self.ref_front["mask_arr"])
        return (iou, m) if keep else iou

    def measures(self, M):
        """Medidas en pose neutra a partir de la escultura (aprox. a la rejilla)."""
        V, Fc, F, lo = self.union_mesh(M, {})
        h = self.h
        pts = M.sk.posed_points({})
        occ = np.zeros_like(F["body"], bool)
        for d in F.values():
            occ |= d < 0
        mass = occ.sum() * h ** 3 * DENSITY
        pf = (pts["mcp_L"] + pts["ftoe_L"]) / 2
        ph = (pts["mtp_L"] + pts["htoe_L"]) / 2
        x, y, z = V[:, 0], V[:, 1], V[:, 2]
        mid = np.abs(x) < 0.05
        withers = z[y < 0].max()
        croup = z[y > 0.15].max()
        sel = mid & (y > pf[1] - 0.10) & (y < pf[1] + 0.22) & (z > 0.15)
        chest_clear = z[sel].min() if sel.any() else 0.0
        sel = mid & (np.abs(y - (ph[1] - 0.28)) < 0.03) & (z > 0.15)
        belly = z[sel].min() if sel.any() else 0.0
        sel = (y > pf[1] - 0.05) & (y < ph[1] - 0.15) & (z > chest_clear + 0.05)
        torso_w = 2 * np.abs(x[sel]).max() if sel.any() else 0.0
        nose = V[np.argmin(y)]
        sel = (z < 0.05) & (np.abs(y - pf[1]) < 0.08) & (x > 0)
        paw_f = np.ptp(x[sel]) if sel.any() else 0.0
        sel = (z < 0.05) & (np.abs(y - ph[1]) < 0.08) & (x > 0)
        paw_h = np.ptp(x[sel]) if sel.any() else 0.0
        sel = (z > 0.175) & (z < 0.195) & (x > 0.04) & (np.abs(y - pts["carpus_L"][1]) < 0.12)
        fore = np.ptp(y[sel]) if sel.any() else 0.0
        # cabeza (componente head): ancho
        hd = F["head"] < 0
        ii = np.nonzero(hd.any(axis=(1, 2)))[0]
        head_w = (ii.max() - ii.min() + 1) * h if len(ii) else 0.0
        tg = M.groups.get("tail", [1, 1, 1])[0]
        m = {
            "head_body_length": pts["tail_base"][1] - nose[1],
            "withers_height": withers, "croup_height": croup,
            "tail_length": M.sk.S["tail"]["length"],
            "head_length": float(np.linalg.norm(nose - pts["occiput"])),
            "head_width": head_w, "chest_depth": withers - chest_clear,
            "chest_clearance": chest_clear, "belly_clearance": belly, "torso_width": torso_w,
            "front_paw_width": paw_f, "hind_paw_width": paw_h, "forearm_depth": fore,
            "tail_base_diameter": 2 * 0.0405 * tg,
        }
        return m, mass

    def penalty(self, m, mass):
        pen = 0.0
        worst = 0.0
        for k, t in self.targets.items():
            if k not in m or t == 0:
                continue
            dev = abs(m[k] - t) / t
            worst = max(worst, dev)
            if dev > TOL:
                pen += 4.0 * (dev - TOL) + 40.0 * (dev - TOL) ** 2
        lo, hi = MASS_RANGE
        if mass < lo:
            pen += 0.02 * (lo - mass)
        elif mass > hi:
            pen += 0.02 * (mass - hi)
        return pen, worst


def run_stage(P, st, ev, stage, evals, log, seed=1):
    import cma
    space = param_space(stage)
    lo = np.array([s[2] for s in space])
    hi = np.array([s[3] for s in space])
    x0 = np.array([np.clip((st.get(s[0], s[1]) - s[2]) / (s[3] - s[2]), 0, 1) for s in space])

    def apply(x, target):
        x = np.clip(x, 0, 1)
        for (kind, key, a, b), v in zip(space, x):
            target.set(kind, key, a + v * (b - a))

    best = {"f": 1e9}
    t0 = time.time()
    count = [0]

    def f(x):
        s2 = copy.deepcopy(st)
        apply(x, s2)
        M = ev.model(s2)
        out = {}
        if stage.startswith("P:"):
            out["region"] = ev.side(M, s2, region=REGIONS[stage[2:]][0])
            pen, worst, mass = 0.0, 0.0, 0.0
            val = -out["region"]
        elif stage == "A":
            out["side"] = ev.side(M, s2)
            m, mass = ev.measures(M)
            pen, worst = ev.penalty(m, mass)
            pen *= 0.25  # en A sólo vigila que el esqueleto no se dispare
            val = -out["side"] + pen
        elif stage == "B":
            out["side"] = ev.side(M, s2)
            out["front"] = ev.front(M, s2)
            m, mass = ev.measures(M)
            pen, worst = ev.penalty(m, mass)
            val = -(0.7 * out["side"] + 0.3 * out["front"]) + pen
        else:
            out["front"] = ev.front(M, s2)
            pen, worst, mass = 0.0, 0.0, 0.0
            val = -out["front"]
        count[0] += 1
        if val < best["f"]:
            best.update(f=val, x=x.copy(), out=out, pen=pen, worst=worst, mass=mass)
        return val

    opts = {"bounds": [0, 1], "maxfevals": evals, "verbose": -9, "seed": seed,
            "popsize": max(10, 4 + int(3 * math.log(len(space))))}
    es = cma.CMAEvolutionStrategy(x0, 0.12, opts)
    gen = 0
    while not es.stop():
        X = es.ask()
        es.tell(X, [f(x) for x in X])
        gen += 1
        rec = {"stage": stage, "gen": gen, "evals": count[0], "best_f": best["f"],
               "best": {k: round(v, 4) for k, v in best.get("out", {}).items()},
               "pen": round(best.get("pen", 0), 4), "worst_dev": round(best.get("worst", 0), 4),
               "mass": round(best.get("mass", 0), 1), "t": round(time.time() - t0, 1)}
        log.write(json.dumps(rec) + "\n")
        log.flush()
        if gen % 5 == 0:
            print(rec, flush=True)
    apply(best["x"], st)
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stages", nargs="+", default=["A", "B", "C", "B"])
    ap.add_argument("--evals", type=int, default=400)
    ap.add_argument("--tag", default="v07")
    ap.add_argument("--h", type=float, default=0.012)
    ap.add_argument("--params", default=os.path.join(SRC, "params.json"))
    a = ap.parse_args()
    with open(a.params, encoding="utf-8") as fh:
        P = json.load(fh)
    st = State(P)
    ev = Evaluator(P, a.h)
    os.makedirs(os.path.join(ROOT, "logs"), exist_ok=True)
    logp = os.path.join(ROOT, "logs", "fit_%s.jsonl" % a.tag)
    with open(logp, "a") as log:
        M = ev.model(st)
        m, mass = ev.measures(M)
        rec0 = {"stage": "start", "side": ev.side(M, st), "front": ev.front(M, st), "mass": mass,
                "measures": {k: round(float(v), 4) for k, v in m.items()}}
        log.write(json.dumps(rec0) + "\n")
        print(rec0, flush=True)
        for i, stage in enumerate(a.stages):
            best = run_stage(P, st, ev, stage, a.evals, log, seed=1 + i)
            st.write(P)
            with open(a.params, "w", encoding="utf-8") as fh:
                json.dump(P, fh, indent=1)
            M = ev.model(st)
            m, mass = ev.measures(M)
            rec = {"stage": stage, "done": True, "side": ev.side(M, st), "front": ev.front(M, st),
                   "mass": mass, "measures": {k: round(float(v), 4) for k, v in m.items()}}
            log.write(json.dumps(rec) + "\n")
            log.flush()
            print("STAGE", stage, rec, flush=True)


if __name__ == "__main__":
    main()
