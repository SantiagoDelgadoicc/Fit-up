/** Organizar la semana: qué rutinas tocan cada día. */

import { useEffect, useState } from "react";

import { useRoutines, useSaveWeek, useWeek } from "../api/hooks";
import { ErrorCard, Loading, useToast, weekdayName } from "../components/ui";

/** weekday → rutinas de ese día, en orden (primero la de la mañana). */
type Semana = Record<string, number[]>;

export default function Week() {
  const week = useWeek();
  const routines = useRoutines();
  const save = useSaveWeek();
  const toast = useToast();

  const [days, setDays] = useState<Semana>({});

  useEffect(() => {
    if (week.data) setDays(week.data.days as Semana);
  }, [week.data]);

  if (week.isLoading || routines.isLoading) return <Loading rows={3} />;
  if (week.error) return <ErrorCard error={week.error} />;

  const list = routines.data ?? [];
  const dirty = week.data ? JSON.stringify(days) !== JSON.stringify(week.data.days) : false;

  const rutinasDe = (weekday: number): number[] => days[String(weekday)] ?? [];

  const cambiar = (weekday: number, indice: number, valor: string) =>
    setDays((prev) => {
      const actuales = [...(prev[String(weekday)] ?? [])];
      if (valor === "") actuales.splice(indice, 1);
      else actuales[indice] = Number(valor);
      return { ...prev, [String(weekday)]: actuales };
    });

  const anadir = (weekday: number) =>
    setDays((prev) => {
      const actuales = prev[String(weekday)] ?? [];
      // Se propone la primera rutina que ese día no tenga ya: repetir la misma
      // dos veces el mismo día no significa nada y el backend lo rechaza.
      const libre = list.find((r) => !actuales.includes(r.id));
      if (!libre) return prev;
      return { ...prev, [String(weekday)]: [...actuales, libre.id] };
    });

  return (
    <div className="stack-lg">
      <header className="page-head">
        <div>
          <h1>Semana</h1>
          <p className="faint" style={{ margin: "2px 0 0" }}>
            Un día puede tener más de una rutina: calistenia por la mañana y pesas por la
            tarde son dos entrenamientos, no uno partido en dos.
          </p>
        </div>
      </header>

      {list.length === 0 && (
        <div className="card">Crea una rutina antes de organizar la semana.</div>
      )}

      <div className="week-grid">
        {[0, 1, 2, 3, 4, 5, 6].map((weekday) => {
          const asignadas = rutinasDe(weekday);
          return (
            <div className="week-row" key={weekday}>
              <label htmlFor={`d${weekday}-0`} style={{ flexDirection: "row" }}>
                {weekdayName(weekday)}
              </label>

              <div className="week-slots">
                {asignadas.length === 0 && (
                  <select
                    id={`d${weekday}-0`}
                    value=""
                    onChange={(e) => cambiar(weekday, 0, e.target.value)}
                  >
                    <option value="">Descanso</option>
                    {list.map((routine) => (
                      <option key={routine.id} value={routine.id}>
                        {routine.name}
                      </option>
                    ))}
                  </select>
                )}

                {asignadas.map((routineId, i) => (
                  <select
                    key={i}
                    id={`d${weekday}-${i}`}
                    value={routineId}
                    onChange={(e) => cambiar(weekday, i, e.target.value)}
                  >
                    <option value="">{i === 0 ? "Descanso" : "Quitar"}</option>
                    {list.map((routine) => (
                      <option key={routine.id} value={routine.id}>
                        {routine.name}
                      </option>
                    ))}
                  </select>
                ))}

                {asignadas.length > 0 && asignadas.length < list.length && (
                  <button
                    className="btn btn-sm btn-ghost"
                    onClick={() => anadir(weekday)}
                    aria-label={`Añadir otra rutina el ${weekdayName(weekday)}`}
                  >
                    + Otra
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <button
        className="btn btn-primary btn-hero"
        disabled={!dirty || save.isPending}
        onClick={() =>
          save.mutate(days, {
            onSuccess: () => toast("Semana guardada"),
            onError: (e) => toast(e instanceof Error ? e.message : "Error", "error"),
          })
        }
      >
        Guardar semana
      </button>

      <p className="tiny muted">
        El cambio se aplica desde hoy. Los días anteriores conservan la planificación que
        tenían, para que el historial no cambie de significado.
      </p>
    </div>
  );
}
