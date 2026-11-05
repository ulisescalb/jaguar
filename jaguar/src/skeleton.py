"""Esqueleto de referencia del jaguar (landmarks 3D) y cinemática directa.

Los landmarks de la pose neutra (de pie) están en params.json["skeleton"], en
el mismo marco que la malla: metros, Z arriba, el animal mira a −Y, +X es su
lado IZQUIERDO, origen en el suelo entre las zarpas. Los del lado derecho se
generan por simetría (sufijo _R).

Poses: rotaciones en el plano sagital (eje X) en cada articulación, en grados.
Convención: ángulo > 0 lleva el segmento distal hacia atrás (+Y) cuando el
hueso apunta hacia abajo, y la nariz hacia abajo en la cabeza.

Sólo depende de numpy: funciona dentro de Blender y fuera.
"""
import json
import math

import numpy as np

# cadenas articuladas: (nombre de la cadena, lista de landmarks proximal→distal,
# nombres de los huesos, uno por tramo)
FRONT = ["scap_top", "shoulder", "elbow", "carpus", "mcp", "ftoe"]
FRONT_BONES = ["scapula", "humerus", "radius", "metacarpus", "fdigits"]
HIND = ["hip", "knee", "hock", "mtp", "htoe"]
HIND_BONES = ["femur", "tibia", "metatarsus", "hdigits"]
NECK = ["T1", "C4", "C1"]
NECK_BONES = ["neck1", "neck2"]
TAIL_N = 6

DESCRIPTIONS = {
    "scap_top": "Escápula, borde dorsal (cruz)", "scap_low": "Escápula, borde inferior (cuello de la escápula)",
    "shoulder": "Articulación del hombro (glenohumeral)", "elbow": "Codo (articulación húmero-cúbito)",
    "olecranon": "Olécranon (punta del codo)", "carpus": "Muñeca (carpo)",
    "mcp": "Metacarpo-falángica", "ftoe": "Punta de los dedos delanteros",
    "iliac_crest": "Cresta ilíaca (tuber coxae)", "hip": "Cadera (acetábulo)",
    "ischium": "Tuberosidad isquiática (punta de la nalga)", "knee": "Rodilla (babilla)",
    "patella": "Rótula", "hock": "Corvejón (articulación tarsal)", "calcaneus": "Calcáneo (punta del corvejón)",
    "mtp": "Metatarso-falángica", "htoe": "Punta de los dedos traseros",
    "withers": "Cruz (piel sobre las escápulas)", "T1": "Primera torácica", "T5": "T5 (bajo la cruz)",
    "T10": "T10", "T13": "T13 (última torácica)", "L4": "Lomo (L4)", "L7": "L7", "sacrum": "Sacro",
    "C1": "Atlas (C1)", "C2": "Axis (C2)", "C3": "C3", "C4": "C4", "C5": "C5", "C6": "C6", "C7": "C7",
    "tail_base": "Base de la cola (Ca1)", "tail_tip": "Punta de la cola",
    "condyle": "Cóndilos occipitales (pivote de la cabeza)", "occiput": "Occipucio (cresta occipital)",
    "orbit": "Centro de la órbita", "nose_tip": "Punta nasal (rinario)",
    "jaw_hinge": "Bisagra de la mandíbula (ATM)", "chin": "Barbilla (sínfisis mandibular)",
    "zygoma": "Arco cigomático (máximo ancho)", "ear_base": "Base de la oreja",
}


