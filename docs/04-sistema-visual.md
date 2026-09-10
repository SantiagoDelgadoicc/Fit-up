# Sistema visual

Cómo está construida la capa visual de Fit-Up y por qué. Documenta el rediseño de la rama
`design`, que **no toca funcionalidad**: mismas pantallas, mismas rutas, mismos controles,
mismos datos. Lo que cambia es cómo se ven y cómo responden.

Todo vive en dos ficheros:

- `frontend/src/styles.css` — fichas de color, escala, primitivas y bloques por pantalla.
- `frontend/src/components/icons.tsx` — los iconos, como trazados propios.

Sigue sin haber framework CSS ni dependencia de iconos ni de animación: son diez pantallas
y unas pocas primitivas, y una dependencia de diseño costaría más de lo que ahorra.

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

Añadir un tema sigue siendo **escribir un bloque de nueve líneas**. Antes había que
reajustar a mano cada tono derivado; ahora ninguno se declara dos veces.

Los colores de estado del día (`--done`, `--partial`, `--pending`, `--missed`…) solo se
retocan en el tema claro, donde los tonos pensados para fondo oscuro pierden contraste. En
los oscuros son idénticos: son el vocabulario del calendario y cambiarlos con cada tema
obligaría a reaprenderlo.

### El acento tiene dos trabajos

Pintar **texto** sobre el fondo del tema y **rellenar** un botón o una pastilla piden tonos
distintos. En los temas oscuros el mismo vale para los dos. En el claro no: para que el
texto llegue a 4,5:1 sobre blanco hay que oscurecer el ámbar tanto que, usado como relleno,
el botón principal sale marrón. Por eso hay dos fichas:

- `--accent` — texto, enlaces, bordes. En claro, `#9a5f00`.
- `--accent-solido` — relleno del botón principal y de la pastilla de «hoy». En claro,
  `#eda21f` con tinta oscura encima (9:1).

En los temas oscuros `--accent-solido` es simplemente `var(--accent)`.

### Contraste

`--text-faint` se ajustó en ambos extremos (`#6b7684` → `#78838f` en oscuro, `#78828f` →
`#6a7381` en claro). Es el color de `.faint`, que es texto de 0,85 rem: por debajo de 4,5:1
no cumple AA. Ahora está en 4,9:1 sobre el fondo.

---

## 2. Profundidad: filo de luz en oscuro, sombra en claro

Sobre un fondo casi negro una sombra no se ve. Lo que separa una tarjeta del fondo es
`--brillo`, una línea de luz de 1 px en el canto superior (`inset 0 1px 0 rgb(255 255 255 /
5%)`), como una luz rasante sobre material real. En el tema claro `--brillo` es `none` y
manda `--sombra-1`.

Las dos escalas de sombra:

- `--sombra-1` — tarjetas y botones, casi imperceptible.
- `--sombra-2` — lo que flota: menú de ajustes, aviso, píldora del temporizador.

## 3. Material translúcido, y solo donde hace falta

La barra de navegación, la cabecera de página y los avisos son capas translúcidas con
`backdrop-filter`, y el contenido pasa **por debajo** en vez de chocar con una banda opaca.

La cabecera de página (`.page-head`) es **pegajosa**: en Historial o en Cuerpo la lista es
larga y saber en qué pantalla estás —y llegar a su acción principal— no debería costar
volver arriba.

Pero el material solo aparece **cuando hay algo debajo que separar**. Con la página arriba
del todo la cabecera va plana, sin cristal y sin línea; el desenfoque y el degradado se
forman en los primeros 4 rem de scroll, con `animation-timeline: scroll()`:

```css
@supports (animation-timeline: scroll()) {
  .page-head {
    background: transparent;
    backdrop-filter: none;
    animation: cuaja-cabecera linear both;
    animation-timeline: scroll();
    animation-range: 0 4rem;
  }
}
```

Donde el navegador no entiende de líneas de tiempo de scroll, se queda el cristal fijo. Y en
vez de una regla de 1 px bajo la cabecera hay un degradado corto: una línea marcaría un
borde que no existe.

## 4. Escala: espaciado en `rem` y tipografía fluida

El espaciado (`--sp-1` … `--sp-10`) va en `rem`, no en píxeles. Si alguien sube el tamaño de
letra del navegador —por preferencia o por necesidad—, la caja crece con el texto en vez de
estrangularlo; con espaciado fijo, subir la letra dos puntos deja el texto pegado al borde
de la tarjeta. Con la raíz por defecto la escala sigue siendo la de 4 px.

Por el mismo motivo `body` va a `font-size: 1rem` y no a `16px`: imponer píxeles ignora la
preferencia del sistema.

