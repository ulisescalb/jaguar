# Jaguar (*Panthera onca*) — malla base, etapa 1

Malla base procedural del jaguar, sin rig, texturas ni pelaje. Unidades en metros,
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

## Uso (desde esta carpeta)

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

Leyenda de `side_guides.png`:

- Rojo: cruz, 0.72 m.
- Naranja: grupa, 0.70 m.
- Azul: altura libre bajo el pecho, 0.33 m.
- Cian: altura libre en el ijar, 0.37 m.
- Verde: punta de la nariz y nariz + 1.50 m (dónde debería caer la base de la
  cola).
- Abajo: regla de 1 m con marcas cada 10 cm.