def _rx(deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def mirror(p):
    return np.array([-p[0], p[1], p[2]])


class Skeleton:
    """Landmarks neutros + transformaciones rígidas por hueso para una pose."""

    def __init__(self, S, scales=None):
        sc = dict(S.get("scales", {}))
        if scales:
            sc.update(scales)
        self.S = S
        self.sc = sc
        pts = {k: np.array(v, float) for k, v in S["points"].items()}
        # escalas globales (las ajusta el optimizador dentro de ±12 %)
        sz = sc.get("height", 1.0)          # alturas respecto al suelo
        sy = sc.get("torso_length", 1.0)    # largo del tronco respecto al centro
        sneck = sc.get("neck_length", 1.0)
        shead = sc.get("head", 1.0)
        for k in pts:
            pts[k][2] *= sz
            pts[k][1] *= sy
        # cuello: alarga/acorta C1 respecto a T1 y arrastra la cabeza
        neck_keys = [k for k in pts if k in ("C1", "C2", "C3", "C4", "C5", "C6", "C7")]
        t1 = pts["T1"].copy()
        c1_old = pts["C1"].copy()
        for k in neck_keys:
            pts[k] = t1 + (pts[k] - t1) * sneck
        dneck = pts["C1"] - c1_old
        # cabeza: marco local (origen en el cóndilo) con inclinación
        H = S["head"]
        self.head_pitch = H["pitch_deg"] + sc.get("head_pitch", 0.0)
        cond = np.array(H["condyle"], float)
        cond[2] *= sz
        cond[1] *= sy
        cond = cond + dneck
        self.head_origin = cond
        Rh = _rx(self.head_pitch)
        for k, v in H["local"].items():
            pts[k] = cond + Rh @ (np.array(v, float) * shead)
        pts["condyle"] = cond
        self.head_scale = shead
        self.head_R = Rh
        # cola: cadena desde Ca1 con ángulos por segmento
        T = S["tail"]
        self.tail_seg = T["length"] / TAIL_N
        self.tail_neutral = list(T["angles_neutral"])
        self.pts = pts
        self._add_mirrors()

    def _add_mirrors(self):
        for k in list(self.pts):
            if k.endswith("_L"):
                self.pts[k[:-2] + "_R"] = mirror(self.pts[k])

    # ------------------------------------------------------------- poses
    def tail_points(self, angles):
        """Puntos de la cola: desde la base, dirección inicial hacia atrás (+Y);
        cada ángulo dobla el segmento siguiente (>0 hacia abajo)."""
        p = self.pts["tail_base"].copy()
        out = [p.copy()]
        heading = 0.0
        for a in angles:
            heading += a
            d = np.array([0.0, math.cos(math.radians(heading)), -math.sin(math.radians(heading))])
            p = p + d * self.tail_seg
            out.append(p.copy())
        return out

    def bones(self, pose=None):
        """Devuelve {hueso: (pivote_neutro, pivote_posado, R)} para la pose.

        Un punto p unido al hueso b se mueve a P + R (p − p0)."""
        pose = pose or {}
        out = {"torso": (np.zeros(3), np.zeros(3), np.eye(3))}
        for side in ("L", "R"):
            for chain, names in ((FRONT, FRONT_BONES), (HIND, HIND_BONES)):
                joints = [j + "_" + side for j in chain]
                R = np.eye(3)
                P = self.pts[joints[0]].copy()
                for i, b in enumerate(names):
                    j0, j1 = joints[i], joints[i + 1]
                    R = R @ _rx(pose.get(chain[i] + "_" + side, 0.0))
                    out[b + "_" + side] = (self.pts[j0].copy(), P.copy(), R.copy())
                    P = P + R @ (self.pts[j1] - self.pts[j0])
        # cuello y cabeza
        R = np.eye(3)
        P = self.pts["T1"].copy()
        for i, b in enumerate(NECK_BONES):
            j0, j1 = NECK[i], NECK[i + 1]
            R = R @ _rx(pose.get(b, 0.0))  # >0 baja el cuello
            out[b] = (self.pts[j0].copy(), P.copy(), R.copy())
            P = P + R @ (self.pts[j1] - self.pts[j0])
        # la cabeza pivota en el cóndilo (unido rígidamente a C1)
        cond_posed = P + R @ (self.pts["condyle"] - self.pts["C1"])
        Rh = R @ _rx(pose.get("head", 0.0))
        out["head"] = (self.pts["condyle"].copy(), cond_posed, Rh)
        hinge = self.pts["jaw_hinge_L"].copy()
        hinge[0] = 0.0
        Rj = Rh @ _rx(pose.get("jaw", 0.0))
        out["jaw"] = (hinge, cond_posed + Rh @ (hinge - self.pts["condyle"]), Rj)
        # cola
        neutral = self.tail_points(self.tail_neutral)
        ang = [a + pose.get("tail%d" % i, 0.0) for i, a in enumerate(self.tail_neutral)]
        posed = self.tail_points(ang)
        acc_n = acc_p = 0.0
        for i in range(TAIL_N):
            acc_n += self.tail_neutral[i]
            acc_p += ang[i]
            R = _rx(-(acc_p - acc_n))
            out["tail%d" % i] = (neutral[i], posed[i], R)
        return out

    def posed_points(self, pose=None):
        """Landmarks transformados por la pose (cada uno con su hueso)."""
        B = self.bones(pose)
        attach = landmark_bones()
        out = {}
        for k, p in self.pts.items():
            b = attach.get(k)
            if b is None:
                out[k] = p.copy()
                continue
            p0, P, R = B[b]
            out[k] = P + R @ (p - p0)
        tp = self.tail_points([a + (pose or {}).get("tail%d" % i, 0.0)
                               for i, a in enumerate(self.tail_neutral)])
        out["tail_tip"] = tp[-1]
        return out


def landmark_bones():
    """Hueso al que va unido cada landmark (para posar)."""
    m = {}
    for side in ("L", "R"):
        m.update({"shoulder_" + side: "scapula_" + side, "scap_low_" + side: "scapula_" + side,
                  "elbow_" + side: "humerus_" + side, "olecranon_" + side: "radius_" + side,
                  "carpus_" + side: "radius_" + side, "mcp_" + side: "metacarpus_" + side,
                  "ftoe_" + side: "fdigits_" + side, "knee_" + side: "femur_" + side,
                  "patella_" + side: "femur_" + side, "hock_" + side: "tibia_" + side,
                  "calcaneus_" + side: "metatarsus_" + side, "mtp_" + side: "metatarsus_" + side,
                  "htoe_" + side: "hdigits_" + side})
        for k in ("orbit", "jaw_hinge", "zygoma", "ear_base"):
            m[k + "_" + side] = "head"
    for k in ("C7", "C6", "C5", "C4"):
        m[k] = "neck1"
    for k in ("C3", "C2", "C1"):
        m[k] = "neck2"
    for k in ("condyle", "occiput", "nose_tip"):
        m[k] = "head"
    m["chin"] = "jaw"
    return m


PARENTS = {
    "T1": None, "T5": "T1", "T10": "T5", "T13": "T10", "L4": "T13", "L7": "L4", "sacrum": "L7",
    "tail_base": "sacrum", "tail_tip": "tail_base",
    "C7": "T1", "C6": "C7", "C5": "C6", "C4": "C5", "C3": "C4", "C2": "C3", "C1": "C2",
    "condyle": "C1", "occiput": "condyle", "nose_tip": "condyle", "chin": "jaw_hinge_L",
    "withers": "T5", "iliac_crest": "sacrum", "hip": "sacrum", "ischium": "sacrum",
}
for _s in ("L", "R"):
    PARENTS.update({
        "scap_top_" + _s: "T5", "scap_low_" + _s: "scap_top_" + _s, "shoulder_" + _s: "scap_top_" + _s,
        "elbow_" + _s: "shoulder_" + _s, "olecranon_" + _s: "elbow_" + _s,
        "carpus_" + _s: "elbow_" + _s, "mcp_" + _s: "carpus_" + _s, "ftoe_" + _s: "mcp_" + _s,
        "iliac_crest_" + _s: "sacrum", "hip_" + _s: "sacrum", "ischium_" + _s: "hip_" + _s,
        "knee_" + _s: "hip_" + _s, "patella_" + _s: "knee_" + _s, "hock_" + _s: "knee_" + _s,
        "calcaneus_" + _s: "hock_" + _s, "mtp_" + _s: "hock_" + _s, "htoe_" + _s: "mtp_" + _s,
        "orbit_" + _s: "condyle", "jaw_hinge_" + _s: "condyle", "zygoma_" + _s: "condyle",
        "ear_base_" + _s: "condyle",
    })


def export_landmarks(sk, path, offset=None, poses=None):
    """Escribe landmarks.json (pose neutra y, opcionalmente, poses de foto)."""
    off = np.zeros(3) if offset is None else np.asarray(offset)
    pts = sk.posed_points({})
    data = {
        "_doc": ("Landmarks anatómicos del jaguar en pose neutra (de pie). Metros, Z arriba, "
                 "el animal mira a -Y, +X = lado izquierdo, origen en el suelo entre las zarpas. "
                 "Mismo marco que export/jaguar_base_*.glb antes de la conversión Y-arriba de glTF. "
                 "'parent' propone la jerarquía para el rig."),
        "units": "m", "up": "Z", "forward": "-Y",
        "landmarks": {},
        "bones": {"front": FRONT_BONES, "hind": HIND_BONES, "neck": NECK_BONES,
                  "tail_segments": TAIL_N},
    }
    for k in sorted(pts):
        base = k[:-2] if k[-2:] in ("_L", "_R") else k
        data["landmarks"][k] = {
            "pos": [round(float(c), 5) for c in (pts[k] - off)],
            "parent": PARENTS.get(k),
            "desc": DESCRIPTIONS.get(base, ""),
        }
    tail = sk.tail_points(sk.tail_neutral)
    data["tail_chain"] = [[round(float(c), 5) for c in (p - off)] for p in tail]
    if poses:
        data["photo_poses_deg"] = poses
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
    return data
