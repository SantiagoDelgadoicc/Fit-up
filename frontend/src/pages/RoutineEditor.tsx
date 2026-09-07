/**
 * Editor de rutinas.
 *
 * Trabaja con la prescripción compacta ("3 series de 15") y deja que el
 * backend genere las filas de series. El modelo guarda series individuales,
 * pero nadie debería tener que escribirlas a mano.
 *
 * Guardar una rutina existente crea una versión nueva; la anterior queda
 * intacta y el historial sigue siendo cierto. La UI lo dice explícitamente
 * para que no sea una sorpresa.
 */

import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import type { Exercise, RoutineInput } from "../api/client";
import { useExercises, useRoutine, useSaveRoutine } from "../api/hooks";
import { ErrorCard, Loading, useToast } from "../components/ui";

type Draft = {
  slug: string;
  count: number;
  reps: number | null;
  timeS: number | null;
  weightKg: number | null;
  restSeconds: number | null;
  warmup: number;
};

export default function RoutineEditor() {
  const { id } = useParams();
  const routineId = id === "nueva" || id === undefined ? null : Number(id);

  const existing = useRoutine(routineId);
  const catalog = useExercises();
  const save = useSaveRoutine();
  const navigate = useNavigate();
  const toast = useToast();

  const [name, setName] = useState("");
  const [items, setItems] = useState<Draft[]>([]);
  const [picker, setPicker] = useState("");

  useEffect(() => {
    const routine = existing.data;
    if (!routine) return;
    setName(routine.name);
    setItems(
      routine.exercises.map((e) => {
        const work = e.sets.filter((s) => !s.is_warmup);
        const first = work[0];
        return {
          slug: e.exercise_slug,
          count: work.length,
          reps: first?.target_reps ?? null,
          timeS: first?.target_time_s ?? null,
          weightKg: first?.target_weight_kg ?? null,
          restSeconds: e.rest_seconds ?? null,
          // Se conserva: guardar no debe destruir en silencio el calentamiento
          // que ya tenia la rutina.
          warmup: e.sets.length - work.length,
        };
      }),
    );
  }, [existing.data]);

  if (routineId !== null && existing.isLoading) return <Loading rows={3} />;
  if (existing.error) return <ErrorCard error={existing.error} />;

  const bySlug = new Map((catalog.data ?? []).map((e) => [e.slug, e]));

  const addExercise = (slug: string) => {
    const exercise = bySlug.get(slug);
    if (!exercise || items.some((i) => i.slug === slug)) return;
    const isTime = exercise.modality === "tiempo";
    setItems((prev) => [
      ...prev,
      {
        slug,
        count: 3,
        reps: isTime ? null : 10,
        timeS: isTime ? 30 : null,
        weightKg: exercise.load_type === "externa" ? 20 : null,
        restSeconds: exercise.default_rest_seconds,
        warmup: 0,
      },
    ]);
    setPicker("");
  };

  const update = (index: number, patch: Partial<Draft>) =>
    setItems((prev) => prev.map((item, i) => (i === index ? { ...item, ...patch } : item)));

  const move = (index: number, delta: number) =>
    setItems((prev) => {
      const next = [...prev];
      const target = index + delta;
      if (target < 0 || target >= next.length) return prev;
      [next[index], next[target]] = [next[target]!, next[index]!];
      return next;
    });

  const submit = () => {
    const body: RoutineInput = {
      name,
      exercises: items.map((item) => ({
        exercise_slug: item.slug,
        rest_seconds: item.restSeconds,
        spec: {
          count: item.count,
          reps: item.reps,
          time_s: item.timeS,
          weight_kg: item.weightKg,
          warmup: item.warmup,
        },
      })),
    };
    save.mutate(
      { id: routineId, body },
      {
        onSuccess: (routine) => {
          toast(routineId === null ? "Rutina creada" : `Guardada como versión ${routine.version_no}`);
          navigate("/rutinas");
        },
        onError: (e) => toast(e instanceof Error ? e.message : "No se pudo guardar", "error"),
      },
    );
  };

  const canSave = name.trim().length > 0 && items.length > 0 && !save.isPending;

  return (
    <div className="stack-lg">
      <header className="page-head">
        <h1>{routineId === null ? "Nueva rutina" : "Editar rutina"}</h1>
      </header>

      <label>
        Nombre
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Empuje A" />
      </label>

      <section className="stack">
        <h2>Ejercicios</h2>
        {items.map((item, index) => (
          <ExerciseRow
            key={item.slug}
            item={item}
            exercise={bySlug.get(item.slug)}
            first={index === 0}
            last={index === items.length - 1}
            onChange={(patch) => update(index, patch)}
            onMove={(delta) => move(index, delta)}
            onRemove={() => setItems((prev) => prev.filter((_, i) => i !== index))}
          />
        ))}

        <select
          value={picker}
          onChange={(e) => addExercise(e.target.value)}
          aria-label="Añadir ejercicio"
        >
          <option value="">+ Añadir ejercicio…</option>
          {(catalog.data ?? [])
            .filter((e) => !items.some((i) => i.slug === e.slug))
            .map((e) => (
              <option key={e.slug} value={e.slug}>
                {e.name}
              </option>
            ))}
        </select>
      </section>

      <div className="stack">
        <button className="btn btn-primary btn-hero" onClick={submit} disabled={!canSave}>
          {routineId === null ? "Crear rutina" : "Guardar como nueva versión"}
        </button>
        {routineId !== null && (
          <p className="tiny muted" style={{ margin: 0 }}>
            Guardar crea una versión nueva. Los entrenamientos ya registrados siguen
            apuntando a la versión con la que se hicieron.
          </p>
        )}
      </div>
    </div>
  );
}

