# Bitácora de iteraciones — Jaguar base mesh (Etapa 1)

Formato: cada versión tiene **una intención**. Los cambios numéricos que sirven a
esa intención van juntos. Las correcciones de herramientas (renders, medidas) se
anotan aparte porque no cambian el modelo. Cada `renders/vNN/` incluye
`params_used.json`, `measurements.md` y las vistas.

## Decisiones previas (Paso 0 y método)

- **Entorno.** La sesión corre en un contenedor Linux en la nube (Ubuntu 24.04, 4
  CPU, sin GPU), no en tu PC, y Blender no estaba instalado. Detenerse ahí habría
  dejado la etapa sin hacer, y aquí instalar no toca tu máquina, así que instalé
  Blender **solo desde fuentes oficiales**:
  - Módulo `bpy` 4.5.15 LTS de PyPI (publicado por la Blender Foundation). Con él
    hice las iteraciones (`python src/build_jaguar.py --version vNN`).
  - `blender` 4.0.2 del repositorio oficial de Ubuntu. Con él comprobé el comando
    exacto `blender -b -P src/build_jaguar.py -- --version vNN`.
  - download.blender.org está bloqueado por la política de red del contenedor; no
    intenté rodearlo.
  - Comando para tu Windows: ver el reporte final o el README.
- **GPU.** `render_views.py` prueba OptiX y luego CUDA; si no encuentra GPU usa CPU.
  Aquí renderizó por CPU con OpenImageDenoise. En tu RTX 3070 Ti elegirá OptiX
  sola. Si el build no trae OIDN (el Blender de Ubuntu no lo trae), multiplica por
  4 las muestras y desactiva el denoise.
- **Estructura del proyecto.** Creé `./jaguar` dentro del repo, tal como pediste
  («créala en ./jaguar»).
- **Método de modelado** (cambio justificado respecto al Skin modifier). Construyo
  la jaula quad por código:
  - Anillos de secciones transversales (superelipses paramétricas) para el
    tronco, el cuello, la cabeza y la mandíbula.
  - Agujeros rectangulares en el tronco donde se injertan patas y cola, con
    emparejado angular para que el puente no se retuerza.
  - Tapas en rejilla quad (Coons patch) para cerrar los extremos sin triángulos ni
    n-gons.
  - Al final, un nivel de Catmull-Clark **aplicado**.

  El Skin modifier genera cascos con triángulos y polos en las uniones de tres o
  más ramas, y su sección cuadrada gira sin control. Con anillos explícitos puedo
  poner un bucle de aristas exactamente en cada articulación: hombro (borde del
  injerto), codo, muñeca, cadera, rodilla, corvejón, párpados y comisura de la
  boca. No usé Remesh.
- **Detalle anatómico.** Encima de las secciones, «bultos» gaussianos
  paramétricos (escápulas, deltoides, tríceps, cadera, glúteo, almohadillas de
  bigotes, pómulos, cejas) aplicados a la jaula antes de subdividir. Todo está en
  `params.json`.
- **Objetos.**
  - `Jaguar_Body` (tronco, cuello, patas y cola), `Jaguar_Head`,
    `Jaguar_LowerJaw`, `Jaguar_EarL/R`, `Jaguar_EyeL/R` (esferas de quads, sin
    polos triangulares).
  - Todos tienen transformaciones identidad: los vértices se construyen
    directamente en coordenadas de mundo.
  - Las propiedades personalizadas guardan los pivotes útiles para el rig:
    bisagra de la mandíbula (`jaw_hinge_world` y `jaw_hinge_axis`), pivote de la
    cabeza y centros de los ojos.
  - Los grupos de vértices por región (`leg_FL`, `paw_HR`, `tail`,
    `eyelid_L`…) sirven para medir y para pesar el rig más adelante.
- **Medidas.** Se calculan siempre de la malla final (`src/measure.py`) usando
  landmarks en grupos de vértices: `nose_tip`, `occiput`, `tail_base`.

## v01 — bloqueo inicial desde las medidas

**Intención:** primer bloqueo completo con las medidas que diste (cabeza-cuerpo
1.65 m en línea recta, cruz 0.72 m, cola 0.55 m).

**Herramientas:** los primeros renders salieron sobreexpuestos (la arcilla se veía
blanca). Bajé la energía de las luces (key 1100→300 W, fill 380→90 W, rim
900→260 W) y oscurecí el fondo. Volví a renderizar la v01 con el mismo
`params_used.json` para que todas las versiones sean comparables.

**Crítica** (side_guides, three_quarter, front, head_closeup):
- *Silueta lateral:* tubo largo y bajo, «salchicha». Con 1.65 m recto y 0.72 m de
  alzada no parece un félido. Cuello largo y horizontal; la cabeza sobresale
  mucho por delante del pecho.
- *Cabeza/cuerpo:* la cabeza mide 0.30 m, pero se ve pequeña y estrecha,
  de roedor.
- *Pecho:* profundidad correcta en números (0.383 m), pero la línea inferior baja
  en diagonal recta hasta el ijar y no se lee el pecho.
