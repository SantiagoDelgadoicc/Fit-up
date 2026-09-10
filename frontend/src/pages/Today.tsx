/**
 * Pantalla «Hoy» — la protagonista.
 *
 * Su única obligación es que registrar un entrenamiento cueste un toque. Todo
 * lo demás (ajustar desviaciones, mirar el historial) es secundario y puede
 * costar más pasos: si registrar es incómodo, no se registra, y sin registro
 * no hay progresión ni ranking.
 */

import { Link, useNavigate } from "react-router-dom";

import { localDate } from "../api/client";
import {
  useExerciseNames,
  useLogAsPlanned,
  usePending,
  useReadiness,
  useSkipDay,
  useToday,
} from "../api/hooks";
import type { Day, PendingDay, RoutineReadiness } from "../api/client";
import { Icon } from "../components/icons";
import { formatPreset, useTimer } from "../components/timer";
import {
  describePlanned,
  Empty,
  ErrorCard,
  formatDate,
  Loading,
  plannedColumns,
  StateBadge,
  useToast,
} from "../components/ui";

export default function Today() {
  const today = useToday();
  const pending = usePending();
  const readiness = useReadiness();
  const toast = useToast();
  const log = useLogAsPlanned();
  const skip = useSkipDay();

  const iso = localDate();

  if (today.isLoading) return <Loading rows={3} />;
  if (today.error) return <ErrorCard error={today.error} />;
  if (!today.data) return null;

  const day = today.data;
  // Los pendientes ya incluyen hoy cuando toca; no debe salir dos veces.
  const otherPending = (pending.data ?? []).filter((p) => p.date !== iso);
  const progresiones = readiness.data ?? [];
  // En pantalla ancha, lo que hay que decidir va a un panel a la derecha; sin
  // nada que decidir no hay panel, y la columna se queda en su ancho de
  // lectura en vez de estirarse por estirarse.
  const hayPanel = progresiones.length > 0 || otherPending.length > 0;

  const registrar = (
    date: string,
    status: "completed" | "partial" = "completed",
    routineId?: number,
  ) =>
    log.mutate(
      { date, status, routine_id: routineId },
      {
        onSuccess: () => toast(status === "partial" ? "Registrado como parcial" : "¡Registrado!"),
        onError: (e) => toast(e instanceof Error ? e.message : "No se pudo registrar", "error"),
      },
    );

  return (
    <div className="stack-lg">
      <header className="page-head">
        <div>
          <h1>Hoy</h1>
          <p className="faint" style={{ margin: "2px 0 0" }}>
            {formatDate(iso)}
          </p>
        </div>
        <StateBadge state={day.state} />
      </header>

      <div className={hayPanel ? "split split-hoy" : undefined}>
        <TodayCard
          day={day}
          busy={log.isPending || skip.isPending}
          onLog={(status, routineId) => registrar(iso, status, routineId)}
          onSkip={() =>
            skip.mutate(iso, {
              onSuccess: () => toast("Marcado como no realizado"),
              onError: (e) => toast(e instanceof Error ? e.message : "Error", "error"),
            })
          }
        />

        {hayPanel && (
          <aside className="stack-lg">
            <ProgressionNotice routines={progresiones} />

            {otherPending.length > 0 && (
              <section className="inspector">
                <div className="inspector-head">
                  <span className="inspector-titulo">Sin registrar</span>
                  <span className="inspector-cuenta" data-tono="aviso">
                    {otherPending.length}
                  </span>
                </div>
                {otherPending.map((p) => (
                  <PendingCard
                    key={p.date}
                    pending={p}
                    busy={log.isPending}
                    onLog={() => registrar(p.date, "completed", p.routine_id)}
                  />
                ))}
                <p className="inspector-pie tiny muted" style={{ margin: 0 }}>
                  Días programados que aún no has anotado. No cuentan como fallados.
                </p>
              </section>
            )}
          </aside>
        )}
      </div>
    </div>
  );
}

/**
 * Aviso de progresiones disponibles.
 *
 * Vive en «Hoy» porque es donde se entra a diario: una progresión que hay que
 * salir a buscar a la pantalla de cada rutina no se aplica nunca. Avisa y
 * enlaza, pero no aplica nada desde aquí — eso pide ver el diff antes.
 */
