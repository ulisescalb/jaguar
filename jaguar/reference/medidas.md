# Medidas de referencia — Jaguar (*Panthera onca*), macho adulto

No hay fotos en `reference/`, así que las proporciones salen de medidas publicadas
y de la anatomía comparada de félidos. Las que pasaste (cabeza-cuerpo 1.7 m, cruz
0.72 m, cola 0.55 m, cabeza 16–19 %) son correctas para un macho grande. Hay que
corregir **cómo se mide** el largo cabeza-cuerpo cuando el animal está de pie
(ver la corrección 1).

## Rangos de la especie

| Medida | Rango publicado | Valor elegido | Nota |
|---|---|---|---|
| Cabeza-cuerpo (medido sobre el contorno, animal estirado) | 1.12–1.85 m | **1.70 m** | Macho adulto grande (los del Pantanal son los mayores) |
| Altura a la cruz | 0.63–0.76 m | **0.72 m** | |
| Cola | 0.45–0.75 m | **0.55 m** | La más corta de los *Panthera*: ≈ 1/3 del cabeza-cuerpo |
| Peso | 56–96 kg (más de 120 kg en el Pantanal) | ≈ 90–100 kg | Sirve para comprobar el volumen de la malla |
| Cráneo (longitud cóndilo-basal) | 0.22–0.28 m en machos | — | Cráneo muy ancho: ancho cigomático ≈ 0.75–0.8 × largo |

## Correcciones

1. **El largo cabeza-cuerpo de 1.70 m se mide con cinta sobre el contorno dorsal y
   con el animal estirado** (convención de campo y de museo). De pie, con el cuello
   levantado y la cabeza un poco baja, la distancia **recta horizontal** entre la
   punta de la nariz y la base de la cola es bastante menor. En la v01 usé 1.65 m
   en línea recta y el jaguar salió largo y bajo, con aspecto de salchicha. Por eso
   el modelo mide las dos cosas:
   - Recta horizontal nariz → base de la cola: **1.50 m** (≈ 0.88 × 1.70; en
     félidos de pie la relación suele estar entre 0.84 y 0.9).
   - Contorno dorsal sobre la línea media (lo que marcaría una cinta): **1.70 m**.
2. **Cabeza** 0.29 m (nariz → occipucio). Es el 17 % de 1.70 m y el 19 % de
   1.50 m, dentro del 16–19 % que diste.
3. **Cola** 0.55 m medida a lo largo de su eje curvo. La cola relajada cuelga
   formando una «J», así que su extensión en línea recta es menor.

## Objetivos derivados (los que comprueba `src/measure.py`)

| Clave en params.json | Medida | Objetivo | Cómo se mide en la malla |
|---|---|---|---|
| head_body_length | Cabeza-cuerpo recto | 1.50 m | ΔY entre la punta de la nariz (landmark `nose_tip`) y el punto dorsal de la base de la cola (`tail_base`) |
| hb_dorsal_contour | Cabeza-cuerpo por contorno | 1.70 m | Longitud del perfil dorsal de la línea media (cabeza + cuerpo) |
| withers_height | Altura a la cruz | 0.72 m | Z máxima del tronco en la mitad delantera |
| croup_height | Altura a la grupa | 0.70 m | Z máxima del tronco en la mitad trasera. La línea dorsal del jaguar es casi recta |
| tail_length | Cola | 0.55 m | Longitud de arco por los centroides de la cola |
| head_length | Cabeza | 0.29 m | Distancia nariz → occipucio |
| head_width | Ancho de cabeza | 0.21 m | Extensión en X de `Jaguar_Head` (arcos cigomáticos y mejillas) |
| chest_depth | Profundidad de pecho | 0.39 m | Cruz − punto más bajo del esternón (≈ 54 % de la alzada: pecho muy profundo) |
| chest_clearance | Altura libre bajo el pecho | 0.33 m | Z mínima del tronco detrás de los codos |
| belly_clearance | Altura libre en el ijar | 0.37 m | Z mínima de la línea media ventral 0.28 m por delante de las zarpas traseras. Remetido suave: el jaguar tiene un pliegue ventral colgante |
| torso_width | Ancho del tronco | 0.32 m | Extensión en X del tronco sin patas (costillar y escápulas) |
| front_paw_width | Zarpa delantera | 0.11 m | Huellas delanteras de 10–12 cm |
| hind_paw_width | Zarpa trasera | 0.095 m | Las traseras son más estrechas |
| forearm_depth | Antebrazo | 0.095 m | Fondo (delante-detrás) a z ≈ 0.185 m. Antebrazo muy grueso |
| tail_base_diameter | Cola cerca de la base | 0.075 m | Diámetro medio de 5 a 9 cm a lo largo de la cola (sin pelo) |

Tolerancia: ±5 % en todas.

**Medida informativa:** masa estimada = volumen de cuerpo + cabeza + mandíbula ×
1040 kg/m³. Debería quedar alrededor de 85–105 kg. No es un criterio de
aceptación porque falta el pelaje y la densidad es aproximada, pero sirve para
detectar un modelo demasiado flaco.

## Rasgos que lo separan del leopardo (lista de control de la silueta)

- Más robusto y pesado: pecho profundo, barril costal ancho, cuarto trasero
  macizo.
- Patas más cortas y gruesas; antebrazos muy anchos; zarpas grandes y redondas.
- Cabeza grande, ancha y redondeada, con hocico corto y ancho, mandíbula muy
  potente y mentón marcado.
- Cuello corto y grueso; la cabeza queda casi delante de los hombros.
- Cola corta y gruesa que apenas pasa del corvejón.
- Patas traseras digitígradas con ángulo de corvejón marcado (calcáneo saliente
  y metatarso casi vertical).
- Orejas pequeñas, redondeadas, separadas y bajas en los lados del cráneo.
