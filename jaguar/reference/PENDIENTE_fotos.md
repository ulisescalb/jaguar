# Fotos de referencia: qué sirve y qué falta

## Recibidas

| Archivo | Vista | Uso | Motivo |
|---|---|---|---|
| `photo_side_walk.jpg` | Lateral derecha, al paso | **Sí: máscara `masks/side_mask.png`** | Fondo blanco, silueta limpia y casi ortogonal (perspectiva leve). La pose no es neutra: patas en zancada, cola levantada en «S», cabeza adelantada. El modelo se compara en una **pose de foto** con las mismas articulaciones dobladas (ver Paso 4). |
| `photo_front_walk.jpg` | Frontal, avanzando hacia la cámara | **Sí: máscara `masks/front_mask.png`** | Silueta limpia, pero con **perspectiva fuerte**: la cabeza está mucho más cerca que la grupa. Se compara con una cámara en perspectiva ajustada. Mano derecha adelantada. |
| `photo_skeleton_side_ai.jpg` | «Esqueleto lateral» | **No** | Composición generada por IA: el esqueleto se disuelve en niebla y faltan húmero, fémur, pelvis completa y casi todo el cráneo. La escápula y la columna tienen formas incoherentes (vértebras sin cuerpos, una escápula «flotante» sobre la columna). Además hay una barra gris en el borde derecho. No sirve ni para máscara ni para landmarks: usarla metería errores anatómicos. |
| `photo_threequarter_fog_ai.jpg` | 3/4 delantero | **No** | Generada o editada por IA: la mitad inferior y la cola desaparecen en niebla, la cara está borrosa y hay una barra gris a la derecha. No se puede extraer silueta, y una vista 3/4 en perspectiva tampoco permite comparar proporciones. |

Ninguna foto tiene escala (regla, objeto conocido), así que la escala absoluta
sale de `medidas.md`: la lateral se alinea con la distancia nariz–base de la cola
del modelo y con la línea del suelo.

## Faltan (en orden de utilidad)

1. **Lateral de pie con las cuatro patas apoyadas**, tomada con teleobjetivo
   (≥ 200 mm, lejos) y la cámara a la altura del hombro. Es la referencia que
   pedía la etapa: hoy hay que doblar el modelo para compararlo con una zancada.
2. **Esqueleto lateral real** (pieza de museo o lámina científica con escala) de
   *Panthera onca*, o en su defecto de *Panthera pardus/leo*. Sin ella, los
   landmarks salen de anatomía comparada (ver `iteration_log.md`).
3. **Frontal de pie con teleobjetivo**, para tener ancho de hombros, pecho y
   cabeza sin la perspectiva de la foto actual.
4. **Cenital (dorsal)** para la planta: hombros, cintura y caderas.
5. **Cabeza**: perfil puro, frente puro y cenital, más un primer plano de ojo,
   trufa y oreja.
6. **Zarpas**: planta (almohadillas) y frente, delantera y trasera.
7. Cualquier foto con una **escala** reconocible.

Hasta tenerlas, los pasos 2, 3, 6 y 7 usan anatomía de félidos y la lista de
comprobación visual; la lateral y la frontal al paso guían el ajuste del paso 4.
