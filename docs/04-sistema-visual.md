# Sistema visual

Cómo está construida la capa visual de Fit-Up y por qué. Documenta el rediseño de la rama
`design`, que **no toca funcionalidad**: mismas pantallas, mismas rutas, mismos controles,
mismos datos.

## La dirección: herramienta de trabajo

Se dibujaron tres direcciones para la pantalla «Hoy» y se eligió la tercera, **«Taller»**:
la app como herramienta de trabajo. Las otras dos —«Rango», que llevaba la escalera
Iron→Radiant a toda la interfaz, y «Cuaderno», un diario tipográfico con serif de alto
contraste— quedan descartadas, pero el porqué de la elegida se entiende mejor con ellas al
lado: lo que se buscaba no era personalidad ni calma, sino **ver más cosas ciertas por
pantalla y decidir sin navegar**.

De ahí salen las cinco decisiones que gobiernan todo lo demás:

1. **Cifras monoespaciadas.** Comparar dos filas debe ser mirar, no leer.
2. **Contexto permanente.** La semana y los dos datos que la enmarcan viven en una barra
   fija, no a un clic de distancia.
3. **Tabla antes que tarjeta.** Series, objetivo, carga y descanso caen siempre en la misma
   columna.
4. **La acción, siempre alcanzable.** El botón de registrar se ancla al pie.
5. **Denso en el PC, cómodo en el móvil.** No es la misma pantalla encogida.

Todo vive en tres ficheros:

- `frontend/src/styles.css` — fichas de color, escala, primitivas y bloques por pantalla.
- `frontend/src/components/icons.tsx` — los iconos, como trazados propios.
- `frontend/src/components/mando.tsx` — la barra de mando y la tira de semana.

Sin framework CSS ni dependencia de iconos ni de animación.

---

## 1. Fichas de color: nueve por tema, el resto derivado

Un tema declara **nueve colores** y nada más:

```css
[data-tema="oceano"] {
  --bg: #061116;   --surface: #0e1d25;  --surface-2: #152a34;
  --border: #22414f;
  --text: #e1f0f6; --text-dim: #96b5c1; --text-faint: #6b8896;
  --accent: #2ee6d6; --accent-ink: #00201d;
}
```

Todo lo demás se calcula con `color-mix` sobre esos nueve, en `:root`:

| Ficha | Para qué |
|---|---|
| `--surface-3` | superficie elevada: hover de botón, celda de calendario señalada |
| `--border-soft` / `--border-strong` | separadores internos / borde de un control activo |
| `--accent-soft`, `--accent-soft-2` | fondo teñido de la pestaña activa, del hito, del preset |
| `--anillo` | anillo de foco de teclado |
| `--campo` | fondo de `input` y `select` |

Añadir un tema sigue siendo **escribir un bloque de nueve líneas**.

El tema por defecto pasó de «Carbón» a un grafito más frío (`--bg: #0b0f15`), que es el
fondo sobre el que las bandas alternas de la tabla y los filetes de 1 px se leen sin subir
el contraste hasta el ruido.

Los colores de estado del día (`--done`, `--partial`, `--pending`, `--missed`…) solo se
retocan en el tema claro, donde los tonos pensados para fondo oscuro pierden contraste. En
los oscuros son idénticos: son el vocabulario del calendario —y ahora también el de la
tira de semana— y cambiarlos con cada tema obligaría a reaprenderlo.

### El acento tiene dos trabajos

Pintar **texto** sobre el fondo del tema y **rellenar** un botón piden tonos distintos. En
los temas oscuros el mismo vale para los dos. En el claro no: para que el texto llegue a
4,5:1 sobre blanco hay que oscurecer el ámbar tanto que, como relleno, el botón principal
sale marrón. Por eso hay dos fichas: `--accent` escribe (en claro, `#9a5f00`) y
`--accent-solido` rellena (`#eda21f` con tinta oscura encima, 9:1).

### Contraste

`--text-faint` está en 5,4:1 sobre el fondo. Es el color de `.faint`, de las cabeceras de
columna y de los rótulos de grupo, todo texto pequeño: por debajo de 4,5:1 no cumple AA, y
en una interfaz densa eso se nota el doble.

---

## 2. Profundidad: filo de luz en oscuro, sombra en claro

Sobre un fondo casi negro una sombra no se ve. Lo que separa una tarjeta del fondo es
`--brillo`, una línea de luz de 1 px en el canto superior. En el tema claro `--brillo` es
`none` y manda `--sombra-1`.

Los radios se acortaron (`--radius` de 16 a 10 px, los controles a 5-7): una herramienta de
trabajo tiene cantos, no cojines.

## 3. Material translúcido, y solo donde hace falta

La barra de mando, la de navegación, la de acción y los avisos son capas translúcidas con
`backdrop-filter`, y el contenido pasa **por debajo**.

