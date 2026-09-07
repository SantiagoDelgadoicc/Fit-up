/**
 * Mapa corporal: dos siluetas esquemáticas, frontal y dorsal.
 *
 * El dibujo es deliberadamente geométrico. No pretende ser una lámina de
 * anatomía: pretende que se localice un músculo de un vistazo y se pueda tocar
 * con el dedo.
 *
 * Se dibuja en tres capas —silueta de fondo, músculos, articulaciones— para
 * que un grupo sin datos no deje un agujero con forma de nada y para que las
 * zonas no tengan que encajar entre sí como un puzle.
 *
 * El cuerpo es simétrico, así que cada músculo par se define **una vez** para
 * el lado izquierdo y se dibuja también reflejado. Las zonas se identifican
 * por `svg_key`, que viene del catálogo: añadir un músculo es añadir su forma
 * aquí y su fila en `muscles.json`, sin tocar lógica.
 *
 * El relleno dice el rango y el borde dice la actividad reciente. Como ninguna
 * de las dos cosas puede quedarse solo en color, cada zona lleva etiqueta
 * accesible, el "sin datos" va con trama, y la pantalla repite todo en forma
 * de lista.
 */

import type { KeyboardEvent } from "react";

import type { MuscleRanking } from "../api/client";
import { tierLabel } from "./ui";

type Shape =
  | { d: string }
  | { cx: number; cy: number; rx: number; ry: number }
  | { x: number; y: number; w: number; h: number; r?: number };

/** Formas de una zona. `mirrored` la dibuja también en el lado derecho. */
type Region = { shapes: Shape[]; mirrored?: boolean };

export type BodyView = "frontal" | "dorsal";

const region = (shapes: Shape[], mirrored = true): Region => ({ shapes, mirrored });

/* Coordenadas en un lienzo de 200x440, con el eje de simetría en x = 100. */

/** Capa de fondo: la forma del cuerpo, sin músculo asignado. */
const SILHOUETTE: Region[] = [
  region([{ cx: 100, cy: 32, rx: 19, ry: 23 }], false), // cabeza
  region([{ x: 93, y: 50, w: 14, h: 18 }], false), // cuello
  // Torso: hombros anchos, cintura estrecha, cadera.
  region([{ d: "M72 76 Q100 64 128 76 L124 150 Q120 206 100 212 Q80 206 76 150 Z" }], false),
  region([{ x: 32, y: 82, w: 24, h: 142, r: 12 }]), // brazo
  region([{ x: 75, y: 202, w: 24, h: 212, r: 12 }]), // pierna
  region([{ cx: 85, cy: 424, rx: 14, ry: 8 }]), // pie
];

/** Articulaciones, por encima de los músculos: los delimitan. */
const JOINTS: Region[] = [
  region([{ cx: 44, cy: 160, rx: 10, ry: 7 }]), // codo
  region([{ cx: 38, cy: 216, rx: 10, ry: 11 }]), // mano
  region([{ cx: 87, cy: 330, rx: 13, ry: 8 }]), // rodilla
];

const FRONT: Record<string, Region> = {
  traps: region([{ d: "M84 70 L100 66 L100 80 L76 86 Z" }]),
  delt_front: region([{ cx: 70, cy: 92, rx: 13, ry: 15 }]),
  delt_side: region([{ cx: 52, cy: 96, rx: 10, ry: 14 }]),
  chest: region([{ d: "M78 88 Q98 82 98 88 L98 122 Q82 128 76 114 Z" }]),
  abs: region([{ x: 88, y: 126, w: 24, h: 66, r: 9 }], false),
  obliques: region([{ d: "M78 130 Q86 128 86 136 L86 188 Q80 186 77 172 Z" }]),
  biceps: region([{ cx: 44, cy: 130, rx: 11, ry: 26 }]),
  forearm: region([{ cx: 40, cy: 188, rx: 10, ry: 26 }]),
  // El hueco entre los dos muslos lo ocupan los aductores, por dentro.
  quads: region([{ d: "M77 214 Q88 210 95 216 L94 320 L79 320 Z" }]),
  adductors: region([{ d: "M96 218 L100 218 L100 276 L95 276 Z" }]),
  calves: region([{ cx: 86, cy: 368, rx: 11, ry: 30 }]),
};

const BACK: Record<string, Region> = {
  traps: region([{ d: "M100 64 L120 72 L112 108 L100 114 L88 108 L80 72 Z" }], false),
  delt_rear: region([{ cx: 70, cy: 92, rx: 13, ry: 15 }]),
  delt_side: region([{ cx: 52, cy: 96, rx: 10, ry: 14 }]),
  rhomboids: region([{ d: "M87 110 L99 114 L99 138 L87 134 Z" }]),
  lats: region([{ d: "M78 108 Q88 118 88 140 L88 176 Q76 166 76 132 Z" }]),
  lower_back: region([{ x: 89, y: 142, w: 22, h: 48, r: 8 }], false),
  triceps: region([{ cx: 44, cy: 130, rx: 11, ry: 26 }]),
  forearm: region([{ cx: 40, cy: 188, rx: 10, ry: 26 }]),
  glutes: region([{ d: "M78 194 Q97 190 99 202 L99 238 Q82 242 76 222 Z" }]),
  hamstrings: region([{ d: "M79 242 Q88 240 96 244 L94 320 L80 320 Z" }]),
  calves: region([{ cx: 86, cy: 368, rx: 11, ry: 30 }]),
};