function ProgressionNotice({ routines }: { routines: RoutineReadiness[] }) {
  if (routines.length === 0) return null;

  // La cuenta es de **ejercicios**, no de rutinas: es lo que hay que revisar.
  const total = routines.reduce((n, r) => n + r.ready + r.deload, 0);

  return (
    <section className="inspector">
      <div className="inspector-head">
        <span className="inspector-titulo">Listas para progresar</span>
        <span className="inspector-cuenta">{total}</span>
      </div>

      {routines.map((routine) => (
        // La fila entera es el enlace: un botón «Revisar» al lado obliga a
        // apuntar a un objetivo pequeño para hacer lo único que se hace aquí.
        <Link
          className="inspector-fila"
          to={`/rutinas/${routine.routine_id}/progresion`}
          key={routine.routine_id}
        >
          <span className="inspector-nombre">
            <strong>{routine.routine_name}</strong>
            <small>
              {routine.ready > 0 && `${routine.ready} suben`}
              {routine.ready > 0 && routine.deload > 0 && " · "}
              {routine.deload > 0 && `${routine.deload} con descarga`}
            </small>
          </span>
          <span className="inspector-marca" data-tono={routine.ready > 0 ? undefined : "aviso"}>
            <Icon name={routine.ready > 0 ? "sube" : "baja"} />
          </span>
        </Link>
      ))}
    </section>
  );
}

function TodayCard({
  day,
  busy,
  onLog,
  onSkip,
}: {
  day: Day;
  busy: boolean;
  onLog: (status: "completed" | "partial", routineId: number) => void;
  onSkip: () => void;
}) {
  const nameOf = useExerciseNames();

  if (day.scheduled.length === 0 && day.extra_sessions.length === 0) {
    return (
      <div className="card">
        <Empty icon="luna">
          <p style={{ margin: 0 }}>Hoy no hay rutina programada.</p>
          <p className="faint" style={{ marginBottom: 0 }}>
            <Link to="/semana">Organizar la semana</Link>
          </p>
        </Empty>
      </div>
    );
  }

  return (
    <section className="stack">
      {/* Una tarjeta por rutina del día: con mañana y tarde, cada una se
          registra por su cuenta y se ve cuál falta. */}
      {day.scheduled.map((slot) => (
        <RoutineCard
          key={slot.routine_id}
          slot={slot}
          reason={day.reason}
          busy={busy}
          nameOf={nameOf}
          onLog={(status) => onLog(status, slot.routine_id)}
          onSkip={onSkip}
        />
      ))}

      {day.extra_sessions.map((sesion) => (
        <div className="card" key={sesion.id}>
          <div className="row">
            <h2>{sesion.routine_name ?? "Entrenamiento libre"}</h2>
            <div className="spacer" />
            <span className="faint">Registrado</span>
          </div>
          <p className="muted" style={{ marginBottom: 0 }}>
            {sesion.exercises.length} ejercicio{sesion.exercises.length === 1 ? "" : "s"}{" "}
            anotados. <Link to="/historial">Ver historial</Link>
          </p>
        </div>
      ))}
    </section>
  );
}

