/**
 * Calendario mensual.
 *
 * Pensada para el PC, que es donde se revisa el mes: rejilla a la izquierda y
 * detalle fijo a la derecha, de modo que consultar varios días seguidos no
 * obligue a abrir y cerrar un panel una y otra vez. En móvil el detalle pasa
 * debajo.
 *
 * Lo que la vista no debe hacer es mentir. Un día programado y aún sin
 * registrar sale en naranja punteado, no en rojo, y no cuenta en la
 * adherencia: no es un fallo, es que todavía no lo has anotado.
 */

import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { localDate } from "../api/client";
import type { Calendar as CalendarData, DayState } from "../api/client";
import {
  useCalendar,
  useClearException,
  useDay,
  useDeleteSession,
  useExerciseNames,
  useLogAsPlanned,
  useSetException,
  useSkipDay,
} from "../api/hooks";
import { Icon } from "../components/icons";
import {
  describePerformed,
  describePlanned,
  ErrorCard,
  formatDate,
  Loading,
  StateBadge,
  StateDot,
  stateLabel,
  useToast,
} from "../components/ui";

const WEEKDAYS = ["L", "M", "X", "J", "V", "S", "D"];
const MONTHS = [
  "enero", "febrero", "marzo", "abril", "mayo", "junio",
  "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
];

const LEGEND: DayState[] = ["done", "partial", "pending", "missed", "extra", "excused", "rest"];