const SHAPES: Record<BodyView, Record<string, Region>> = { frontal: FRONT, dorsal: BACK };

const MIRROR = "translate(200,0) scale(-1,1)";

/**
 * Frescura del estímulo — el halo de ADR-0003.
 *
 * Es actividad, no rango: contesta "¿lo estoy entrenando?", nunca "¿qué tal lo
 * tengo?". Por eso viaja en el borde y no en el relleno.
 */
export function freshness(days: number | null | undefined): "fresh" | "warm" | "cold" | "none" {
  if (days === null || days === undefined) return "none";
  if (days <= 7) return "fresh";
  if (days <= 21) return "warm";
  return "cold";
}

export const FRESHNESS_LABEL: Record<string, string> = {
  fresh: "Entrenado esta semana",
  warm: "Entrenado este mes",
  cold: "Sin estímulo reciente",
  none: "Nunca registrado",
};

function renderShape(shape: Shape, props: Record<string, unknown>, key: number) {
  if ("cx" in shape) return <ellipse key={key} {...props} {...shape} />;
  if ("x" in shape) {
    return (
      <rect
        key={key}
        {...props}
        x={shape.x}
        y={shape.y}
        width={shape.w}
        height={shape.h}
        rx={shape.r ?? 6}
      />
    );
  }
  return <path key={key} {...props} d={shape.d} />;
}

function Layer({ pieces, className }: { pieces: Region[]; className: string }) {
  return (
    <>
      {pieces.map((piece, i) => (
        <g key={i}>
          <g>{piece.shapes.map((s, j) => renderShape(s, { className }, j))}</g>
          {piece.mirrored && (
            <g transform={MIRROR}>
              {piece.shapes.map((s, j) => renderShape(s, { className }, j))}
            </g>
          )}
        </g>
      ))}
    </>
  );
}

function MuscleZone({
  shapes,
  muscle,
  selected,
  onSelect,
}: {
  shapes: Region;
  muscle: MuscleRanking;
  selected: boolean;
  onSelect: () => void;
}) {
  const common = {
    className: "zone",
    "data-tier": muscle.tier,
    "data-fresh": freshness(muscle.days_since_stimulus),
    "data-selected": selected || undefined,
    onClick: onSelect,
  };
  // Solo el lado izquierdo entra en el orden de tabulación: para el teclado el
  // músculo es uno, aunque se dibuje dos veces.
  const focusable = {
    ...common,
    role: "button" as const,
    tabIndex: 0,
    "aria-label": `${muscle.name}: ${tierLabel(muscle.tier)}`,
    "aria-pressed": selected,
    onKeyDown: (e: KeyboardEvent) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        onSelect();
      }
    },
  };

  return (
    <>
      <g>{shapes.shapes.map((s, i) => renderShape(s, focusable, i))}</g>
      {shapes.mirrored && (
        <g transform={MIRROR} aria-hidden="true">
          {shapes.shapes.map((s, i) => renderShape(s, common, i))}
        </g>
      )}
    </>
  );
}

export default function BodyMap({
  view,
  entries,
  selected,
  onSelect,
}: {
  view: BodyView;
  entries: MuscleRanking[];
  selected: string | null;
  onSelect: (slug: string) => void;
}) {
  const bySvgKey = new Map(entries.map((e) => [e.svg_key, e]));
  const patternId = `sin-datos-${view}`;

  return (
    <figure className="body-map">
      <svg viewBox="0 0 200 440" role="group" aria-label={`Vista ${view}`}>
        <defs>
          {/* "Sin datos" no puede distinguirse solo por color: lleva trama. */}
          <pattern
            id={patternId}
            width="6"
            height="6"
            patternTransform="rotate(45)"
            patternUnits="userSpaceOnUse"
          >
            <rect width="6" height="6" fill="var(--surface-2)" />
            <line x1="0" y1="0" x2="0" y2="6" stroke="var(--border)" strokeWidth="2.5" />
          </pattern>
        </defs>

        <g style={{ ["--sin-datos" as string]: `url(#${patternId})` }}>
          <Layer pieces={SILHOUETTE} className="silhouette" />

          {Object.entries(SHAPES[view]).map(([svgKey, shapes]) => {
            const muscle = bySvgKey.get(svgKey);
            if (!muscle) return null;
            return (
              <MuscleZone
                key={svgKey}
                shapes={shapes}
                muscle={muscle}
                selected={selected === muscle.muscle_slug}
                onSelect={() => onSelect(muscle.muscle_slug)}
              />
            );
          })}

          <Layer pieces={JOINTS} className="joint" />
        </g>
      </svg>
      <figcaption>{view === "frontal" ? "Vista frontal" : "Vista dorsal"}</figcaption>
    </figure>
  );
}
