/** Historial de entrenamientos realizados. */

import { localDate } from "../api/client";
import type { Session } from "../api/client";
import { useDeleteSession, useExerciseNames, useSessions } from "../api/hooks";
import {
  describePerformed,
  Empty,
  ErrorCard,
  Loading,
  relativeDate,
  useToast,
} from "../components/ui";

export default function History() {
  const sessions = useSessions();
  const remove = useDeleteSession();
  const toast = useToast();

  if (sessions.isLoading) return <Loading rows={3} />;
  if (sessions.error) return <ErrorCard error={sessions.error} />;

  const list = sessions.data ?? [];

  return (
    <div className="stack-lg">
      <header className="page-head">
        <h1>Historial</h1>
      </header>

      {list.length === 0 ? (
        <div className="card">
          <Empty icon="📖">
            <p style={{ margin: 0 }}>Aún no hay entrenamientos registrados.</p>
          </Empty>
        </div>
      ) : (
        <div className="stack">
          {list.map((session) => (
            <SessionCard
              key={session.id}
              session={session}
              busy={remove.isPending}
              onDelete={() =>
                remove.mutate(session.id, {
                  onSuccess: () => toast("Entrenamiento borrado"),
                  onError: (e) => toast(e instanceof Error ? e.message : "Error", "error"),
                })
              }
            />
          ))}
        </div>
      )}
    </div>
  );
}

function SessionCard({
  session,
  busy,
  onDelete,
}: {
  session: Session;
  busy: boolean;
  onDelete: () => void;
}) {
  const nameOf = useExerciseNames();
  const today = localDate();

  return (
    <div className="card card-flush">
      <div style={{ padding: "14px 16px" }}>
        <div className="row">
          <div>
            <strong>{session.routine_name ?? "Entrenamiento libre"}</strong>
            <div className="faint">
              {relativeDate(session.date, today)}
              {session.status === "partial" && " · parcial"}
              {session.status === "skipped" && " · no realizado"}
              {/* Registrado otro día: útil para juzgar la fiabilidad del dato. */}
              {session.is_retroactive && " · registrado después"}
            </div>
          </div>
          <div className="spacer" />
          <button className="btn btn-sm btn-ghost btn-danger" onClick={onDelete} disabled={busy}>
            Borrar
          </button>
        </div>
      </div>

      {session.exercises.map((exercise) => (
        <div className="exercise" key={exercise.exercise_slug}>
          <div className="exercise-head">
            <span className="exercise-name">{nameOf(exercise.exercise_slug)}</span>
            <span className="prescription">{describePerformed(exercise)}</span>
          </div>
          <div className="set-list">
            {exercise.sets.map((set) => (
              <span className="set-chip" data-warmup={set.is_warmup} key={set.set_no}>
                {set.time_s != null ? `${set.time_s}s` : (set.reps ?? "—")}
                {set.weight_kg ? ` · ${set.weight_kg}kg` : ""}
                {set.rir != null ? ` · RIR ${set.rir}` : ""}
              </span>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
