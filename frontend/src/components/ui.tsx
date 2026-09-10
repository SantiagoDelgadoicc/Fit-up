/** Primitivas compartidas por las pantallas. */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type { ReactNode } from "react";

import { Icon } from "./icons";
import type { IconName } from "./icons";

import type {
  DayState,
  PlannedExercise,
  PerformedExercise,
  ProgressionOutcome,
  Tier,
} from "../api/client";

/* ------------------------------------------------------------- Estados */

/**
 * Cada estado lleva **forma** y color, no solo color. Depender del color
 * dejaría la app inservible para quien no lo distinga, y peor aún: `pending`
 * y `missed` significan cosas opuestas y no pueden confundirse. Por eso cada
 * uno tiene su propio símbolo —marca, media luna, círculo punteado, aspa— y
 * no el mismo círculo pintado de otro tono.
 */
const STATE_META: Record<DayState, { icon: IconName; label: string }> = {
  done: { icon: "estado-cumplida", label: "Cumplida" },
  partial: { icon: "estado-parcial", label: "Parcial" },
  pending: { icon: "estado-pendiente", label: "Sin registrar" },
  missed: { icon: "estado-fallada", label: "No realizada" },
  rest: { icon: "estado-descanso", label: "Descanso" },
  extra: { icon: "estado-extra", label: "Extra" },
  excused: { icon: "estado-excusado", label: "Excusado" },
};

export function StateBadge({ state }: { state: DayState }) {
  const meta = STATE_META[state];
  return (
    <span className="badge" data-state={state}>
      <Icon name={meta.icon} />
      {meta.label}
    </span>
  );
}

/**
 * El símbolo del estado a secas, sin la píldora: en la celda del calendario y
 * en la leyenda, donde el nombre ya está escrito al lado o en el `aria-label`.
 */
export function StateDot({ state, className }: { state: DayState; className?: string }) {
  return (
    <span
      className={className ? `state-dot ${className}` : "state-dot"}
      data-state={state}
      aria-hidden="true"
    >
      <Icon name={STATE_META[state].icon} />
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
      s.target_weight_kg === first.target_weight_kg &&
      s.to_failure === first.to_failure,
  );

  const one = (s: (typeof work)[number]) => {
    // Una serie al fallo no tiene objetivo: decirlo con un "?" la haría
    // parecer un dato que falta, cuando es el plan.
    const base = s.to_failure
      ? "fallo"
      : s.target_time_s != null
        ? `${s.target_time_s}s`
        : `${s.target_reps ?? "?"}`;
    return s.target_weight_kg ? `${base} · ${s.target_weight_kg}kg` : base;
  };

  return uniform ? `${work.length}×${one(first)}` : work.map(one).join(" / ");
}

/**
 * El plan de un ejercicio partido en las tres columnas de la tabla.
 *
 * Cuando las series no son uniformes **no se promedia nada**: el objetivo
 * lleva la descripción entera y la carga se queda vacía. Un número inventado
 * en la columna «Carga» sería peor que un hueco, porque parecería un dato.
 */