- *Vientre:* sin remetido; el ijar está 2 cm por encima del objetivo.
- *Hombros y escápulas:* no hay; la pata delantera sale como una columna de la
  panza.
- *Cuarto trasero:* bloque rectangular; el muslo forma una «falda» hasta la
  rodilla.
- *Patas traseras:* el corvejón se intuye, pero el contorno posterior es una recta
  vertical.
- *Grosor de patas y zarpas:* zarpa delantera −5.2 %, antebrazo −5.3 %.
- *Hocico y mandíbula:* la mandíbula sobresale como un pico de pato y la boca
  queda abierta; ojos de bolita saltones.
- *Orejas:* bien colocadas a grandes rasgos; demasiado finas vistas de canto.
- *Cola:* buena caída en «J»; base 15 % más fina que el objetivo.

**Diagnóstico:** el 1.70 m publicado se mide con cinta sobre el contorno del animal
estirado. De pie, la distancia recta debe ser menor (ver `reference/medidas.md`).

## v02 — proporciones globales

**Intención:** compactar el animal.
- Objetivo recto nariz→base de la cola: 1.50 m (≈ 0.88 × 1.70).
- Tramo entre patas: de 0.62 a 0.46 m.
- Muslo/cadera: de 0.31 a 0.28 m.
- Cuello más corto y alto.
- Pivote de la cabeza adelantado 4 cm y subido 2.5 cm.

**Herramientas:**
- Nueva medida del contorno dorsal (tipo cinta) y masa estimada por volumen.
- Corregido un fallo: el contorno cogía puntos del vientre; ahora filtra por
  normal hacia arriba.

**Resultado** (cabeza-cuerpo 1.472 m, −1.8 %): ahora se lee como un félido grande y
pesado; la distancia entre zarpas pasa de 0.95 a 0.79 m.

**Crítica:**
- *Silueta:* mucho mejor; falta definir las patas.
- *Cabeza:* sigue de roedor, con la mandíbula de pato.
- *Pecho y vientre:* aceptables.
- *Hombros:* sin definición.
- *Cuarto trasero:* sigue siendo un bloque con contorno posterior vertical.
- *Patas:* columnas.
- *Cola:* fina en la base.
- *Masa estimada:* 119 kg, algo alta (incluye el solape cabeza-cuello).

## v03 — anatomía de las patas

**Intención:** que las patas lean como de jaguar.

Delanteras:
- Anillo superior inclinado (*roll* 25°: axila baja y lado externo alto) para el
  volumen del brazo.
- Olécranon que sobresale hacia atrás a z ≈ 0.30.
- Antebrazo grueso que se afina hacia la muñeca.
- Bucles en codo (3) y muñeca (3).

Traseras:
- Rediseño con números de esqueleto (fémur ≈ 0.25 m, tibia ≈ 0.23 m, corvejón
  a 0.16 m). En v02 la rodilla estaba tan adelantada que la tibia quedaba a 35° de
  la horizontal; ahora va a ≈ 50°: rodilla en y ≈ 0.23.
- Contorno posterior convexo en el glúteo que se recoge hacia el tendón de
  Aquiles. El calcáneo sobresale y el metatarso se adelanta: ángulo de corvejón
  marcado.

Zarpas: más anchas (delantera 0.114 m, trasera 0.099 m).

Añadido a las herramientas: parámetro `roll` por anillo; preview rápido
(`--preview`) para tantear antes de fijar la versión.

**Crítica:**
- *Patas:* el muslo ya se estrecha hacia una pierna más fina y la rodilla está en
  su sitio. La delantera sigue siendo bastante columnar; el codo apenas se lee de
  perfil, pero es fiel a la pata recta y gruesa del jaguar.
- *Medidas de patas:* todas en verde.
- *Cabeza:* sigue siendo el peor problema, porque domina el primer plano y la
  vista 3/4.

## v04 — cabeza

**Intención:** cabeza de jaguar (grande, ancha y redonda, con hocico corto y ancho)
y mandíbula bien asentada.

Cambios principales:
- Cráneo más alto (+1.5–2 cm) y mejillas cigomáticas a 0.112 m de semiancho.
  Objetivo de ancho de cabeza corregido de 0.21 a **0.22 m**: cráneo de 0.19 m
  más tejidos blandos.
- Hocico trapezoidal: puente nasal más estrecho que las almohadillas. Nariz
  recortada a y = −0.265 m.
- Labio superior que cae 1–1.2 cm sobre los lados de la mandíbula (`drape`).
- Mandíbula retrasada (mentón 2–3 cm por detrás de la nariz), más estrecha que
  el labio superior y 2 mm bajo él. Bisagra en la ATM y 1° de apertura: boca
  casi cerrada.
- Ojos 1 cm más profundos (`inset` 0.45→0.70 R), mirada frontal explícita (22°
  hacia fuera, 2° arriba), apertura en almendra con inclinación de 10°, y radio
  de 16.5 a 17.5 mm.
- Cuello engrosado para que nuca y garganta empalmen.
- Inclinación de la cabeza 22°→18° y pivote 2.5 cm más bajo: la coronilla queda
  ≈ 3 cm bajo la cruz, «ligeramente baja».
