/**
 * Mapa corporal: dos siluetas anatómicas, frontal y dorsal.
 *
 * Se dibuja en tres capas —silueta de fondo, músculos, articulaciones— para
 * que un grupo sin datos no deje un agujero con forma de nada y para que las
 * zonas no tengan que encajar entre sí como un puzle.
 *
 * Las zonas se identifican por `svg_key`, que viene del catálogo: añadir un
 * músculo es añadir su forma en `bodyPaths.ts` y su fila en `muscles.json`,
 * sin tocar lógica. La geometría vive allí, con la procedencia y las
 * decisiones que se tomaron al traerla; aquí solo se pinta.
 *
 * El relleno dice el rango y el borde dice la actividad reciente. Como ninguna
 * de las dos cosas puede quedarse solo en color, cada zona lleva etiqueta
 * accesible, el "sin datos" va con trama, y la pantalla repite todo en forma
 * de lista.
 */

import type { KeyboardEvent } from "react";

import type { MuscleRanking } from "../api/client";
import { JOINTS, SILHOUETTE, VIEW_BOX, ZONES, type Zone } from "./bodyPaths";
import { tierLabel } from "./ui";

export type { BodyView } from "./bodyPaths";
import type { BodyView } from "./bodyPaths";

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

/* El lienzo del asset es ~3,6 veces mayor que el anterior, así que un
   stroke-width en unidades de usuario se vería casi invisible. Con
   non-scaling-stroke los grosores del CSS siguen siendo píxeles de pantalla y
   dejan de depender del viewBox, que M11 prevé cambiar. */
function Layer({ paths, className }: { paths: string[]; className: string }) {
  return (
    <>
      {paths.map((d, i) => (
        <path key={i} className={className} vectorEffect="non-scaling-stroke" d={d} />
      ))}
    </>
  );
}

function MuscleZone({
  zone,
  clipId,
  muscle,
  selected,
  onSelect,
}: {
  zone: Zone;
  clipId: string;
  muscle: MuscleRanking;
  selected: boolean;
  onSelect: () => void;
}) {
  const common = {
    className: "zone",
    vectorEffect: "non-scaling-stroke" as const,
    clipPath: zone.clip ? `url(#${clipId})` : undefined,
    "data-tier": muscle.tier,
    "data-fresh": freshness(muscle.days_since_stimulus),
    "data-selected": selected || undefined,
    onClick: onSelect,
  };
  // Un músculo son varios trazados (los dos lados, y a veces varios haces),
  // pero para el teclado y el lector de pantalla es uno solo: únicamente el
  // primero entra en el orden de tabulación y lleva la etiqueta.
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
      {zone.paths.map((d, i) =>
        i === 0 ? (
          <path key={i} {...focusable} d={d} />
        ) : (
          <path key={i} {...common} aria-hidden="true" d={d} />
        ),
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
  const zones = Object.entries(ZONES[view]);

  return (
    <figure className="body-map">
      <svg viewBox={VIEW_BOX[view]} role="group" aria-label={`Vista ${view}`}>
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

          {zones.map(([svgKey, zone]) =>
            zone.clip ? (
              <clipPath key={svgKey} id={`clip-${view}-${svgKey}`}>
                {zone.clip.map(([x, y, w, h], i) => (
                  <rect key={i} x={x} y={y} width={w} height={h} />
                ))}
              </clipPath>
            ) : null,
          )}
        </defs>

        <g style={{ ["--sin-datos" as string]: `url(#${patternId})` }}>
          <Layer paths={SILHOUETTE[view]} className="silhouette" />

          {zones.map(([svgKey, zone]) => {
            const muscle = bySvgKey.get(svgKey);
            if (!muscle) return null;
            return (
              <MuscleZone
                key={svgKey}
                zone={zone}
                clipId={`clip-${view}-${svgKey}`}
                muscle={muscle}
                selected={selected === muscle.muscle_slug}
                onSelect={() => onSelect(muscle.muscle_slug)}
              />
            );
          })}

          <Layer paths={JOINTS[view]} className="joint" />
        </g>
      </svg>
      <figcaption>{view === "frontal" ? "Vista frontal" : "Vista dorsal"}</figcaption>
    </figure>
  );
}
