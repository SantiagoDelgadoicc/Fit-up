/**
 * Pantalla «Hoy» — la protagonista.
 *
 * Su única obligación es que registrar un entrenamiento cueste un toque. Todo
 * lo demás (ajustar desviaciones, mirar el historial) es secundario y puede
 * costar más pasos: si registrar es incómodo, no se registra, y sin registro
 * no hay progresión ni ranking.
 */

import { Link } from "react-router-dom";

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
import {
  describePlanned,
  Empty,
  ErrorCard,
  formatDate,
  Loading,
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

  const registrar = (date: string, status: "completed" | "partial" = "completed") =>
    log.mutate(
      { date, status },
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

      <TodayCard
        day={day}
        busy={log.isPending || skip.isPending}
        onLog={(status) => registrar(iso, status)}
        onSkip={() =>
          skip.mutate(iso, {
            onSuccess: () => toast("Marcado como no realizado"),
            onError: (e) => toast(e instanceof Error ? e.message : "Error", "error"),
          })
        }
      />

      <ProgressionNotice routines={readiness.data ?? []} />

      {otherPending.length > 0 && (
        <section className="stack">
          <h2>Pendientes de registrar</h2>
          <p className="faint" style={{ margin: 0 }}>
            Días programados que aún no has anotado. No cuentan como fallados.
          </p>
          {otherPending.map((p) => (
            <PendingCard
              key={p.date}
              pending={p}
              busy={log.isPending}
              onLog={() => registrar(p.date)}
            />
          ))}
        </section>
      )}
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

  return (
    <section className="stack">
      <h2>Progresiones disponibles</h2>
      {routines.map((routine) => (
        <div className="card" key={routine.routine_id}>
          <div className="row">
            <div>
              <strong>{routine.routine_name}</strong>
              <div className="faint">
                {routine.ready > 0 &&
                  `${routine.ready} ejercicio${routine.ready === 1 ? "" : "s"} listo${
                    routine.ready === 1 ? "" : "s"
                  } para subir`}
                {routine.ready > 0 && routine.deload > 0 && " · "}
                {routine.deload > 0 && `${routine.deload} con descarga sugerida`}
              </div>
            </div>
            <div className="spacer" />
            <Link className="btn btn-sm btn-primary" to={`/rutinas/${routine.routine_id}/progresion`}>
              Revisar
            </Link>
          </div>
        </div>
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
  onLog: (status: "completed" | "partial") => void;
  onSkip: () => void;
}) {
  const nameOf = useExerciseNames();

  if (day.session) {
    return (
      <section className="stack">
        <div className="card">
          <div className="row">
            <h2>{day.session.routine_name ?? "Entrenamiento libre"}</h2>
            <div className="spacer" />
            <span className="faint">Registrado</span>
          </div>
          <p className="muted" style={{ marginBottom: 0 }}>
            {day.session.exercises.length} ejercicio
            {day.session.exercises.length === 1 ? "" : "s"} anotados.{" "}
            <Link to="/historial">Ver historial</Link>
          </p>
        </div>
      </section>
    );
  }

  if (!day.planned) {
    return (
      <div className="card">
        <Empty icon="😴">
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
      <div className="card card-flush">
        <div style={{ padding: "16px 16px 4px" }}>
          <h2>{day.planned.name}</h2>
          <p className="faint" style={{ margin: "2px 0 10px" }}>
            {day.reason}
          </p>
        </div>
        {day.planned.exercises.map((exercise) => (
          <div className="exercise" key={exercise.exercise_slug}>
            <div className="exercise-head">
              <span className="exercise-name">{nameOf(exercise.exercise_slug)}</span>
              <span className="prescription">{describePlanned(exercise)}</span>
            </div>
            {exercise.rest_seconds ? (
              <span className="faint">Descanso {exercise.rest_seconds}s</span>
            ) : null}
          </div>
        ))}
      </div>

      <button
        className="btn btn-primary btn-hero"
        onClick={() => onLog("completed")}
        disabled={busy}
      >
        ✓ Hice esta rutina
      </button>

      <div className="row">
        <button className="btn btn-ghost btn-sm" onClick={() => onLog("partial")} disabled={busy}>
          La hice a medias
        </button>
        <div className="spacer" />
        <button className="btn btn-ghost btn-sm btn-danger" onClick={onSkip} disabled={busy}>
          No la hice
        </button>
      </div>
    </section>
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
    <div className="card">
      <div className="row">
        <div>
          <strong>{pending.routine_name}</strong>
          <div className="faint">{formatDate(pending.date)}</div>
        </div>
        <div className="spacer" />
        <button className="btn btn-sm btn-primary" onClick={onLog} disabled={busy}>
          ✓ La hice
        </button>
      </div>
      <p className="tiny muted" style={{ margin: "10px 0 0" }}>
        {pending.days_left === 0
          ? "Último día antes de contar como no realizada"
          : `Quedan ${pending.days_left} día(s) de margen`}
      </p>
    </div>
  );
}
