# Jaguar (*Panthera onca*) — malla base (etapas 1 y 2)

Malla base procedural del jaguar, sin rig, texturas ni pelaje. Desde la v07 la
forma sale de una escultura por volúmenes musculares (SDF) ajustada a las
siluetas de fotos reales, y se transfiere a la topología limpia de animación. Unidades en metros,
Z arriba, el animal mira hacia −Y, origen en el suelo centrado entre las zarpas y
transformaciones aplicadas.

## Requisitos

Blender 4.x. Probado con 4.5.15 LTS (módulo `bpy`) y con 4.0.2.

En Windows:

```bash
winget install -e --id BlenderFoundation.Blender.LTS.4.5
```

Después añade al `PATH` la carpeta de instalación
(p. ej. `C:\Program Files\Blender Foundation\Blender 4.5`) o llama a `blender.exe`
con la ruta completa.

## Etapa 2 (v07+): un comando regenera todo

Con un venv de Python 3.11 y `pip install -r requirements.txt` (incluye `bpy`
4.5 LTS oficial), desde esta carpeta:

```bash
python src/build_jaguar.py --version v07 --export-glb
```

El comando:
- Construye la malla limpia sobre la escultura SDF definida en `params.json`.
- Mide, valida la topología y calcula el IoU de la malla posada como en las fotos.
- Exporta `export/landmarks.json`, `export/jaguar_base_v07.glb` y
  `blend/jaguar_v07.blend`.
- Guarda la escultura de alta resolución en `blend/jaguar_v07_sculpt.blend`.
- Renderiza `renders/v07/` (más `renders/v07/sculpt/` e `renders/v07/iou/`).

Con el Blender normal (`blender -b -P src/build_jaguar.py -- --version v07`)
también se genera la malla limpia, porque la SDF sólo usa numpy. El IoU y la
escultura se omiten con un aviso si ese Python no tiene OpenCV ni scikit-image.

Pasos previos, ya hechos y con resultado guardado en el repo:

```bash
python src/extract_masks.py
```

```bash
python src/fit_silhouette.py --stages C B P:hind_legs P:front_legs P:head P:tail B --evals 420
```

El primero genera las máscaras en `reference/masks/`. El segundo ajusta
volúmenes y poses contra las fotos, escribe el resultado en `params.json` y el
registro en `logs/fit_v07.jsonl`.

## Uso de la etapa 1 (v01–v06, desde esta carpeta)

Generar la malla, validarla, medirla, guardar `blend/jaguar_v06.blend` y renderizar
`renders/v06/`:

```bash
blender -b -P src/build_jaguar.py -- --version v06
```

Opciones:

- `--export-glb`: escribe además `export/jaguar_base_<versión>.glb`.
- `--no-render`: sólo construir, medir y guardar.
- `--preview`: renders rápidos en `renders/_preview/`.
- `--samples N`: muestras de Cycles.
- `--params RUTA`: usar otro `params.json`, p. ej. el `params_used.json` de una
  versión anterior para reproducirla.

Volver a renderizar un `.blend` existente:

```bash
blender -b blend/jaguar_v06.blend -P src/render_views.py -- --version v06
```

Cycles usa OptiX o CUDA si hay GPU NVIDIA; si no, CPU.

## Archivos

| Ruta | Contenido |
|---|---|
| `reference/medidas.md` | Medidas de referencia, correcciones y cómo se mide cada una |
| `src/params.json` | Todas las proporciones: secciones, anillos de patas, cola, cabeza, mandíbula, orejas, ojos y bultos musculares |
| `src/build_jaguar.py` | Construcción de la malla (punto de entrada) |
| `src/geom.py` | Primitivas: anillos, injertos, tapas quad, esfera quad, bultos |
| `src/measure.py` | Medidas reales desde la malla y validación topológica |
| `src/render_views.py` | Renders estilo arcilla y silueta |
| `blend/` | Un `.blend` por versión |
| `renders/vNN/` | Vistas, `side_guides.png` (cotas objetivo), `contact_sheet.png`, `measurements.md` y `params_used.json` |
| `export/` | GLB de la última versión |
| `iteration_log.md` | Bitácora de decisiones y críticas |
| `reference/photo_*.jpg`, `reference/masks/` | Fotos de referencia y sus máscaras de silueta |
| `reference/PENDIENTE_fotos.md` | Fotos que no sirven y las que faltan |
| `src/skeleton.py` | Landmarks anatómicos y cinemática directa (poses de foto) |
| `src/sdf.py`, `src/sculpt.py` | Escultura por volúmenes musculares (SDF) y su malla de alta resolución |
| `src/silhouette.py`, `src/fit_silhouette.py` | Métrica IoU contra las fotos y ajuste CMA-ES |
| `src/conform.py` | Transferencia de la escultura a la topología limpia |
| `export/landmarks.json` | Esqueleto de referencia para la etapa de rig |
| `logs/fit_v07.jsonl` | Registro del optimizador |

Leyenda de `side_guides.png`:

- Rojo: cruz, 0.72 m.
- Naranja: grupa, 0.70 m.
- Azul: altura libre bajo el pecho, 0.33 m.
- Cian: altura libre en el ijar, 0.37 m.
- Verde: punta de la nariz y nariz + 1.50 m (dónde debería caer la base de la
  cola).
- Abajo: regla de 1 m con marcas cada 10 cm.