- Bultos faciales: almohadillas de bigotes, arco superciliar, pómulo, puente
  nasal ancho y filtrum.

Tanteos dentro de la versión (preview):
- Un frontal del hocico demasiado plano quedó como hocico de cerdo; volví a una
  nariz algo redondeada.
- Bajar la cabeza aumentaba el contorno dorsal.

**Decisión sobre el contorno dorsal:** la medida «tipo cinta» sobre el animal de
pie incluye la subida nariz→frente y la vuelta del cuello, que el zoólogo no mide
porque estira la cabeza en línea con el cuerpo. Depende demasiado de la pose, así
que **la dejé informativa** (1.93 m) y el criterio de aceptación es la recta
horizontal de 1.50 m.

**Crítica** (head_closeup, front, three_quarter):
- *Perfil:* la cabeza ya se lee como de félido: cráneo redondo, cara corta y
  mandíbula recogida bajo el labio.
- *Frente y 3/4:* todavía tiene algo de oso. Las orejas redondas quedan muy
  arriba, los ojos se ven pequeños y la trufa no se distingue: el morro es un
  bulbo liso.
- *Unión cabeza-cuello:* queda un escalón visible en la nuca.
- *Dos auto-intersecciones* en la cabeza dentro de las cuencas (anillos de
  párpado interior tras la esfera del ojo); quedan ocultas por el globo ocular.
  En la v04 final aparecen 0.

## v05 — tronco, cuello y cola

**Intención:** dar forma al tronco, que en planta era un tubo uniforme.

- *Planta:* hombros 0.134 → barril costal 0.167 detrás de los codos → cintura
  0.133 → caderas y grupa 0.152 → anca.
- *Bultos musculares:* borde dorsal de las escápulas, punta del hombro,
  tríceps, punta de la cadera y glúteo.
- *Nuca:* continua con el occipucio. Neck +2 cm de alto en la unión; los
  anillos traseros de la cabeza, un poco más pequeños para quedar dentro del
  cuello.
- *Cola:* radios ×1.16. La subdivisión de un anillo de 8 vértices encoge ≈ 13 %,
  y eso explicaba el −15 % de diámetro.

**Resultado:** las 15 medidas en ±5 % (diámetro de la cola 0.075 m, −0.5 %). Desde
arriba se leen la cintura y la grupa ancha; la nuca empalma sin escalón visible de
perfil.

**Crítica:**
- *Silueta lateral:* félido robusto con patas cortas y gruesas, pecho profundo y
  cola corta y gruesa.
- *Proporción cabeza/cuerpo:* 19.7 % del cabeza-cuerpo recto.
- *Pecho:* 0.389 m de profundidad.
- *Vientre:* remetido suave (ijar a 0.382 m).
- *Hombros y escápulas:* leves; a distancia de estrategia se leen como masa, no
  como forma.
- *Cuarto trasero:* macizo y bien.
- *Corvejón:* marcado.
- *Zarpas:* anchas.
- *Hocico y mandíbula:* bien de perfil, mejorables de frente.
- *Orejas:* todavía de oso: altas y encima del cráneo.
- *Cola:* grosor correcto.
- *Masa estimada:* 126 kg, alta. El solape de la cabeza con el cuello suma
  ≈ 5–8 kg; aun así es un animal pesado, coherente con un macho grande del
  Pantanal.

## v06 — lectura felina de la cabeza

**Intención:** quitarle a la cabeza el aire de oso o hipopótamo en el primer plano
y en la vista 3/4.

- *Orejas:* más bajas y laterales (x 0.078→0.088 m, z 0.100→0.088 m locales,
  roll 28°→40°) y algo más pequeñas (0.066 × 0.072 m). Desde el frente quedan a
  los lados del cráneo, a la altura del borde de las mejillas, como en el jaguar.
- *Hocico:* sección más triangular (puente nasal estrecho con `pt` 1.5–1.7 y
  ancho máximo abajo), algo menos lleno delante de los ojos.
- *Almohadillas de bigotes:* bultos el doble de fuertes.
- *Filtrum:* surco más marcado.
- *Trufa:* nuevo bulto del rinario.
- *Ojos:* radio 18.5 mm y apertura vertical 0.78.

**Crítica** (front, head_closeup, three_quarter):
- *Frente:* mejora clara. Se leen el puente nasal, los dos lóbulos de las
  almohadillas sobre el mentón y las orejas laterales.
- *3/4 y primer plano:* el morro sigue algo bulboso y los ojos parecen esferas
  sobrepuestas (falta el pliegue del párpado superior y el ángulo lagrimal).
  Con esta jaula (32 vértices por anillo) el bulto gaussiano ya no da más de sí:
  es trabajo de esculpido/normal map.
- *Silueta y medidas:* sin cambios respecto a la v05, todas en ±5 %.

**Cierre:** llegué al máximo de 6 iteraciones. Ninguna fue nula, así que no hizo
falta la regla de parada anticipada.

## Estado final (v06)