/** Una rutina del día: lo que toca, o lo que quedó registrado. */
function RoutineCard({
  slot,
  reason,
  busy,
  nameOf,
  onLog,
  onSkip,
}: {
  slot: Day["scheduled"][number];
  reason: string;
  busy: boolean;
  nameOf: (slug: string) => string;
  onLog: (status: "completed" | "partial") => void;
  onSkip: () => void;
}) {
  const timer = useTimer();
  const navigate = useNavigate();

  if (slot.session) {
    return (
      <div className="card">
        <div className="row">
          <h2>{slot.name}</h2>
          <div className="spacer" />
          <span className="faint">Registrado</span>
        </div>
        <p className="muted" style={{ marginBottom: 0 }}>
          {slot.session.exercises.length} ejercicio
          {slot.session.exercises.length === 1 ? "" : "s"} anotados.{" "}
          <Link to="/historial">Ver historial</Link>
        </p>
      </div>
    );
  }

  const descansar = (segundos: number) => {
    // Arrancar el descanso del ejercicio sin teclear su duración: el dato ya
    // está en el plan y a mitad de serie no se elige.
    timer.start(segundos);
    navigate("/descanso");
  };

  return (
    <div className="stack">
      <div className="card card-flush">
        <div className="card-head row">
          <h2>{slot.name}</h2>
          <div className="spacer" />
          <span className="faint">{reason}</span>
        </div>

        {/* Los ejercicios en columnas: series, objetivo, carga y descanso caen
            siempre en el mismo sitio, así que comparar dos filas es mirar y no
            leer. Debajo de 760 px la tabla se pliega a dos líneas —lo hace el
            CSS— porque seis columnas no caben en un móvil. */}
        <div className="tabla">
          <div className="tabla-head" aria-hidden="true">
            <span>#</span>
            <span>Ejercicio</span>
            <span className="tabla-dato">Series</span>
            <span className="tabla-dato">Objetivo</span>
            <span className="tabla-dato">Carga</span>
            <span className="tabla-dato">Descanso</span>
            <span />
          </div>

          {slot.detail.exercises.map((exercise, i) => {
            const col = plannedColumns(exercise);
            const descanso = exercise.rest_seconds;
            return (
              <div className="tabla-fila" key={exercise.exercise_slug}>
                <span className="tabla-num">{String(i + 1).padStart(2, "0")}</span>

                <span className="tabla-ejercicio">
                  <span className="tabla-nombre">{nameOf(exercise.exercise_slug)}</span>
                  {descanso ? (
                    <span className="tabla-sub">Descanso {formatPreset(descanso)}</span>
                  ) : null}
                </span>

                <span className="tabla-dato tabla-series">{col.series}</span>
                <span className="tabla-dato tabla-objetivo">{col.objetivo}</span>
                <span
                  className="tabla-dato tabla-carga"
                  data-vacio={col.carga ? undefined : ""}
                >
                  {col.carga ?? "—"}
                </span>
                <span
                  className="tabla-dato tabla-descanso"
                  data-vacio={descanso ? undefined : ""}
                >
                  {descanso ? formatPreset(descanso) : "—"}
                </span>

                {/* Solo en móvil, donde las columnas no caben. */}
                <span className="tabla-resumen">{describePlanned(exercise)}</span>

                {descanso ? (
                  <button
                    className="tabla-accion"
                    onClick={() => descansar(descanso)}
                    aria-label={`Descansar ${formatPreset(descanso)} tras ${nameOf(exercise.exercise_slug)}`}
                  >
                    <Icon name="descanso" />
                  </button>
                ) : (
                  <span />
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Anclada al pie en escritorio: con una rutina larga, el botón de
          registrar quedaba por debajo del pliegue justo los días en que hay
          más que hacer. */}
      <div className="barra-accion">
        <button
          className="btn btn-primary btn-hero"
          onClick={() => onLog("completed")}
          disabled={busy}
        >
          <Icon name="marca" />
          Hice esta rutina
        </button>
        <button className="btn btn-sm btn-ghost" onClick={() => onLog("partial")} disabled={busy}>
          La hice a medias
        </button>
        <div className="spacer" />
        <button className="btn btn-sm btn-ghost btn-danger" onClick={onSkip} disabled={busy}>
          No la hice
        </button>
      </div>
    </div>
  );
}

function PendingCard({
  pending,
  busy,
  onLog,
}: {
  pending: PendingDay;
  busy: boolean;
  onLog: () => void;
}) {
  return (
    <div className="inspector-fila">
      <span className="inspector-nombre">
        <strong>{pending.routine_name}</strong>
        <small>
          {formatDate(pending.date)} ·{" "}
          {pending.days_left === 0
            ? "último día"
            : `${pending.days_left} día${pending.days_left === 1 ? "" : "s"} de margen`}
        </small>
      </span>
      <button className="btn btn-sm btn-primary" onClick={onLog} disabled={busy}>
        <Icon name="marca" />
        La hice
      </button>
    </div>
  );
}