`--tap: 44px` se queda en píxeles a propósito: mide un dedo, no una letra.

El margen lateral de la página es `--margen: clamp(1rem, 3vw, 2.25rem)` — crece de forma
continua con la pantalla en vez de saltar en cada punto de ruptura.

El titular también es fluido: `clamp(1.55rem, 1.3rem + 1.1vw, 1.9rem)`. Y el tracking es
**específico del tamaño**, nunca uno solo para todos: cuanto más grande es la letra, más
separadas se ven entre sí. `h1` va a `-0.028em`, `h2` a `-0.015em`, el texto pequeño a
`+0.005em`.

`.metric-value` y `.timer-clock` usan la familia de titulares (Outfit) con tracking negativo
fuerte: son cifras que se leen de un vistazo, no texto.

## 5. Movimiento

Dos curvas propias y un muelle, porque las del navegador son flojas:

```css
--sal:     cubic-bezier(0.23, 1, 0.32, 1);     /* lo que entra o responde al dedo */
--ent-sal: cubic-bezier(0.77, 0, 0.175, 1);    /* lo que se desplaza */
--muelle:  linear(0, 0.0849, …, 1);            /* ζ≈0,72, ~4 % de rebasamiento */
```

`--muelle` es un muelle subamortiguado descrito punto a punto con `linear()`: la curva de un
resorte real, sin librería. Se usa donde algo aparece **desde** un sitio —el menú desde su
botón, el aviso desde abajo—, que es donde el material se comporta como materia. En un
cambio de estado tranquilo el rebote se lee como un fallo, así que ahí no entra.

`ease-in` no aparece en toda la hoja a propósito: empieza lento y hace que la interfaz
parezca que va con retraso.

| Gesto | Qué hace | Por qué |
|---|---|---|
| Pulsar un botón, un día del calendario, un preset | `scale(0.97)` en 120 ms | Responde al **pulsar**, no al soltar: es lo que hace que la interfaz parezca que te ha oído |
| Cambiar de pestaña | Solo opacidad, 160 ms | Se hace decenas de veces al día; cualquier desplazamiento ahí se acaba percibiendo como lentitud |
| Aviso (toast) | Entra desde abajo con muelle y desenfoque, 380 ms; sale por el mismo sitio en 180 ms | Viene de donde está la acción que lo provoca, y se va por donde vino. Al entrar hay algo que mirar; al salir, ya no |
| Menú de ajustes | Crece con muelle desde abajo a la izquierda | Nace en su botón, no en el centro de la pantalla |
| Esqueleto de carga | Barrido de luz | El parpadeo de opacidad se lee como "esto está roto"; el barrido, como "esto viene" |

### Respuesta inmediata

`touch-action: manipulation` en todo lo pulsable quita el retardo de ~300 ms que el
navegador se guarda por si el toque era un doble toque. Y `-webkit-tap-highlight-color:
transparent` apaga el destello gris del sistema, que llega tarde y tapa el nuestro.

Los `:hover` decorativos van dentro de `@media (hover: hover) and (pointer: fine)`: en
táctil se quedaban pegados después de tocar y parecía que el control seguía seleccionado.

### Las tres señales de accesibilidad

| Señal | Qué hace la app |
|---|---|
| `prefers-reduced-motion: reduce` | Quita desplazamiento, escala y pulso. **No quita la respuesta**: las transiciones de color y opacidad se quedan porque ayudan a entender qué ha cambiado |
| `prefers-reduced-transparency: reduce` | Las capas translúcidas se vuelven sólidas, no invisibles: quitarles el fondo dejaría la barra flotando |
| `prefers-contrast: more` | Bordes reales (42 % del texto), texto secundario que deja de ser un matiz, insignias con borde de 1,5 px y cromada opaca |

## 6. Iconos propios en lugar de emojis

`components/icons.tsx`: veintitantos trazados en rejilla de 24, `currentColor`, grosor
1,75. El tamaño lo fija el CSS, nunca el componente.

Dos motivos, y el segundo pesa más:

1. Cada sistema operativo dibuja los emojis a su manera. La barra lateral se veía distinta
   en el PC y en el móvil, y ninguna de las dos coincidía con la paleta del tema.
2. **Los estados del día se distinguían solo por color.** 🟢🟡🟠🔴 son el mismo círculo
   pintado siete veces, y la regla de la casa es que un estado nunca se comunica solo por
   color. Ahora cada uno tiene su forma:

   | Estado | Símbolo |
   |---|---|
   | Cumplida | círculo con marca |
   | Parcial | círculo medio relleno |
   | Sin registrar | círculo punteado |
   | No realizada | círculo con aspa |
   | Extra | círculo con `+` |
   | Descanso | círculo con guion |
   | Excusado | círculo con barra |

   Se leen igual en escala de grises. Lo mismo con los cuatro veredictos de la progresión
   (flecha arriba, reloj, interrogación, flecha abajo).