Las medidas, sacadas de la malla, están en `renders/v06/measurements.md`. Las 14
medidas de aceptación quedan dentro de ±5 %:
- Cabeza-cuerpo recto 1.451 m (−3.3 %).
- Cruz 0.721 m.
- Grupa 0.700 m.
- Cola 0.543 m.
- Cabeza 0.285 m (19.6 % del cabeza-cuerpo).
- Ancho de cabeza 0.226 m.
- Pecho 0.389 m.
- Altura libre bajo el pecho 0.332 m.
- Ijar 0.382 m.
- Tronco 0.329 m.
- Zarpas 0.114 y 0.099 m.
- Antebrazo 0.099 m.
- Cola en la base 0.075 m.

**Topología:**
- **10 272 quads**: cuerpo 5 536, cabeza 2 704, mandíbula 832, orejas 2×384,
  ojos 2×216.
- 0 triángulos, 0 n-gons.
- 0 aristas no-manifold, 0 bordes abiertos, 0 vértices sueltos.
- 0 normales incoherentes, normales hacia fuera.
- 0 auto-intersecciones en cada objeto.

Los solapes entre objetos son intencionados: la cabeza encaja en el cuello, la
mandíbula queda bajo el labio y la base de orejas y ojos va dentro de la cabeza.

**Bucles de aristas** (jaula × 2 tras la subdivisión):
- Hombro y cadera: bucle de raíz del injerto (grupos `loop_shoulder` y
  `loop_hip`).
- Codo, muñeca, rodilla y corvejón: tres anillos de jaula cada uno, que pasan a
  ser cinco o seis bucles.
- Párpados: tres anillos concéntricos por ojo (`eyelid_L/R`).
- Comisura: estaciones densas (≈ 2 cm) alrededor de y = −0.135 m en la cabeza y
  en la mandíbula, más el bucle del labio inferior (`lip_lower`).

**Reproducibilidad:** `blender -b -P src/build_jaguar.py -- --version v06`, con el
Blender 4.0.2 real y en una copia limpia, corrió de cero (1 min 49 s en CPU con
renders). Dio medidas idénticas a las de Blender 4.5.15 (diferencia máxima
6·10⁻⁸ m) y el mismo número de quads.

**Zonas débiles para la etapa 2:**
1. *Cara en primer plano:* morro bulboso, ojos de «cuenta» sin pliegue palpebral,
   trufa poco definida. Esculpir o hacer normal map; quizá subir la jaula de la
   cabeza a 40 vértices por anillo.
2. *Patas delanteras:* columnares; el codo apenas se lee de perfil. Las zarpas son
   óvalos lisos sin lóbulos de dedos ni almohadilla carpal.
3. *Hombros y escápulas:* se leen como masa, no como forma. Le falta el pliegue de
   piel ventral colgante (bolsa primordial) típico del jaguar.
4. *Cabeza y cuerpo separados:* lo pediste así. Para el rig habrá que pesar con
   cuidado la transición en el cuello o fusionarlos; el anillo trasero de la
   cabeza queda dentro del cuello.
5. *Masa estimada* 126 kg (el solape cabeza-cuello suma algunos kg): animal
   pesado. Si se quiere un macho medio de 90 kg, reducir ≈ 5 % el semiancho del
   tronco.

---

# Etapa 2 — forma guiada por referencias (v07+)

Diagnóstico de partida (tuyo, y lo comparto): la v06 cumple las medidas pero no la
forma. A partir de aquí manda la **comparación de siluetas** contra fotos reales, y
el juicio visual pesa más que las tablas.

## Paso 1 — referencias y métrica de silueta

- Fotos copiadas a `reference/`:
  - Útiles: `photo_side_walk.jpg` y `photo_front_walk.jpg`.
  - Inservibles: `photo_skeleton_side_ai.jpg` y `photo_threequarter_fog_ai.jpg`.
  - Detalle y lista de lo que falta en `reference/PENDIENTE_fotos.md`.
- **Máscaras** (`src/extract_masks.py`):
  - Semilla por color (pelaje saturado u oscuro = primer plano; blanco puro =
    fondo) + GrabCut para separar el pelaje blanco de las patas de la sombra
    gris del suelo.
  - Después: componente mayor, relleno de huecos y cierre de 15 px. El cierre
    tapa una muesca en la pata trasera lejana.
  - Revisadas a ojo: `reference/masks/*_check.jpg`, contorno magenta.
- **Puntos de alineación** medidos sobre la foto lateral (px originales):
  - Punta de la nariz (1835, 505).
  - Base dorsal de la cola (490, 350), ±15 px ≈ ±1.5 cm. La curva grupa→cola es
    continua y el punto exacto es ambiguo.
  - Suelo en y = 1000: zarpas de apoyo en 998 y 1005.
- **`src/silhouette.py`**:
  - Rasteriza los triángulos con OpenCV, sin Cycles, a media resolución de la
    foto. Lateral ortográfica, escalada por nariz–base de la cola y apoyada en
    el suelo. Frontal en perspectiva, con cámara estenopeica ajustada por CMA-ES
    dentro de límites físicos; el mismo procedimiento para todas las versiones.
  - Superposición: gris = coincide, rojo = sobra, azul = falta.
  - *Fallo corregido:* `fillPoly` con muchos triángulos usa la regla par-impar y
    los solapes se anulaban (salía un IoU de 0.28). Ahora rellena triángulo a
    triángulo.