En móvil, donde no hay barra de mando, la cabecera de página se queda pegajosa y el
material solo aparece **cuando hay algo debajo que separar**: la cabecera va plana arriba
del todo y el cristal se forma en los primeros 4 rem de scroll, con
`animation-timeline: scroll()`. En escritorio la cabecera de página deja de ser pegajosa
porque ya hay una cromada permanente arriba.

`@media (prefers-reduced-transparency: reduce)` convierte esas capas en opacas en lugar de
quitarles el fondo, que dejaría las barras flotando.

## 4. Tipografía: una para leer, otra para contar

- **Inter** para todo el texto: interfaz, titulares y marca. Un grotesco neutro no compite
  con el dato, que es lo que se viene a leer. La jerarquía la hacen el peso y el espacio.
- **IBM Plex Mono** para **las cifras**: kilos, repeticiones, tiempos, puntuaciones, días
  del calendario y el reloj del descanso. En una tabla, las cifras monoespaciadas se
  alinean columna con columna y se comparan de un vistazo; con la proporcional hay que
  leerlas una a una.

Antes había una tercera familia, **Outfit**, para titulares y rangos. Se retiró: su hueco
lo ocupa Plex Mono, que hace un trabajo que Inter no hacía y pesa menos de lo que ocupaba
Outfit. Las dos son OFL y viajan en `licenses/`.

El espaciado (`--sp-1` … `--sp-10`) va en `rem`, no en píxeles: si alguien sube el tamaño
de letra del navegador, la caja crece con el texto en vez de estrangularlo. `body` va a
`font-size: 1rem` por lo mismo. `--tap: 44px` se queda en píxeles a propósito: mide un
dedo, no una letra.

El tracking es **específico del tamaño**, nunca uno solo para todos: `h1` a `-0.022em`, el
texto pequeño a `+0.005em`. El margen lateral es `clamp(0.875rem, 2vw, 1.5rem)`.

## 5. Movimiento

Dos curvas propias y un muelle, porque las del navegador son flojas:

```css
--sal:     cubic-bezier(0.23, 1, 0.32, 1);     /* lo que entra o responde al dedo */
--ent-sal: cubic-bezier(0.77, 0, 0.175, 1);    /* lo que se desplaza */
--muelle:  linear(0, 0.0849, …, 1);            /* ζ≈0,72, ~4 % de rebasamiento */
```

`--muelle` es un muelle subamortiguado descrito punto a punto con `linear()`: la curva de
un resorte real, sin librería. Se usa donde algo aparece **desde** un sitio —el menú desde
su botón, el aviso desde abajo—. En un cambio de estado tranquilo el rebote se lee como un
fallo, así que ahí no entra. `ease-in` no aparece en toda la hoja: empieza lento y hace que
la interfaz parezca que va con retraso.

| Gesto | Qué hace | Por qué |
|---|---|---|
| Pulsar un botón, un día, un preset | `scale(0.97)` en 120 ms | Responde al **pulsar**, no al soltar |
| Cambiar de pestaña | Solo opacidad, 160 ms | Se hace decenas de veces al día |
| Aviso | Entra desde abajo con muelle y desenfoque (380 ms); sale por el mismo sitio en 180 ms | Viene de donde está la acción que lo provoca |
| Menú de ajustes | Crece con muelle desde abajo a la izquierda | Nace en su botón |
| Esqueleto de carga | Barrido de luz | El parpadeo se lee como "esto está roto" |

`touch-action: manipulation` quita el retardo de ~300 ms del doble toque, y
`-webkit-tap-highlight-color: transparent` apaga el destello del sistema, que llega tarde y
tapa el nuestro. Los `:hover` decorativos van dentro de
`@media (hover: hover) and (pointer: fine)`.

### Las tres señales de accesibilidad

| Señal | Qué hace la app |
|---|---|
| `prefers-reduced-motion` | Quita desplazamiento, escala y pulso. **No la respuesta**: color y opacidad se quedan |
| `prefers-reduced-transparency` | Las capas translúcidas se vuelven sólidas, no invisibles |
| `prefers-contrast: more` | Bordes reales, texto secundario que deja de ser un matiz, cromada opaca |

## 6. Iconos propios en lugar de emojis

`components/icons.tsx`: veintitantos trazados en rejilla de 24, `currentColor`, grosor
1,75. El tamaño lo fija el CSS.

Dos motivos, y el segundo pesa más:

1. Cada sistema operativo dibuja los emojis a su manera.
2. **Los estados del día se distinguían solo por color.** 🟢🟡🟠🔴 son el mismo círculo
   pintado siete veces, y la regla de la casa es que un estado nunca se comunica solo por
   color. Ahora cada uno tiene su forma —marca, media luna, punteado, aspa, `+`, guion,
   barra— y se leen igual en escala de grises. Lo mismo con los cuatro veredictos de la
   progresión.

