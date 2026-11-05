# Medidas y validación — v07

| Medida | Objetivo (m) | Malla (m) | Desv. | OK |
|---|---:|---:|---:|:-:|
| Largo cabeza-cuerpo (nariz→base cola, horizontal) | 1.500 | 1.473 | -1.8 % | ✔ |
| Altura a la cruz | 0.720 | 0.703 | -2.3 % | ✔ |
| Altura a la grupa | 0.700 | 0.691 | -1.3 % | ✔ |
| Largo de cola (arco) | 0.550 | 0.562 | +2.1 % | ✔ |
| Largo de cabeza (nariz→occipucio) | 0.290 | 0.293 | +1.1 % | ✔ |
| Ancho de cabeza (cigomático) | 0.220 | 0.219 | -0.3 % | ✔ |
| Profundidad de pecho (cruz→esternón) | 0.390 | 0.364 | -6.8 % | ✔ |
| Altura libre bajo el pecho | 0.330 | 0.340 | +3.0 % | ✔ |
| Altura libre en el ijar (remetido) | 0.370 | 0.386 | +4.3 % | ✔ |
| Ancho máximo del tronco (costillar) | 0.320 | 0.308 | -3.6 % | ✔ |
| Ancho zarpa delantera | 0.110 | 0.106 | -3.9 % | ✔ |
| Ancho zarpa trasera | 0.095 | 0.096 | +0.8 % | ✔ |
| Grosor antebrazo (fondo, z≈0.185) | 0.095 | 0.099 | +4.3 % | ✔ |
| Diámetro cola cerca de la base | 0.075 | 0.075 | +0.0 % | ✔ |

Cabeza = 19.9 % del cabeza-cuerpo; cola = 38.1 %; distancia entre zarpas (del./tras.) = 0.791 m; largo total bbox = 1.593 m; cabeza-cuerpo por el contorno dorsal = 1.969 m; masa estimada (vol. × 1040 kg/m³) = 99 kg


Masa por volumen real de la unión de la escultura (sin solapes): 98.2 kg a 1000 kg/m³ (102.2 kg a 1040 kg/m³); volumen 0.0982 m³.

IoU de la malla final posada como en las fotos: lateral 0.782, frontal 0.832.

| Objeto | Quads | Tris | N-gons | No-manifold | Bordes abiertos | Vért. sueltos | Normales incoherentes | Normales afuera | Auto-intersec. | Caras colapsadas | Ángulos [p1, p99] | Ángulos fuera de 25–155° |
|---|---:|---:|---:|---:|---:|---:|---:|:-:|---:|---:|---:|---:|
| Jaguar_Body | 5344 | 0 | 0 | 0 | 0 | 0 | 0 | sí | 110 | 0 | [39°, 140°] | 128 |
| Jaguar_Head | 2832 | 0 | 0 | 0 | 0 | 0 | 0 | sí | 141 | 0 | [39°, 136°] | 80 |
| Jaguar_LowerJaw | 912 | 0 | 0 | 0 | 0 | 0 | 0 | sí | 0 | 0 | [24°, 151°] | 62 |
| Jaguar_EarL | 384 | 0 | 0 | 0 | 0 | 0 | 0 | sí | 0 | 0 | [61°, 118°] | 0 |
| Jaguar_EarR | 384 | 0 | 0 | 0 | 0 | 0 | 0 | sí | 0 | 0 | [61°, 118°] | 0 |
| Jaguar_EyeL | 216 | 0 | 0 | 0 | 0 | 0 | 0 | sí | 0 | 0 | [69°, 119°] | 0 |
| Jaguar_EyeR | 216 | 0 | 0 | 0 | 0 | 0 | 0 | sí | 0 | 0 | [69°, 119°] | 0 |
| **Total** | **10288** | | | | | | | | | | | |