**Línea base v06** (`renders/v06/iou/`): **IoU lateral 0.533**, **frontal 0.747**.

Lectura de la superposición lateral:
- Con la escala fijada por el largo nariz–base de la cola, el jaguar de la foto es
  ≈ 11 % más alto (cruz ≈ 0.80 m si el cabeza-cuerpo fuera 1.46 m).
- Tiene el vientre más bajo (pecho de ≈ 0.45 m de fondo), cuello y cabeza
  adelantados y bajos, la cola levantada en «S» y las patas en zancada.
- La v06 sobra sobre todo en las patas (rectas) y en la cola colgante.

**Consecuencia:** con ±8 % sobre `medidas.md`, una silueta tan compacta solo cabe
con un cabeza-cuerpo recto ≈ 1.40–1.43 m (−5…−7 %) y una cruz ≈ 0.76–0.78 m
(+5…+8 %). El optimizador trabajará en ese margen. No cambio los objetivos: si
el resultado queda en el límite, lo anoto como evidencia de que la foto muestra un
animal más compacto que el promedio publicado.

## Paso 2 — esqueleto de referencia (landmarks)

- `params.json["skeleton"]`:
  - Landmarks 3D de la pose neutra: columna C1–C7, T1, T5, T10, T13, L4, L7,
    sacro y base de la cola; escápula (borde dorsal e inferior), hombro, codo,
    olécranon, carpo, metacarpo y dedos; cresta ilíaca, cadera, isquion, rodilla,
    rótula, corvejón, calcáneo, metatarso y dedos.
  - Cráneo en marco local con inclinación: cóndilos/pivote, occipucio, órbita,
    punta nasal, bisagra de la mandíbula, barbilla, arco cigomático y base de la
    oreja.
  - Cola: cadena de 6 segmentos con ángulos.
- `src/skeleton.py`:
  - Simetría L→R y cinemática directa en el plano sagital, con ángulos por
    articulación. La usan las «poses de foto»: la del lateral, en zancada, y la
    del frontal, mano derecha adelantada.
  - Escalas globales ajustables (altura respecto al suelo, largo del tronco,
    cuello, cabeza) que conservan el apoyo de las cuatro zarpas.
- Osteología de *Panthera* escalada a un macho de ~0.75 m de cruz:
  - Largos resultantes: escápula 0.24 m, húmero 0.23, radio 0.21, metacarpo
    0.085, fémur 0.25, tibia 0.23, metatarso 0.13 y cuello (T1–C1) 0.25.
  - Columna, en proporción del cabeza-cuerpo recto: torácicas + lumbares ≈ 60 %,
    cuello ≈ 23 % y cabeza ≈ 18 %, igual que en la foto lateral (60/22/18 %).
    En la v06 eran 65/18/19: tronco largo y cuello corto, justo el defecto
    diagnosticado.
- Criterios verificados en los landmarks:
  - *Escápula oblicua:* 25° respecto a la vertical. El borde dorsal queda a
    0.715 m, justo bajo la piel de la cruz (0.75 m); asoma al ajustar la pose de
    paso.
  - *Codo pegado al tronco:* a 0.32 m, la altura del fondo del pecho; x = 0.11 m,
    junto a la caja torácica. El húmero va atrás y abajo.
  - *Digitígrado:* carpo a 0.11 m, corvejón a 0.16 m y metatarso trasero a 79°
    de la horizontal.
  - *Rodilla:* delante, a 0.335 m, la altura del vientre.
  - *Cuello y cabeza:* la coronilla queda a la altura del lomo o algo por
    debajo; la nariz, a 0.50 m.
- `export/landmarks.json`: posiciones, jerarquía propuesta (`parent`) para el
  rig, descripción y cadena de la cola. Se regenera en cada build con el mismo
  desplazamiento que la malla.

## Paso 3 — escultura por volúmenes musculares (SDF)

**Método elegido:** SDF propia en numpy (`src/sdf.py`), no metaballs. Motivos:
- Funciona dentro de Blender y fuera.
- Se evalúa en puntos arbitrarios, que es lo que necesita la transferencia del
  paso 5.
- Admite restas suaves: pliegue del ijar, filtrum, fosas nasales, cuencas de los
  ojos, concavidad de la oreja.
- Cada primitiva va unida a un hueso del esqueleto, así que la misma escultura se
  evalúa en pose neutra o en las poses de foto.

Detalles:
- *Primitivas:* elipsoide (aproximación de iq) y cono redondeado exacto con
  sección elíptica opcional. Unión con smooth-min polinómico, resta con
  smooth-max.
- *Componentes:* `body`, `head`, `jaw`, `ear_L`/`ear_R`; los ojos son esferas
  aparte.
- *Velocidad:* la rejilla se evalúa sólo dentro de la caja de cada primitiva.
  Rejilla de 12 mm de todo el animal: 0.25 s.
