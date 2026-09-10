/**
 * Barra de mando: la cromada permanente del escritorio.
 *
 * Lleva lo que no cambia al navegar —la marca, la semana y los dos datos que
 * dan contexto a todo lo demás— para que ninguna pantalla tenga que repetirlo.
 *
 * La semana está ahí por una razón concreta: saber en qué punto de la semana
 * vas era ir al Calendario y volver. Ahora se ve siempre, con el mismo
 * vocabulario de color que el calendario, y cada día lleva a su detalle.
 *
 * En móvil no existe: allí la navegación es la barra inferior y la pantalla
 * no sobra para una segunda banda fija.
 */

import { Link } from "react-router-dom";

import { localDate } from "../api/client";
import { useBodyweight, useCalendar } from "../api/hooks";
import type { DayState } from "../api/client";
import { stateLabel } from "./ui";

const LETRAS = ["L", "M", "X", "J", "V", "S", "D"];

/** Fecha local en ISO, sin pasar por UTC. */
const iso = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

/** Los siete días de la semana en curso, de lunes a domingo. */
function semanaDe(hoy: string): Date[] {
  const [y, m, d] = hoy.split("-").map(Number);
  const base = new Date(y!, (m ?? 1) - 1, d!);
  const lunes = new Date(base);
  // getDay() cuenta desde el domingo; la semana española empieza en lunes.
  lunes.setDate(base.getDate() - ((base.getDay() + 6) % 7));
  return Array.from({ length: 7 }, (_, i) => {
    const dia = new Date(lunes);
    dia.setDate(lunes.getDate() + i);
    return dia;
  });
}

export function Mando() {
  const hoy = localDate();
  const dias = semanaDe(hoy);
  const primero = dias[0]!;
  const ultimo = dias[6]!;
  const [y, m] = hoy.split("-").map(Number);

  // Una semana cae como mucho en dos meses. Los tres `useCalendar` se piden
  // siempre —los hooks no pueden ser condicionales— y react-query une los que
  // repiten clave, así que en la mayoría de las semanas es una sola petición.
  const mesA = useCalendar(primero.getFullYear(), primero.getMonth() + 1);
  const mesB = useCalendar(ultimo.getFullYear(), ultimo.getMonth() + 1);
  const mesHoy = useCalendar(y!, m!);
  const peso = useBodyweight();

  const porFecha = new Map(
    [...(mesA.data?.days ?? []), ...(mesB.data?.days ?? [])].map((d) => [d.date, d]),
  );

  const adherencia = mesHoy.data?.adherence;

  return (
    <header className="mando">
      <Link className="mando-marca" to="/">
        {/* Decorativo: el nombre va escrito justo al lado. */}
        <span className="brand-mark" aria-hidden="true" />
        Fit-Up
      </Link>

      <span className="mando-sep" aria-hidden="true" />

      <nav className="semana-tira" aria-label="Esta semana">
        {dias.map((dia, i) => {
          const fecha = iso(dia);
          const info = porFecha.get(fecha);
          const estado = info?.state as DayState | undefined;
          return (
            <Link
              key={fecha}
              className="semana-dia"
              to={`/calendario?dia=${fecha}`}
              data-state={estado}
              aria-current={fecha === hoy ? "date" : undefined}
              aria-label={`${LETRAS[i]} ${dia.getDate()}${estado ? `: ${stateLabel(estado)}` : ""}`}
            >
              <span className="semana-dia-letra" aria-hidden="true">
                {LETRAS[i]}
              </span>
              <span className="semana-dia-num" aria-hidden="true">
                {String(dia.getDate()).padStart(2, "0")}
              </span>
            </Link>
          );
        })}
      </nav>

      <div className="spacer" />

      {/* Los dos datos que contextualizan el resto. Si no hay, se dice. */}
      <span className="mando-dato">
        cumplimiento{" "}
        <strong>
          {adherencia === null || adherencia === undefined
            ? "—"
            : `${Math.round(adherencia * 100)}%`}
        </strong>
      </span>
      <span className="mando-dato">
        peso <strong>{peso.data ? `${peso.data.weight_kg} kg` : "—"}</strong>
      </span>
    </header>
  );
}
