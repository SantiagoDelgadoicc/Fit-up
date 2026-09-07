/** Organizar la semana: qué rutina toca cada día. */

import { useEffect, useState } from "react";

import { useRoutines, useSaveWeek, useWeek } from "../api/hooks";
import { ErrorCard, Loading, useToast, weekdayName } from "../components/ui";

export default function Week() {
  const week = useWeek();
  const routines = useRoutines();
  const save = useSaveWeek();
  const toast = useToast();

  const [days, setDays] = useState<Record<string, number | null>>({});

  useEffect(() => {
    if (week.data) setDays(week.data.days as Record<string, number | null>);
  }, [week.data]);

  if (week.isLoading || routines.isLoading) return <Loading rows={3} />;
  if (week.error) return <ErrorCard error={week.error} />;

  const list = routines.data ?? [];
  const dirty = week.data
    ? JSON.stringify(days) !== JSON.stringify(week.data.days)
    : false;

  return (
    <div className="stack-lg">
      <header className="page-head">
        <h1>Semana</h1>
      </header>

      {list.length === 0 && (
        <div className="card">
          Crea una rutina antes de organizar la semana.
        </div>
      )}

      <div className="week-grid">
        {[0, 1, 2, 3, 4, 5, 6].map((weekday) => (
          <div className="week-row" key={weekday}>
            <label htmlFor={`d${weekday}`} style={{ flexDirection: "row" }}>
              {weekdayName(weekday)}
            </label>
            <select
              id={`d${weekday}`}
              value={days[String(weekday)] ?? ""}
              onChange={(e) =>
                setDays((prev) => ({
                  ...prev,
                  [String(weekday)]: e.target.value === "" ? null : Number(e.target.value),
                }))
              }
            >
              <option value="">Descanso</option>
              {list.map((routine) => (
                <option key={routine.id} value={routine.id}>
                  {routine.name}
                </option>
              ))}
            </select>
          </div>
        ))}
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