- *Superficie:* `src/sculpt.py`, marching cubes de scikit-image a 8 mm en el
  cuerpo y 3 mm en cabeza, mandíbula y orejas (~0.2 M triángulos, muy por debajo
  del límite de 1 M).
- *Volumen:* el de la **unión** se integra por ocupación en una rejilla común de
  5 mm, sin sumar solapes.
- *Grupos musculares* (`params.json["sculpt"]["prims"]`, 78 definiciones,
  128 con las copias derechas):
  - Tronco: tórax (barril costal), dorsal torácico, cruz, lomo, abdomen, pliegue
    ventral colgante, grupa, glúteos y prosterno/pectoral.
  - Cuello: base, cono del cuello, nuca y garganta.
  - Miembro delantero: escápula, deltoides, tríceps, bíceps, antebrazo y su masa
    muscular, olécranon, carpo, almohadilla carpal, metacarpo, espolón, zarpa con
    4 dedos y almohadilla central.
  - Miembro trasero: muslo, cuádriceps, isquiotibiales, rodilla, gastrocnemio,
    tibia, Aquiles, corvejón, calcáneo, metatarso, zarpa con 4 dedos y
    almohadilla.
  - Cola: raíz y 6 conos.
  - Cabeza: cráneo, temporales, occipital, frente, arcos cigomáticos, maseteros,
    carrillos, cejas, suelo de la órbita, hocico, puente nasal, almohadillas de
    bigotes, labio superior, rinario y restas de filtrum, fosas nasales y cuencas.
  - Mandíbula: cuerpo, ramas, barbilla y labio inferior.
  - Orejas: concha, concavidad (resta) y raíz.
- *Primera escultura* (`renders/v07_steps/sculpt_initial/`): masa de félido, pero
  «bultosa» (músculos sueltos), ojos saltones y hocico de hipopótamo. Suavicé
  las mezclas y hundí los ojos 11 mm; la forma global la ajusta el paso 4 y la
  cara el paso 6.
- *Masa inicial:* volumen del cuerpo ≈ 0.12 m³, ≈ 120 kg. Demasiado pesado.

**Renders corregidos** (lo que pediste):
- Todas las vistas son cuadradas de 1024 px, sin bandas negras en el contact
  sheet.
- Encuadre ajustado: el animal ocupa el 86 % de la dimensión mayor del cuadro, en
  ortográfica y en perspectiva (la distancia de la cámara se calcula
  proyectando los vértices).
- Suelo y fondo más oscuros que la arcilla y luz key más baja.
- Se mide la fracción de píxeles quemados por vista (`render_check.json`): 0.0 %.

## Paso 4 — ajuste automático contra las siluetas

`src/fit_silhouette.py`. Cada evaluación hace SDF a 12 mm → marching cubes →
rasterizado de las dos vistas, en 0.3–0.8 s sin renders. Registro completo en
`logs/fit_v07.jsonl`.

**Parámetros:**
- Escalas del esqueleto, limitadas a ±12 % (altura, largo del tronco, cuello,
  cabeza) más la inclinación de la cabeza.
- Tamaños de 18 grupos musculares.
- Desplazamientos de 9 volúmenes del tronco: grupa, glúteo, lomo, dorsal, cruz,
  pliegue ventral, abdomen, cuello y nuca.
- Pose de la foto lateral: 14 articulaciones de patas, cuello, cabeza y 6
  segmentos de cola.
- Pose y cámara de la foto frontal.

**Restricciones (penalización):**
- Medidas en pose neutra ±8 %.
- Masa 80–95 kg.
- Regularización: los tamaños musculares no se alejan sin motivo de su valor
  anatómico (ver más abajo).

**Etapas y lecciones:**
1. *A + C + B* (pose + esqueleto, cámara frontal, volúmenes): lateral
   0.641 → 0.726. CMA-ES dejó la cola enroscada sobre la grupa (mínimo local) y
   las patas traseras con la fase cambiada: el IoU global diluye los errores de
   las piezas finas.
2. *P (por regiones):* IoU recortado a cola, patas delanteras, patas traseras y
   cabeza, con la cola inicializada con ángulos medidos en la foto. Lateral
   **0.726 → 0.761 → 0.802 → 0.808 → 0.816**.
3. *Desplazamientos por volumen + nueva B:* lateral ≈ 0.80–0.81, frontal
   0.83–0.85.
4. *Juicio visual por encima del número.* Para cumplir los 95 kg, el optimizador
   llevó tórax, vientre, hombros y muslos al límite inferior (×0.75) y estiró el
   cuello en vertical al máximo (×1.30). Resultado: joroba en la cruz y cintura
   de «hueso de perro» vista desde arriba. Lo corregí:
   - Regularización de los tamaños (peso 0.6 × media de log²).
   - Límites ×0.80–1.25, cuello en vertical ≤ ×1.15.
   - Rebalanceo a mano hacia un tórax de barril. La masa estaba mal repartida:
     el tronco era el 48 % y lo normal en mamíferos es ~55–60 %; cuello (9 kg)
     y muslos (13 kg) iban cargados.