function ExerciseRow({
  item,
  exercise,
  first,
  last,
  onChange,
  onMove,
  onRemove,
}: {
  item: Draft;
  exercise: Exercise | undefined;
  first: boolean;
  last: boolean;
  onChange: (patch: Partial<Draft>) => void;
  onMove: (delta: number) => void;
  onRemove: () => void;
}) {
  const isTime = exercise?.modality === "tiempo";
  const usesWeight = exercise?.load_type === "externa" || exercise?.load_type === "corporal";

  return (
    <div className="card">
      <div className="row">
        <strong>{exercise?.name ?? item.slug}</strong>
        <div className="spacer" />
        <button className="btn btn-sm btn-ghost" onClick={() => onMove(-1)} disabled={first}>
          ↑
        </button>
        <button className="btn btn-sm btn-ghost" onClick={() => onMove(1)} disabled={last}>
          ↓
        </button>
        <button className="btn btn-sm btn-ghost btn-danger" onClick={onRemove}>
          Quitar
        </button>
      </div>

      <div className="row" style={{ marginTop: 12, alignItems: "flex-end" }}>
        <label>
          Series
          <input
            className="num"
            type="number"
            min={1}
            max={20}
            value={item.count}
            onChange={(e) => onChange({ count: Number(e.target.value) })}
          />
        </label>

        {isTime ? (
          <label>
            Segundos
            <input
              className="num"
              type="number"
              min={1}
              value={item.timeS ?? ""}
              onChange={(e) => onChange({ timeS: Number(e.target.value) || null })}
            />
          </label>
        ) : (
          <label>
            Reps
            <input
              className="num"
              type="number"
              min={1}
              value={item.reps ?? ""}
              onChange={(e) => onChange({ reps: Number(e.target.value) || null })}
            />
          </label>
        )}

        {usesWeight && (
          <label>
            {exercise?.load_type === "corporal" ? "Lastre kg" : "Peso kg"}
            <input
              className="num"
              type="number"
              min={0}
              step={1.25}
              value={item.weightKg ?? ""}
              onChange={(e) =>
                onChange({ weightKg: e.target.value === "" ? null : Number(e.target.value) })
              }
            />
          </label>
        )}

        <label>
          Calent.
          <input
            className="num"
            type="number"
            min={0}
            max={5}
            value={item.warmup}
            onChange={(e) => onChange({ warmup: Number(e.target.value) || 0 })}
          />
        </label>

        <label>
          Descanso s
          <input
            className="num"
            type="number"
            min={0}
            step={15}
            value={item.restSeconds ?? ""}
            onChange={(e) =>
              onChange({ restSeconds: e.target.value === "" ? null : Number(e.target.value) })
            }
          />
        </label>
      </div>
    </div>
  );
}