export default function CalendarPage() {
  const today = localDate();
  // La tira de semana de la barra de mando enlaza con `?dia=`: entrar por ahí
  // tiene que abrir ese día, no el de hoy.
  const [params] = useSearchParams();
  const pedido = params.get("dia");
  const inicial = pedido && /^\d{4}-\d{2}-\d{2}$/.test(pedido) ? pedido : today;

  const [cursor, setCursor] = useState(() => {
    const [y, m] = inicial.split("-").map(Number);
    return { year: y!, month: m! };
  });
  const [selected, setSelected] = useState<string | null>(inicial);

  const month = useCalendar(cursor.year, cursor.month);

  const shift = (delta: number) =>
    setCursor(({ year, month: m }) => {
      const next = m + delta;
      if (next < 1) return { year: year - 1, month: 12 };
      if (next > 12) return { year: year + 1, month: 1 };
      return { year, month: next };
    });

  // Al cambiar de mes, un detalle que pertenece a otro mes se queda descolgado:
  // la rejilla muestra agosto y el panel habla de septiembre. Se descarta.
  const prefix = `${cursor.year}-${String(cursor.month).padStart(2, "0")}`;
  const visible = selected?.startsWith(prefix) ? selected : null;

  // Teclado: en el PC cambiar de mes con las flechas es más rápido que apuntar
  // a un botón, y no cuesta nada ofrecerlo.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement | null)?.tagName;
      if (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA") return;
      if (e.key === "ArrowLeft") shift(-1);
      if (e.key === "ArrowRight") shift(1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="stack-lg">
      <header className="page-head">
        <div>
          <h1>Calendario</h1>
          <p className="faint" style={{ margin: "2px 0 0" }}>
            {MONTHS[cursor.month - 1]} de {cursor.year}
          </p>
        </div>
        <div className="row-tight">
          <button className="btn btn-sm" onClick={() => shift(-1)} aria-label="Mes anterior">
            <Icon name="flecha-izquierda" />
          </button>
          <button
            className="btn btn-sm"
            onClick={() => {
              const [y, m] = today.split("-").map(Number);
              setCursor({ year: y!, month: m! });
              setSelected(today);
            }}
          >
            Hoy
          </button>
          <button className="btn btn-sm" onClick={() => shift(1)} aria-label="Mes siguiente">
            <Icon name="flecha-derecha" />
          </button>
        </div>
      </header>

      <div className="split">
        <section className="stack">
          {month.isLoading && <Loading rows={3} />}
          {month.error && <ErrorCard error={month.error} />}
          {month.data && (
            <MonthGrid
              data={month.data}
              cursor={cursor}
              today={today}
              selected={visible}
              onSelect={setSelected}
            />
          )}

          <div className="row">
            <div className="cal-legend">
              {LEGEND.map((state) => (
                <span key={state}>
                  <StateDot state={state} />
                  {stateLabel(state)}
                </span>
              ))}
            </div>
          </div>

          <p className="tiny muted" style={{ margin: 0 }}>
            <span className="kbd">←</span> <span className="kbd">→</span> cambian de mes.
          </p>
        </section>

        <aside>
          {visible ? (
            <DayDetail date={visible} today={today} />
          ) : (
            <div className="card muted">Selecciona un día para ver el detalle.</div>
          )}
        </aside>
      </div>
    </div>
  );
}

function MonthGrid({
  data,
  cursor,
  today,
  selected,
  onSelect,
}: {
  data: CalendarData;
  cursor: { year: number; month: number };
  today: string;
  selected: string | null;
  onSelect: (date: string) => void;
}) {
  const byDate = useMemo(
    () => new Map(data.days.map((d) => [d.date, d])),
    [data.days],
  );

  const first = new Date(cursor.year, cursor.month - 1, 1);
  const daysInMonth = new Date(cursor.year, cursor.month, 0).getDate();
  // getDay() cuenta desde el domingo; la semana española empieza en lunes.
  const leading = (first.getDay() + 6) % 7;

  const cells: (number | null)[] = [
    ...Array.from({ length: leading }, () => null),
    ...Array.from({ length: daysInMonth }, (_, i) => i + 1),
  ];

  const adherence = data.adherence;

  return (
    <div className="stack">
      <div className="card stack">
        <div className="row">
          <div className="metric">
            <span className="metric-value">
              {adherence === null || adherence === undefined
                ? "—"
                : `${Math.round(adherence * 100)}%`}
            </span>
            <span className="faint">Cumplimiento del mes</span>
          </div>
          <div className="spacer" />
          <p className="tiny muted" style={{ margin: 0, maxWidth: 260, textAlign: "right" }}>
            {adherence === null || adherence === undefined
              ? "Todavía no hay días que computen."
              : "Los días pendientes de registrar no cuentan."}
          </p>
        </div>
      </div>

      <div className="card">
        <div className="cal-grid" role="grid" aria-label="Días del mes">
          {WEEKDAYS.map((label) => (
            <div className="cal-weekday" key={label}>
              {label}
            </div>
          ))}

          {cells.map((day, index) => {
            if (day === null) return <div className="cal-day empty" key={`e${index}`} />;

            const iso = `${cursor.year}-${String(cursor.month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
            const info = byDate.get(iso);
            // Los días futuros no tienen estado: el backend no evalúa el futuro
            // y la app no debe insinuar que sí lo sabe.
            const future = iso > today;

            return (
              <button
                key={iso}
                className="cal-day"
                data-state={info?.state}
                aria-current={iso === today ? "date" : undefined}
                aria-pressed={iso === selected}
                aria-label={`${day}: ${info ? stateLabel(info.state) : "sin datos"}`}
                disabled={future}
                onClick={() => onSelect(iso)}
              >
                <span className="cal-head-row">
                  <span className="cal-num">{day}</span>
                  <span className="spacer" />
                  {info && <StateDot state={info.state} className="cal-dot" />}
                </span>
                {info?.routine_name && <span className="cal-routine">{info.routine_name}</span>}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function DayDetail({ date, today }: { date: string; today: string }) {
  const day = useDay(date);
  const nameOf = useExerciseNames();
  const toast = useToast();

  const log = useLogAsPlanned();
  const skip = useSkipDay();
  const remove = useDeleteSession();
  const except = useSetException();
  const clearExcept = useClearException();

  const busy =
    log.isPending || skip.isPending || remove.isPending || except.isPending || clearExcept.isPending;

  if (day.isLoading) return <Loading rows={2} />;
  if (day.error) return <ErrorCard error={day.error} />;
  if (!day.data) return null;

  const info = day.data;
  const sesiones = [
    ...info.scheduled.flatMap((s) => (s.session ? [s.session] : [])),
    ...info.extra_sessions,
  ];
  // Un día se puede excusar mientras no conste que se entrenó. Si consta que
  // NO se entrenó ("no la hice"), excusarlo sigue teniendo sentido: es
  // precisamente el caso de la lesión o el viaje.
  const excusable = sesiones.every((s) => s.status === "skipped");
  const ok = (msg: string) => () => toast(msg);
  const fail = (e: unknown) => toast(e instanceof Error ? e.message : "Error", "error");

  /**
   * Excusar un día.
   *
   * Si consta un "no la hice", primero se retira ese registro. En el dominio
   * una sesión registrada manda sobre la excepción (regla correcta: lo que
   * hiciste pesa más que el motivo por el que no), así que dejar el registro
   * puesto haría que la excepción no cambiara nada y el control mentiría.
   * Reclasificar el día es exactamente lo que pide quien elige "lesión".
   */
  async function excusar(reason: string) {
    try {
      for (const saltada of sesiones.filter((s) => s.status === "skipped")) {
        await remove.mutateAsync(saltada.id);
      }
      if (reason === "") {
        await clearExcept.mutateAsync(date);
        toast("Excepción quitada");
      } else {
        await except.mutateAsync({ date, reason });
        toast("Día excusado");
      }
    } catch (e) {
      fail(e);
    }
  }

  return (
    <div className="card stack">
      <div className="row">
        <div>
          <h2 style={{ fontSize: "1rem" }}>{formatDate(date)}</h2>
          {date === today && <span className="faint">Hoy</span>}
        </div>
        <div className="spacer" />
        <StateBadge state={info.state} />
      </div>

      <p className="faint" style={{ margin: 0 }}>
        {info.reason}
      </p>

      {/* Una tarjeta por rutina del día: con mañana y tarde hay que poder ver
          y registrar cada una por separado. */}
      {info.scheduled.map((slot) => (
        <div className="stack" key={slot.routine_id}>
          <div className="row">
            <h3 style={{ fontSize: "0.95rem" }}>{slot.name}</h3>
            <div className="spacer" />
            <span className="faint">{slot.session ? "Registrada" : "Sin registrar"}</span>
          </div>

          {slot.session ? (
            <>
              {slot.session.exercises.map((e) => (
                <div className="row" key={e.exercise_slug}>
                  <span>{nameOf(e.exercise_slug)}</span>
                  <div className="spacer" />
                  <span className="prescription">{describePerformed(e)}</span>
                </div>
              ))}
              <button
                className="btn btn-sm btn-ghost btn-danger"
                disabled={busy}
                onClick={() =>
                  remove.mutate(slot.session!.id, {
                    onSuccess: ok("Registro borrado"),
                    onError: fail,
                  })
                }
              >
                Borrar registro
              </button>
            </>
          ) : (
            <>
              {slot.detail.exercises.map((e) => (
                <div className="row" key={e.exercise_slug}>
                  <span className="muted">{nameOf(e.exercise_slug)}</span>
                  <div className="spacer" />
                  <span className="prescription">{describePlanned(e)}</span>
                </div>
              ))}
              <button
                className="btn btn-primary"
                disabled={busy}
                onClick={() =>
                  log.mutate(
                    { date, status: "completed", routine_id: slot.routine_id },
                    { onSuccess: ok("¡Registrado!"), onError: fail },
                  )
                }
              >
                <Icon name="marca" />
                Hice esta rutina
              </button>
              <div className="row">
                <button
                  className="btn btn-sm btn-ghost"
                  disabled={busy}
                  onClick={() =>
                    log.mutate(
                      { date, status: "partial", routine_id: slot.routine_id },
                      { onSuccess: ok("Registrado como parcial"), onError: fail },
                    )
                  }
                >
                  A medias
                </button>
                <div className="spacer" />
                <button
                  className="btn btn-sm btn-ghost btn-danger"
                  disabled={busy}
                  onClick={() => skip.mutate(date, { onSuccess: ok("Marcado"), onError: fail })}
                >
                  No la hice
                </button>
              </div>
            </>
          )}
        </div>
      ))}

      {/* Lo entrenado fuera de plan: no tenía rutina, pero cuenta igual. */}
      {info.extra_sessions.map((sesion) => (
        <div className="stack" key={sesion.id}>
          <h3 style={{ fontSize: "0.95rem" }}>
            {sesion.routine_name ?? "Entrenamiento libre"}
          </h3>
          {sesion.exercises.map((e) => (
            <div className="row" key={e.exercise_slug}>
              <span>{nameOf(e.exercise_slug)}</span>
              <div className="spacer" />
              <span className="prescription">{describePerformed(e)}</span>
            </div>
          ))}
          <button
            className="btn btn-sm btn-ghost btn-danger"
            disabled={busy}
            onClick={() =>
              remove.mutate(sesion.id, { onSuccess: ok("Registro borrado"), onError: fail })
            }
          >
            Borrar registro
          </button>
        </div>
      ))}

      {excusable && (
        <div className="stack">
          <label>
            {info.exception_reason ? "Día excusado" : "Excusar el día"}
            <select
              value={info.exception_reason ?? ""}
              disabled={busy}
              onChange={(e) => void excusar(e.target.value)}
            >
              <option value="">No excusado</option>
              <option value="descanso">Descanso</option>
              <option value="lesion">Lesión</option>
              <option value="viaje">Viaje</option>
              <option value="movido">Entrenamiento movido</option>
              <option value="otro">Otro</option>
            </select>
          </label>
          <p className="tiny muted" style={{ margin: 0 }}>
            Un día excusado no cuenta como incumplimiento.
          </p>
        </div>
      )}
    </div>
  );
}
