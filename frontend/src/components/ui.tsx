/** Primitivas compartidas por las pantallas. */

import { createContext, useCallback, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";

import type { DayState, PlannedExercise, PerformedExercise } from "../api/client";

/* ------------------------------------------------------------- Estados */

/**
 * Cada estado lleva icono **y** color. Depender solo del color dejaría la app
 * inservible para quien no los distinga, y peor aún: `pending` y `missed`
 * significan cosas opuestas y no pueden confundirse.
 */
const STATE_META: Record<DayState, { icon: string; label: string }> = {
  done: { icon: "🟢", label: "Cumplida" },
  partial: { icon: "🟡", label: "Parcial" },
  pending: { icon: "🟠", label: "Sin registrar" },
  missed: { icon: "🔴", label: "No realizada" },
  rest: { icon: "⚪", label: "Descanso" },
  extra: { icon: "🔵", label: "Extra" },
  excused: { icon: "⚫", label: "Excusado" },
};

export function StateBadge({ state }: { state: DayState }) {
  const meta = STATE_META[state];
  return (
    <span className="badge" data-state={state}>
      <span aria-hidden="true">{meta.icon}</span>
      {meta.label}
    </span>
  );
}

export const stateLabel = (state: DayState) => STATE_META[state].label;

/* -------------------------------------------------------------- Fechas */

const DAY_NAMES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"];

export const weekdayName = (weekday: number) => DAY_NAMES[weekday] ?? "";

export function formatDate(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  if (!y || !m || !d) return iso;
  // Construida con componentes locales: `new Date(iso)` la interpretaría como
  // UTC y en husos negativos mostraría el día anterior.
  const date = new Date(y, m - 1, d);
  return date.toLocaleDateString("es-ES", { weekday: "long", day: "numeric", month: "long" });
}

export function relativeDate(iso: string, today: string): string {
  if (iso === today) return "Hoy";
  const [y, m, d] = iso.split("-").map(Number);
  const [ty, tm, td] = today.split("-").map(Number);
  if (!y || !m || !d || !ty || !tm || !td) return formatDate(iso);
  const diff = Math.round(
    (new Date(ty, tm - 1, td).getTime() - new Date(y, m - 1, d).getTime()) / 86_400_000,
  );
  if (diff === 1) return "Ayer";
  if (diff > 1 && diff < 7) return weekdayName(new Date(y, m - 1, d).getDay() === 0 ? 6 : new Date(y, m - 1, d).getDay() - 1);
  return formatDate(iso);
}

/* ----------------------------------------------------------- Ejercicios */

/** Resumen legible de un plan: `3x15`, `3x8 · 40kg`, `3x45s`. */
export function describePlanned(exercise: PlannedExercise): string {
  const work = exercise.sets.filter((s) => !s.is_warmup);
  const first = work[0];
  if (!first) return "sin series";

  const uniform = work.every(
    (s) =>
      s.target_reps === first.target_reps &&
      s.target_time_s === first.target_time_s &&
      s.target_weight_kg === first.target_weight_kg,
  );

  const one = (s: (typeof work)[number]) => {
    const base = s.target_time_s != null ? `${s.target_time_s}s` : `${s.target_reps ?? "?"}`;
    return s.target_weight_kg ? `${base} · ${s.target_weight_kg}kg` : base;
  };

  return uniform ? `${work.length}×${one(first)}` : work.map(one).join(" / ");
}

export function describePerformed(exercise: PerformedExercise): string {
  const work = exercise.sets.filter((s) => !s.is_warmup && s.completed);
  if (work.length === 0) return "sin series completadas";
  const first = work[0]!;
  const uniform = work.every(
    (s) => s.reps === first.reps && s.time_s === first.time_s && s.weight_kg === first.weight_kg,
  );
  const one = (s: (typeof work)[number]) => {
    const base = s.time_s != null ? `${s.time_s}s` : `${s.reps ?? "?"}`;
    return s.weight_kg ? `${base} · ${s.weight_kg}kg` : base;
  };
  return uniform ? `${work.length}×${one(first)}` : work.map(one).join(" / ");
}

/* ------------------------------------------------------------- Estados */

export function Empty({ icon, children }: { icon: string; children: ReactNode }) {
  return (
    <div className="empty">
      <span className="empty-icon" aria-hidden="true">
        {icon}
      </span>
      {children}
    </div>
  );
}

export function Loading({ rows = 2 }: { rows?: number }) {
  return (
    <div className="stack" aria-busy="true" aria-label="Cargando">
      {Array.from({ length: rows }, (_, i) => (
        <div className="skeleton" key={i} />
      ))}
    </div>
  );
}

export function ErrorCard({ error }: { error: unknown }) {
  const message = error instanceof Error ? error.message : "Algo ha fallado";
  return (
    <div className="card error" role="alert">
      {message}
    </div>
  );
}

/* --------------------------------------------------------------- Avisos */

type Toast = { text: string; kind: "ok" | "error" };
const ToastContext = createContext<(text: string, kind?: Toast["kind"]) => void>(() => {});

export const useToast = () => useContext(ToastContext);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toast, setToast] = useState<Toast | null>(null);

  const show = useCallback((text: string, kind: Toast["kind"] = "ok") => {
    setToast({ text, kind });
    setTimeout(() => setToast(null), 3200);
  }, []);

  const value = useMemo(() => show, [show]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      {toast && (
        <div className="toast" data-kind={toast.kind} role="status" aria-live="polite">
          {toast.text}
        </div>
      )}
    </ToastContext.Provider>
  );
}