Los iconos son decorativos por defecto (`aria-hidden`). Donde va uno solo —reordenar un
ejercicio, arrancar el descanso de una fila— el botón lleva `aria-label`.

## 7. Las piezas de «Taller»

### Barra de mando (`.mando`, solo escritorio)

Lleva lo que no cambia al navegar: la marca, la **tira de semana** y dos datos —
cumplimiento del mes y peso corporal—. Ninguna pantalla tiene que repetirlos.

La tira de semana existe por una razón concreta: saber en qué punto de la semana vas era ir
al Calendario y volver. Usa el mismo vocabulario de color que el calendario y cada día
enlaza a su detalle (`/calendario?dia=YYYY-MM-DD`, que la pantalla lee para abrir ese día y
no el de hoy).

Los datos que no existen **no se inventan**: si no hay peso registrado, pone `—`.

### Rail agrupado

Ocho pestañas seguidas son una lista; agrupadas en **Registro / Plan / Análisis** son un
mapa. Los títulos solo aparecen en la barra lateral: en la barra inferior del móvil no hay
sitio, y allí las pestañas se leen seguidas en ese mismo orden. La activa se rellena y su
icono toma el acento; el texto se queda blanco, porque a 32 px un texto en color se lee
como un enlace y no como «estás aquí».

### Tabla de la sesión (`.tabla`)

`#`, ejercicio, series, objetivo, carga, descanso y la acción de descansar. `plannedColumns`
(en `ui.tsx`) parte el plan en esas columnas y **no promedia nada**: cuando las series no
son uniformes, el objetivo lleva la descripción entera y la carga queda vacía. Un número
inventado en la columna «Carga» sería peor que un hueco, porque parecería un dato.

Bandas alternas en vez de un filete por fila: con seis columnas, el ojo sigue mejor una
banda.

### Barra de acción (`.barra-accion`)

Anclada al pie en escritorio: con una rutina larga, el botón de registrar quedaba por
debajo del pliegue justo los días en que hay más que hacer. En móvil se queda en el flujo,
porque abajo ya está la barra de navegación y dos barras apiladas son una de más.

### Inspector (`.inspector`)

La columna derecha de «Hoy»: lo que el sistema propone, sin salir de la pantalla. La fila
entera es el enlace —un botón «Revisar» al lado obligaba a apuntar a un objetivo pequeño
para hacer lo único que se hace ahí—, y la cuenta de la cabecera es de **ejercicios**, no
de rutinas, porque es lo que hay que revisar.

## 8. La escalera de tamaños

No hay "versión móvil" y "versión escritorio": hay una escalera, y cada peldaño existe
porque a ese ancho cabe algo que antes no cabía.

| Desde | Qué cambia |
|---|---|
| 320 px | Todo funciona. Las etiquetas de la barra inferior bajan un punto antes que recortarse |
| 375 px | Base del móvil. La barra del ranking desaparece de la lista de músculos: le sobraban treinta píxeles |
| 600 px | Vuelve la barra del ranking |
| **760 px** | La tabla de la sesión se despliega en columnas. Por debajo se pliega a dos líneas por ejercicio —nombre y descanso arriba, la prescripción a la derecha—: seis columnas no caben en un móvil |
| 700 px | El calendario pasa a celdas altas con el nombre de la rutina |
| 900 px | Aparece la barra de mando. La navegación pasa a columna lateral. «Hoy» se parte en dos. Todo se aprieta un punto: controles de 34 px, tabla de 42, letra un escalón menor |
| 1080 px | Calendario y Cuerpo abren su panel de detalle a la derecha |

El móvil **no se aprieta**: targets de 44 px y letra grande, que es lo que pide el gimnasio.
La densidad es una decisión del escritorio, donde hay ratón y se viene a comparar datos.

En apaisado, el anillo del temporizador entra también por altura
(`min(340px, 78vw, 58vh)`).

## 9. Arreglos que salieron por el camino

- `ToastProvider` no cancelaba el reloj del aviso anterior: dos avisos seguidos se pisaban.
  Ahora cada uno cancela los pendientes y el desmontaje espera a la animación de salida.
- Las flechas de reordenar del editor de rutinas no tenían nombre accesible.

## 10. Qué NO cambió

- Ninguna ruta, ningún endpoint, ningún contrato. `openapi.json` está intacto.
- Las mismas ocho pestañas y los mismos destinos. Lo único que cambió es su **orden**, para
  agruparlas: Hoy · Calendario · Descanso · Rutinas · Semana · Cuerpo · Historial · Ajustes.
- Los siete temas.
- El mapa corporal: `bodyPaths.ts` no se ha tocado. La partición del cuerpo la sigue
  mandando el catálogo.
- La escalera de rangos y sus nueve colores.
- Todos los objetivos táctiles siguen en 44 px en móvil.