export function plannedColumns(exercise: PlannedExercise): {
  series: string;
  objetivo: string;
  carga: string | null;
} {
  const work = exercise.sets.filter((s) => !s.is_warmup);
  const first = work[0];
  if (!first) return { series: "—", objetivo: "sin series", carga: null };

  const uniform = work.every(
    (s) =>
      s.target_reps === first.target_reps &&
      s.target_time_s === first.target_time_s &&
      s.target_weight_kg === first.target_weight_kg &&
      s.to_failure === first.to_failure,
  );
  const series = String(work.length);
  if (!uniform) return { series, objetivo: describePlanned(exercise), carga: null };

  // Al fallo no lleva objetivo: o se llega al fallo, o se llega al número.
  const objetivo = first.to_failure
    ? "al fallo"
    : first.target_time_s != null
      ? `${first.target_time_s} s`
      : first.target_reps != null
        ? String(first.target_reps)
        : "—";

  return { series, objetivo, carga: first.target_weight_kg ? `${first.target_weight_kg} kg` : null };
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

export function Empty({ icon, children }: { icon: IconName; children: ReactNode }) {
  return (
    <div className="empty">
      <span className="empty-icon" aria-hidden="true">
        <Icon name={icon} />
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

type Toast = { text: string; kind: "ok" | "error"; leaving?: boolean };
const ToastContext = createContext<(text: string, kind?: Toast["kind"]) => void>(() => {});

export const useToast = () => useContext(ToastContext);

/** Lo que dura leído y lo que tarda en irse. El segundo, en la hoja de estilos. */
const VISIBLE_MS = 3200;
const SALIDA_MS = 180;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toast, setToast] = useState<Toast | null>(null);
  const relojes = useRef<number[]>([]);

  const limpiar = useCallback(() => {
    relojes.current.forEach(clearTimeout);
    relojes.current = [];
  }, []);

  const show = useCallback(
    (text: string, kind: Toast["kind"] = "ok") => {
      // Un aviso nuevo cancela los relojes del anterior. Sin esto, el reloj
      // del primero escondía al segundo antes de que diera tiempo a leerlo.
      limpiar();
      setToast({ text, kind });
      relojes.current.push(
        // Primero se marca la salida y solo después se desmonta: quitarlo de
        // golpe no es irse, es parpadear.
        window.setTimeout(
          () => setToast((t) => (t ? { ...t, leaving: true } : t)),
          VISIBLE_MS,
        ),
        window.setTimeout(() => setToast(null), VISIBLE_MS + SALIDA_MS),
      );
    },
    [limpiar],
  );

  useEffect(() => limpiar, [limpiar]);

  const value = useMemo(() => show, [show]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      {toast && (
        <div
          className="toast"
          data-kind={toast.kind}
          data-leaving={toast.leaving ? "" : undefined}
          role="status"
          aria-live="polite"
        >
          {toast.text}
        </div>
      )}
    </ToastContext.Provider>
  );
}

/* --------------------------------------------------------- Progresión */

/**
 * Los cuatro veredictos del motor, cada uno con icono **y** color.
 *
 * `undetermined` no se esconde ni se disfraza de "aún no": significa que el
 * sistema no puede saberlo, y es información que el usuario necesita para
 * arreglar lo que falte (una regla, un peso sin registrar).
 */
const OUTCOME_META: Record<ProgressionOutcome, { icon: IconName; label: string }> = {
  ready: { icon: "sube", label: "Listo para progresar" },
  not_yet: { icon: "espera", label: "Todavía no" },
  undetermined: { icon: "duda", label: "No se puede determinar" },
  deload_suggested: { icon: "baja", label: "Conviene descargar" },
};

export function OutcomeBadge({ outcome }: { outcome: ProgressionOutcome }) {
  const meta = OUTCOME_META[outcome];
  return (
    <span className="badge" data-outcome={outcome}>
      <Icon name={meta.icon} />
      {meta.label}
    </span>
  );
}

export const outcomeLabel = (outcome: ProgressionOutcome) => OUTCOME_META[outcome].label;

/** Fecha con hora, para los instantes de auditoría (aplicado el…). */
export function formatDateTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleDateString("es-ES", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/* ---------------------------------------------------------------- Rangos */

/**
 * Los rangos se muestran con su nombre inglés a propósito: son un vocabulario
 * de videojuego reconocible, y traducirlos ("Platino", "Diamante") los
 * convertiría en algo distinto y peor.
 */
const TIER_NAMES: Record<Tier, string> = {
  sin_datos: "Sin datos",
  iron: "Iron",
  bronze: "Bronze",
  silver: "Silver",
  gold: "Gold",
  platinum: "Platinum",
  diamond: "Diamond",
  ascendant: "Ascendant",
  immortal: "Immortal",
  radiant: "Radiant",
};

export const tierLabel = (tier: Tier): string => TIER_NAMES[tier];

export function TierBadge({ tier, size }: { tier: Tier; size?: "lg" }) {
  return (
    <span className={size === "lg" ? "badge badge-lg" : "badge"} data-tier={tier}>
      {tierLabel(tier)}
    </span>
  );
}
