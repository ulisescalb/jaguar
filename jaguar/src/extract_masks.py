"""Extrae máscaras de silueta de las fotos de referencia (fondo blanco).

Uso (venv con opencv-python-headless):
    python src/extract_masks.py
Genera reference/masks/<nombre>_mask.png (blanco = animal) y
reference/masks/<nombre>_check.jpg (contorno sobre la foto, para revisar a ojo).

Método: semilla por color (pelaje anaranjado/negro = primer plano seguro; casi
blanco puro = fondo seguro) + GrabCut para resolver el pelaje blanco del vientre
y patas frente a la sombra gris del suelo. Luego se queda la componente conexa
mayor y se rellenan huecos.
"""
import os
import sys

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF = os.path.join(ROOT, "reference")
OUT = os.path.join(REF, "masks")

# fotos utilizables y franja inferior a ignorar (sombra en el suelo, px)
PHOTOS = {
    "side": ("photo_side_walk.jpg", {}),
    "front": ("photo_front_walk.jpg", {}),
}


def fill_holes(m):
    h, w = m.shape
    ff = m.copy()
    mask = np.zeros((h + 2, w + 2), np.uint8)
    cv2.floodFill(ff, mask, (0, 0), 255)
    return m | cv2.bitwise_not(ff)


def largest_component(m):
    n, lab, stats, _ = cv2.connectedComponentsWithStats(m, 8)
    if n <= 1:
        return m
    k = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    return np.where(lab == k, 255, 0).astype(np.uint8)


def extract(path):
    img = cv2.imread(path)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    s = hsv[..., 1].astype(np.float32) / 255
    v = hsv[..., 2].astype(np.float32) / 255
    mn = img.min(axis=2)
    gc = np.full(img.shape[:2], cv2.GC_PR_BGD, np.uint8)
    # primer plano probable: algo de color o algo oscuro
    gc[(s > 0.12) | (v < 0.80)] = cv2.GC_PR_FGD
    # primer plano seguro: pelaje claramente saturado u oscuro (rosetas)
    fg = ((s > 0.30) | (v < 0.35)).astype(np.uint8)
    fg = cv2.erode(fg, np.ones((5, 5), np.uint8))
    gc[fg > 0] = cv2.GC_FGD
    # fondo seguro: casi blanco puro
    bg = (mn > 238).astype(np.uint8)
    bg = cv2.erode(bg, np.ones((7, 7), np.uint8))
    gc[bg > 0] = cv2.GC_BGD
    bgm = np.zeros((1, 65), np.float64)
    fgm = np.zeros((1, 65), np.float64)
    cv2.grabCut(img, gc, None, bgm, fgm, 6, cv2.GC_INIT_WITH_MASK)
    m = np.where((gc == cv2.GC_FGD) | (gc == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    m = largest_component(m)
    m = fill_holes(m)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    return img, m


def main():
    os.makedirs(OUT, exist_ok=True)
    names = sys.argv[1:] or list(PHOTOS)
    for name in names:
        fn, _ = PHOTOS[name]
        img, m = extract(os.path.join(REF, fn))
        cv2.imwrite(os.path.join(OUT, name + "_mask.png"), m)
        chk = img.copy()
        cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        cv2.drawContours(chk, cnts, -1, (255, 0, 255), 3)
        tint = chk.copy()
        tint[m == 0] = (tint[m == 0] * 0.5 + np.array([255, 160, 0]) * 0.5).astype(np.uint8)
        cv2.imwrite(os.path.join(OUT, name + "_check.jpg"), tint, [cv2.IMWRITE_JPEG_QUALITY, 85])
        ys, xs = np.nonzero(m)
        print(name, "bbox x[%d,%d] y[%d,%d] area %d" % (xs.min(), xs.max(), ys.min(), ys.max(), len(xs)))


if __name__ == "__main__":
    main()