Los iconos son decorativos por defecto (`aria-hidden`), porque siempre acompañan al texto
que dice lo mismo. Donde va uno solo —reordenar un ejercicio con las flechas del editor de
rutinas— el botón ahora lleva `aria-label`, que antes le faltaba.

## 7. La escalera de tamaños

No hay "versión móvil" y "versión escritorio": hay una escalera, y cada peldaño existe
porque a ese ancho cabe algo que antes no cabía.

| Desde | Qué cambia |
|---|---|
| 320 px | Todo funciona. Las etiquetas de la barra inferior bajan un punto de cuerpo antes que empezar a recortarse |
| 375 px | Base del móvil. La barra del ranking desaparece de la lista de músculos: le sobraban treinta píxeles y parecía un fallo de maquetación |
| 600 px | Vuelve la barra del ranking |
| 700 px | El calendario pasa a celdas altas **con el nombre de la rutina**: leer el mes de un vistazo es la ventaja de la pantalla grande, y una tablet en vertical ya la tiene |
| 900 px | La navegación pasa de barra inferior a columna lateral, con la caja de ajustes al pie. «Hoy» se parte en dos columnas |
| 1080 px | Calendario y Cuerpo abren su panel de detalle a la derecha, pegajoso bajo la cabecera |

En apaisado, el anillo del temporizador entra también por altura (`min(340px, 78vw, 58vh)`):
con solo `vw` se salía de la pantalla y dejaba los botones fuera de cuadro.

## 8. Cambios por pantalla

- **Navegación.** En escritorio, riel de acento a la izquierda de la pestaña activa: dice
  dónde estás sin depender del color del texto, que a ese tamaño es un matiz. En móvil, las
  ocho pestañas se reparten el ancho **según lo que mide cada nombre**, no a partes
  iguales: con `flex: 1` todas medían 44 px y "Calendario" —que pide 55— chocaba con sus
  vecinas. Sumados, los ocho nombres caben de sobra en 375 px; lo que no cabía era el
  reparto a partes iguales.
- **Hoy.** En pantalla ancha, dos columnas: a la izquierda lo que toca hacer, a la derecha
  lo que hay que decidir (progresiones y días sin anotar). Antes la decisión quedaba por
  debajo del pliegue justo los días con rutina larga, que son los días en que hay algo que
  decidir. **El panel solo existe si tiene contenido**: sin él, la columna se queda en su
  ancho de lectura en vez de estirarse por estirarse.
- **Calendario.** El estado tiñe el fondo de la celda además del borde: el mes se lee como
  manchas, que es como se mira un calendario, y no como catorce bordes. El día de hoy lleva
  su número en una pastilla del acento, porque el borde solo no bastaba cuando el día ya
  tiene su propio color de estado.
- **Ranking.** La barra de cada músculo va en degradado: dos músculos del mismo rango pero
  distinta puntuación se distinguen sin leer la cifra.
- **Semana.** Cada día es una fila con cuerpo propio. En una rejilla desnuda, con dos
  rutinas en un día y ninguna en el siguiente, se perdía de quién era cada selector.
- **Descanso.** Anillo más limpio, halo del color del estado y reloj en la familia de
  titulares. El estado (`EN MARCHA`, `EN PAUSA`) pasa a versalitas con tracking amplio.
- **Estados vacíos.** El icono va dentro de un disco tenue: suelto sobre el fondo parecía un
  error de maquetación, no una ilustración.

## 9. Un arreglo que salió por el camino

`ToastProvider` no cancelaba el reloj del aviso anterior: si salían dos seguidos, el
temporizador del primero escondía al segundo antes de que diera tiempo a leerlo. Ahora cada
aviso cancela los relojes pendientes, y el desmontaje espera a que termine la animación de
salida en vez de quitarlo de golpe.

## 10. Qué NO cambió

- Ninguna ruta, ningún endpoint, ningún contrato. `openapi.json` está intacto.
- La arquitectura de la información: las mismas ocho pestañas, en el mismo orden, con los
  mismos nombres.
- Los siete temas y sus acentos.
- El mapa corporal: `bodyPaths.ts` no se ha tocado. La partición del cuerpo la sigue
  mandando el catálogo.
- La escalera de rangos y sus nueve colores.
- Todos los objetivos táctiles siguen en 44 px.