**Resultado de la escultura** (`renders/v07/iou/sculpt_iou_*.png`):
- **IoU lateral 0.801.**
- **IoU frontal 0.830.**

## Paso 5 — transferencia a la malla limpia

`src/conform.py`. Misma topología que la v06 (anillos, injertos, tapas de rejilla,
párpados, comisura), pero cada anillo se coloca en su plano anatómico y se lanza
por *raycast* hasta la escultura:
- Tronco: planos verticales.
- Cuello: perpendicular a su eje.
- Patas y cola: perpendicular al hueso, centrado en el landmark.
- Muslo y rodilla: cortes horizontales.
- Zarpa: anillos horizontales.
- Cabeza y mandíbula: perpendicular al eje del cráneo, con las estaciones
  escaladas a la extensión real de la escultura.

Después, 1 nivel de Catmull-Clark, proyección Newton sobre la SDF de cada objeto
y 4 iteraciones de relajación tangencial (Laplaciano proyectado al plano
tangente + reproyección). Residuo de proyección: media < 0.003 mm, máximo
1.2 mm.

Problemas que aparecieron y cómo los resolví (con alambre y con recuento de
auto-intersecciones por zona):
- *Pliegues en hombro y muslo:* los anillos del tronco quedaban debajo de los
  músculos y la proyección final los doblaba. Ahora la pared del tronco incluye
  escápula y muslo, pero no tríceps.
- *Astillas en la unión pata–tronco:* el primer anillo de la pata quedaba por
  encima del borde inferior del injerto. Ahora la pata empieza en el codo y en
  la pierna, y el injerto trasero se puso un índice más alto.
- *Pinzamiento en la raíz de la cola:* los anillos empezaban dentro de la grupa.
  Ahora arrancan donde la cadena sale del tronco, y el agujero de la tapa bajó
  una fila.
- *Pozo en la cuenca del ojo:* el agujero de la rejilla no coincidía con el ojo.
  - El injerto se elige solo: es el bloque de celdas más cercano al punto de
    piel del ojo.
  - El globo se coloca a 0.70 R bajo esa piel, a lo largo de la mirada.
  - El contorno y el párpado exterior se apoyan sobre la piel; el borde del
    párpado (0.8 R) y los anillos interiores quedan fijos.
  - Apertura en almendra de ≈ 34 × 22 mm.
- *Púas en el hocico:* había una cavidad interna en la línea media entre el
  cráneo y el hocico, y los rayos sin cruce usaban un respaldo de 8.8 cm. Añadí
  un relleno interior (`head_core` / `jaw_core`), y los rayos sin cruce toman la
  mediana de su anillo.
- *Orejas:* la concha sale del marco de su primitiva. Proyectar una lámina tan
  fina la plegaba, así que no se proyecta.

**Quads:**
- 10 288 en total: cuerpo 5 344, cabeza 2 832, mandíbula 912, orejas 2×384, ojos
  2×216.
- No hizo falta subir hacia 15k: los anillos extra van en la zarpa (4 en vez de
  3), compensados por el muslo, que ahora es parte de la pared del tronco.

**Bucles de aristas en su sitio:**
- Hombro y cadera: borde del injerto.
- Codo, muñeca, rodilla y corvejón: un anillo de jaula centrado en el landmark,
  más vecinos, que dan 5–6 bucles tras subdividir.
- Párpados: 5 anillos.
- Comisura: estaciones densas de cabeza y mandíbula.

**Validación:**
- Sin triángulos ni n-gons, sin aristas no-manifold, sin bordes abiertos, sin
  vértices sueltos, sin normales incoherentes y sin caras colapsadas.
- Ángulos de quads entre 39° y 140° en el percentil 1–99 del cuerpo.
- **Quedan auto-intersecciones locales** (la v06 tenía 0):
  - Cuerpo, 110: unión de la pata trasera y raíz de la cola.
  - Cabeza, 141: dentro de las cuencas, tapadas por el globo ocular.

## Paso 6 — cabeza

Proporciones medidas sobre la foto frontal (respecto al ancho de mejillas):

| Proporción | Foto | Modelo antes | v07 (medido en la malla) |
|---|---:|---:|---:|
| Distancia entre pupilas | 49 % | 32 % | 43 % |
| Ancho del hocico | 68 % | 46 % | 48 % |
| Ancho de la trufa | 26 % | 21 % | 20 % |
| Ancho del ojo | 16 % | 13 % | 16 % |

Cómo se mide la v07, sobre `Jaguar_Head` (ancho 0.219 m):
- Pupilas: distancia en X entre centros de ojo.
- Hocico: ancho de la franja 3–4.5 cm por detrás de la punta de la nariz.
- Trufa: ancho de los 8 mm delanteros.
- Ojo: apertura del párpado.

**El hocico y la trufa siguen estrechos frente a la foto.** La proyección de la
malla limpia y la escala de la cabeza (×0.90 del ajuste) se comen parte del
ensanche de la escultura. Esto explica buena parte de la lectura «cachorro» de
frente.

