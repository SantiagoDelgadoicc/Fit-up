/** Listado de rutinas. */

import { Link } from "react-router-dom";

import type { RoutineReadiness } from "../api/client";

import { useArchiveRoutine, useReadiness, useRoutines } from "../api/hooks";
import { Icon } from "../components/icons";
import { Empty, ErrorCard, Loading, useToast } from "../components/ui";

export default function Routines() {
  const routines = useRoutines();
  const readiness = useReadiness();
  const archive = useArchiveRoutine();
  const toast = useToast();

  if (routines.isLoading) return <Loading />;
  if (routines.error) return <ErrorCard error={routines.error} />;

  const list = routines.data ?? [];
  // El aviso se calcula una vez para todas las rutinas: entrar en cada una a
  // comprobarlo sería justo lo que hace que la progresion no se use.
  const ready = new Map((readiness.data ?? []).map((r) => [r.routine_id, r]));

  return (
    <div className="stack-lg">
      <header className="page-head">
        <h1>Rutinas</h1>
        <Link className="btn btn-primary btn-sm" to="/rutinas/nueva">
          <Icon name="mas" />
          Nueva
        </Link>
      </header>

      {list.length === 0 ? (
        <div className="card">
          <Empty icon="rutinas">
            <p style={{ margin: 0 }}>Todavía no has creado ninguna rutina.</p>
            <p className="faint">Crea una y asígnala a los días de la semana.</p>
          </Empty>
        </div>
      ) : (
        <div className="stack">
          {list.map((routine) => (
            <div className="card" key={routine.id}>
              <div className="row">
                <div>
                  <Link to={`/rutinas/${routine.id}`} style={{ color: "inherit" }}>
                    <strong>{routine.name}</strong>
                  </Link>
                  <div className="faint">
                    {routine.exercise_count} ejercicio
                    {routine.exercise_count === 1 ? "" : "s"} · versión {routine.version_no}
                  </div>
                  {ready.has(routine.id) && (
                    <span className="badge" data-outcome="ready" style={{ marginTop: 8 }}>
                      <Icon name="sube" />
                      {readyLabel(ready.get(routine.id)!)}
                    </span>
                  )}
                </div>
                <div className="spacer" />
                <Link
                  className={ready.has(routine.id) ? "btn btn-sm btn-primary" : "btn btn-sm"}
                  to={`/rutinas/${routine.id}/progresion`}
                >
                  Progresar
                </Link>
                <Link className="btn btn-sm" to={`/rutinas/${routine.id}`}>
                  Editar
                </Link>
                <button
                  className="btn btn-sm btn-ghost btn-danger"
                  disabled={archive.isPending}
                  onClick={() =>
                    archive.mutate(routine.id, {
                      onSuccess: () => toast("Rutina archivada"),
                      onError: (e) => toast(e instanceof Error ? e.message : "Error", "error"),
                    })
                  }
                >
                  Archivar
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <p className="tiny muted">
        Archivar no borra nada: el historial sigue apuntando a la versión que se entrenó.
      </p>
    </div>
  );
}

/** "2 para progresar", o la descarga si es lo único que hay que decidir. */
function readyLabel(readiness: RoutineReadiness): string {
  const partes: string[] = [];
  if (readiness.ready > 0) partes.push(`${readiness.ready} para progresar`);
  if (readiness.deload > 0) partes.push(`${readiness.deload} con descarga`);
  return partes.join(" · ");
}
