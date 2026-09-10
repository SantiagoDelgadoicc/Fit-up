# Sistema visual

Cómo está construida la capa visual de Fit-Up y por qué. Documenta el rediseño de la rama
`design`, que **no toca funcionalidad**: mismas pantallas, mismas rutas, mismos controles,
mismos datos. Lo que cambia es cómo se ven y cómo responden.

Todo vive en dos ficheros:

- `frontend/src/styles.css` — fichas de color, escala, primitivas y bloques por pantalla.
- `frontend/src/components/icons.tsx` — los iconos, como trazados propios.

Sigue sin haber framework CSS ni dependencia de iconos: son diez pantallas y unas pocas
primitivas, y una dependencia de diseño costaría más de lo que ahorra.

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

### Contraste

`--text-faint` se aclaró (`#6b7684` → `#78838f` en oscuro, `#78828f` → `#6a7381` en claro).
Es el color de `.faint`, que es texto de 0,85 rem: por debajo de 4,5:1 no cumple AA. Ahora
está en 4,9:1 sobre el fondo.

---

## 2. Profundidad: filo de luz en oscuro, sombra en claro

Sobre un fondo casi negro una sombra no se ve. Lo que separa una tarjeta del fondo es
`--brillo`, una línea de luz de 1 px en el canto superior (`inset 0 1px 0 rgb(255 255 255 /
5%)`), como una luz rasante sobre material real. En el tema claro `--brillo` es `none` y
manda `--sombra-1`.

Las dos escalas de sombra:

- `--sombra-1` — tarjetas y botones, casi imperceptible.
- `--sombra-2` — lo que flota: menú de ajustes, aviso, píldora del temporizador.

## 3. Material translúcido en la cromada

La barra de navegación, la cabecera de página y los avisos son capas translúcidas con
`backdrop-filter`, y el contenido pasa **por debajo** en vez de chocar con una banda opaca.

La cabecera de página (`.page-head`) ahora es **pegajosa**: en Historial o en Cuerpo la
lista es larga y saber en qué pantalla estás —y llegar a su acción principal— no debería
costar volver arriba. En vez de una regla de 1 px debajo, un degradado corto marca dónde el
contenido se mete debajo: una línea marcaría un borde que no existe.

`@media (prefers-reduced-transparency: reduce)` convierte esas capas en opacas en lugar de
quitarles el fondo, que dejaría la barra flotando.

## 4. Espaciado y tipografía

Escala de 4 px (`--sp-1` … `--sp-10`), sin valores sueltos. Cuatro radios (`--radius-xs`,
`-sm`, base, `-lg`) y `--tap: 44px`, que no cambia.

El tracking es **específico del tamaño**, no un valor único: cuanto más grande es la letra,
más separadas se ven las letras entre sí. `h1` va a `-0.025em`, `h2` a `-0.015em`, el texto
pequeño a `+0.005em`. Un valor fijo para todos los tamaños está mal en algún sitio.

`.metric-value` y `.timer-clock` pasan a la familia de titulares (Outfit) con tracking
negativo fuerte: son cifras que se leen de un vistazo, no texto.

## 5. Movimiento

Dos curvas propias, porque las del navegador son flojas:

```css
--sal:     cubic-bezier(0.23, 1, 0.32, 1);     /* lo que entra o responde al dedo */
--ent-sal: cubic-bezier(0.77, 0, 0.175, 1);    /* lo que se desplaza */
```

`ease-in` no aparece en toda la hoja a propósito: empieza lento y hace que la interfaz
parezca que va con retraso.

Qué se anima y qué no:

| Gesto | Qué hace | Por qué |
|---|---|---|
| Pulsar un botón, un día del calendario, un preset | `scale(0.97)` en 120 ms | Responde al **pulsar**, no al soltar: es lo que hace que la interfaz parezca que te ha oído |
| Cambiar de pestaña | Solo opacidad, 160 ms | Se hace decenas de veces al día; cualquier desplazamiento ahí se acaba percibiendo como lentitud |
| Aviso (toast) | Entra desde abajo con escala, 240 ms | Viene de donde está la acción que lo provoca |
| Menú de ajustes | Crece desde abajo a la izquierda, 180 ms | Desde el botón que lo abre, no desde su centro |
| Esqueleto de carga | Barrido de luz | El parpadeo de opacidad se lee como "esto está roto"; el barrido, como "esto viene" |

`@media (prefers-reduced-motion: reduce)` quita el desplazamiento y el pulso, **no la
respuesta**: las transiciones de color y opacidad se quedan porque ayudan a entender qué ha
cambiado.

Los `:hover` decorativos van dentro de `@media (hover: hover) and (pointer: fine)`: en
táctil se quedaban pegados después de tocar y parecía que el control seguía seleccionado.

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

## 7. Cambios por pantalla

- **Navegación.** En escritorio, riel de acento a la izquierda de la pestaña activa: dice
  dónde estás sin depender del color del texto, que a ese tamaño es un matiz. En móvil, las
  ocho pestañas se reparten el ancho **según lo que mide cada nombre**, no a partes
  iguales: con `flex: 1` todas medían 44 px y "Calendario" —que pide 55— chocaba con sus
  vecinas. Sumados, los ocho nombres caben de sobra en 375 px; lo que no cabía era el
  reparto a partes iguales.
- **Calendario.** El estado tiñe el fondo de la celda además del borde: el mes se lee como
  manchas, que es como se mira un calendario, y no como catorce bordes. El día de hoy lleva
  su número en una pastilla del acento, porque el borde solo no bastaba cuando el día ya
  tiene su propio color de estado.
- **Ranking.** La barra de cada músculo va en degradado: dos músculos del mismo rango pero
  distinta puntuación se distinguen sin leer la cifra. En el móvil la barra desaparece —con
  el nombre fijo en 8,5 rem le sobraban treinta píxeles y parecía un fallo de maquetación—;
  la comparación visual la cubre el mapa, justo encima.
- **Semana.** Cada día es una fila con cuerpo propio. En una rejilla desnuda, con dos
  rutinas en un día y ninguna en el siguiente, se perdía de quién era cada selector.
- **Descanso.** Anillo más limpio, halo del color del estado y reloj en la familia de
  titulares. El estado (`EN MARCHA`, `EN PAUSA`) pasa a versalitas con tracking amplio.
- **Estados vacíos.** El icono va dentro de un disco tenue: suelto sobre el fondo parecía un
  error de maquetación, no una ilustración.

## 8. Qué NO cambió

- Ninguna ruta, ningún endpoint, ningún contrato. `openapi.json` está intacto.
- La arquitectura de la información: las mismas ocho pestañas, en el mismo orden, con los
  mismos nombres.
- Los siete temas y sus acentos.
- El mapa corporal: `bodyPaths.ts` no se ha tocado. La partición del cuerpo la sigue
  mandando el catálogo.
- La escalera de rangos y sus nueve colores.
- Todos los objetivos táctiles siguen en 44 px.
