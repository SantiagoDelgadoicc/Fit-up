/** Listado de rutinas. */

import { Link } from "react-router-dom";

import { useArchiveRoutine, useRoutines } from "../api/hooks";
import { Empty, ErrorCard, Loading, useToast } from "../components/ui";

export default function Routines() {
  const routines = useRoutines();
  const archive = useArchiveRoutine();
  const toast = useToast();

  if (routines.isLoading) return <Loading />;
  if (routines.error) return <ErrorCard error={routines.error} />;

  const list = routines.data ?? [];

  return (
    <div className="stack-lg">
      <header className="page-head">
        <h1>Rutinas</h1>
        <Link className="btn btn-primary btn-sm" to="/rutinas/nueva">
          + Nueva
        </Link>
      </header>

      {list.length === 0 ? (
        <div className="card">
          <Empty icon="📋">
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
                </div>
                <div className="spacer" />
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