Cambios:
- Ojos 4.4 mm más separados en x y radio 21.5 mm.
- Trufa ancha y punto más adelantado de la cabeza; hocico corto. Las
  almohadillas de bigotes van debajo de la nariz y se funden con los carrillos.
- Filtrum y fosas nasales sutiles.
- Labio superior que cae sobre la mandíbula.
- Arco de cejas fino. Quité el suelo de la órbita, que dibujaba «gafas».
- Pómulos y carrillos 4–5 mm más estrechos (ancho de cabeza 0.219 m).
- Orejas en las esquinas superiores, inclinadas 40° hacia fuera y 12 % más
  altas que anchas, con concavidad interna (resta `ear_cup`).

**Crítica honesta:** de perfil y en primer plano ya se lee un felino: trufa,
almohadillas, ojo almendrado con párpado. De frente sigue pareciendo más un
cachorro de león que un jaguar adulto, y las orejas son demasiado de disco y
quedan altas: en la superposición frontal faltan las orejas, que en la foto
sobresalen por los lados. Con 32 vértices por anillo de cabeza, el detalle
facial fino es trabajo de esculpido/normal map.

## Paso 7 — zarpas

Escultura:
- Bloque central más pequeño y 4 dedos con surcos entre lóbulos (mezcla de 6 mm).
- Almohadilla central (metacarpal/metatarsal) y almohadilla carpal.
- Espolón en las delanteras.
- Anchos: delantera 0.106 m y trasera 0.096 m (objetivo 0.11 y 0.095).

Malla limpia:
- 4 anillos de zarpa (antes 3).
- Los vértices se concentran delante, en los dedos (θ' = θ − a·sin(θ − θ_frente),
  hasta a = 0.42), y la densidad crece poco a poco desde el metacarpo para no
  retorcer la pata.
- Los dedos se ven en la escultura (`renders/v07/sculpt/`). En la malla limpia,
  con ~6 mm entre vértices delante, solo se insinúan como un festón: el
  espolón y las almohadillas quedan para el normal map.

## v07 — resultado

**IoU:**

| | Lateral | Frontal |
|---|---:|---:|
| v06 (línea base) | 0.533 | 0.747 |
| v07, escultura | 0.801 | 0.830 |
| v07, malla limpia posada como en las fotos | 0.782 | 0.832 |

La malla limpia se posa con *skinning* rígido suave por hueso sobre los mismos
landmarks. Superposiciones en `renders/v07/iou/`, incluida la comparación
`antes_despues_iou.png`.

**Criterios no alcanzados:** IoU lateral ≥ 0.90 y frontal ≥ 0.85. Lo que limita,
según las superposiciones:
1. La foto es de un animal más compacto, profundo y pesado. Con ±8 % y ≤ ~95 kg
   no se puede copiar su vientre y su lomo: el ajuste sin restricciones pedía
   ~107 kg.
2. Las patas y las zarpas de la foto están en zancada y en perspectiva, y las
   zarpas casi no tienen área en común.
3. La foto frontal tiene perspectiva fuerte y otra pose; las orejas no coinciden.
4. Errores de un par de cm en piezas finas (cola, patas) cuestan mucho IoU.

**Medidas:** las 14, dentro de ±8 % (`renders/v07/measurements.md`).

**Masa** (volumen real de la unión): 98.2 kg a 1000 kg/m³, **≈ 3 % por encima de
95**. Lo elegí a propósito. Con ≤ 95 kg, el tórax quedaba en 0.26–0.29 m (−10…−19 %),
fuera de ±8 % y con cintura de «hueso de perro». Prefiero cumplir las medidas y
el juicio visual (tórax de barril) y quedar algo por encima de la masa
aproximada, que encaja con un macho grande del Pantanal.

**Entregables:**
- `export/landmarks.json`, regenerado con el mismo desplazamiento que la malla.
- `export/jaguar_base_v07.glb`.
- `blend/jaguar_v07.blend`.
- `blend/jaguar_v07_sculpt.blend`: escultura de 0.31 M triángulos, cuerpo a 5 mm
  y cabeza a 3 mm.
- Renders cuadrados ajustados, sin píxeles quemados: `renders/v07/` y
  `renders/v07/sculpt/`.
- Comparación de contact sheets: `renders/v07/antes_despues_contact.png`.

**Reproducibilidad:**
- `python src/build_jaguar.py --version v07 --export-glb` (venv con
  `requirements.txt`) regenera todo en ~5 min.
- `blender -b -P src/build_jaguar.py -- --version v07`, con el Blender 4.0.2 real
  y en una copia limpia, genera la malla en 19 s con medidas idénticas. Omite
  con aviso el IoU y la escultura porque ese Python no tiene OpenCV ni
  scikit-image.

**Qué sigue débil:**
1. Cabeza de frente (cachorro de león) y orejas de disco.
2. Malla limpia más lisa que la escultura: dedos y musculatura sólo insinuados.
3. Auto-intersecciones locales en la unión trasera, la raíz de la cola y las
   cuencas.
4. IoU por debajo del objetivo, por los motivos de arriba.
5. Masa algo alta.
