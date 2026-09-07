/**
 * Hooks de datos.
 *
 * Un único sitio donde vive el conocimiento de qué invalida qué: registrar un
 * entrenamiento cambia el día, los pendientes, el calendario y el historial, y
 * olvidarse de uno de ellos deja la pantalla mintiendo.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  api,
  logKey,
  type Bodyweight,
  type Calendar,
  type Day,
  type Exercise,
  type Muscle,
  type PendingDay,
  type Routine,
  type RoutineInput,
  type RoutineSummary,
  type Rule,
  type Session,
  type Week,
} from "./client";

const keys = {
  today: ["hoy"] as const,
  day: (date: string) => ["dia", date] as const,
  pending: ["pendientes"] as const,
  routines: ["rutinas"] as const,
  routine: (id: number) => ["rutina", id] as const,
  week: ["semana"] as const,
  sessions: ["sesiones"] as const,
  calendar: (year: number, month: number) => ["calendario", year, month] as const,
  exercises: ["ejercicios"] as const,
  muscles: ["musculos"] as const,
  rules: ["reglas"] as const,
  settings: ["ajustes"] as const,
  bodyweight: ["peso"] as const,
};

/** Todo lo que deja de ser cierto cuando se registra o borra un entrenamiento. */
function invalidateTraining(qc: ReturnType<typeof useQueryClient>) {
  for (const key of [keys.today, keys.pending, keys.sessions, ["dia"], ["calendario"]]) {
    void qc.invalidateQueries({ queryKey: key as readonly unknown[] });
  }
}

// --------------------------------------------------------------------------
// Catálogo
// --------------------------------------------------------------------------

export const useExercises = () =>
  useQuery({
    queryKey: keys.exercises,
    queryFn: () => api<Exercise[]>("/catalogo/ejercicios"),
    staleTime: Infinity, // el catálogo no cambia durante la sesión
  });

export const useMuscles = () =>
  useQuery({
    queryKey: keys.muscles,
    queryFn: () => api<Muscle[]>("/catalogo/musculos"),
    staleTime: Infinity,
  });

export const useRules = () =>
  useQuery({
    queryKey: keys.rules,
    queryFn: () => api<Rule[]>("/catalogo/reglas"),
    staleTime: Infinity,
  });

// --------------------------------------------------------------------------
// Día y pendientes
// --------------------------------------------------------------------------

export const useToday = () =>
  useQuery({ queryKey: keys.today, queryFn: () => api<Day>("/hoy") });

export const useDay = (date: string) =>
  useQuery({ queryKey: keys.day(date), queryFn: () => api<Day>(`/dias/${date}`) });

export const usePending = () =>
  useQuery({ queryKey: keys.pending, queryFn: () => api<PendingDay[]>("/pendientes") });

export const useCalendar = (year: number, month: number) =>
  useQuery({
    queryKey: keys.calendar(year, month),
    queryFn: () => api<Calendar>(`/calendario/${year}/${month}`),
  });

// --------------------------------------------------------------------------
// Registro
// --------------------------------------------------------------------------

export function useLogAsPlanned() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { date: string; status?: "completed" | "partial" }) =>
      api<Session>("/sesiones/como-planificado", {
        method: "POST",
        body: { date: input.date, status: input.status ?? "completed" },
        idempotencyKey: logKey(`planned-${input.status ?? "completed"}`, input.date),
      }),
    onSuccess: () => invalidateTraining(qc),
  });
}

export function useSkipDay() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (date: string) =>
      api<Session>("/sesiones/no-realizado", { method: "POST", body: { date } }),
    onSuccess: () => invalidateTraining(qc),
  });
}

export function useDeleteSession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api<void>(`/sesiones/${id}`, { method: "DELETE" }),
    onSuccess: () => invalidateTraining(qc),
  });
}

export const useSessions = (limit = 50) =>
  useQuery({
    queryKey: keys.sessions,
    queryFn: () => api<Session[]>(`/sesiones?limit=${limit}`),
  });

// --------------------------------------------------------------------------
// Rutinas y semana
// --------------------------------------------------------------------------

export const useRoutines = () =>
  useQuery({ queryKey: keys.routines, queryFn: () => api<RoutineSummary[]>("/rutinas") });

export const useRoutine = (id: number | null) =>
  useQuery({
    queryKey: keys.routine(id ?? 0),
    queryFn: () => api<Routine>(`/rutinas/${id}`),
    enabled: id !== null,
  });

export function useSaveRoutine() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: number | null; body: RoutineInput }) =>
      id === null
        ? api<Routine>("/rutinas", { method: "POST", body })
        : api<Routine>(`/rutinas/${id}`, { method: "PUT", body }),
    onSuccess: (routine) => {
      void qc.invalidateQueries({ queryKey: keys.routines });
      void qc.invalidateQueries({ queryKey: keys.routine(routine.id) });
      // El plan del día sale de la rutina: si cambia, el día también.
      invalidateTraining(qc);
    },
  });
}

export function useArchiveRoutine() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api<void>(`/rutinas/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: keys.routines });
      void qc.invalidateQueries({ queryKey: keys.week });
      invalidateTraining(qc);
    },
  });
}

export const useWeek = () =>
  useQuery({ queryKey: keys.week, queryFn: () => api<Week>("/semana") });

export function useSaveWeek() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (days: Record<string, number | null>) =>
      api<Week>("/semana", { method: "PUT", body: { days } }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: keys.week });
      invalidateTraining(qc);
    },
  });
}

export function useClearException() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (date: string) => api<void>(`/excepciones/${date}`, { method: "DELETE" }),
    onSuccess: () => invalidateTraining(qc),
  });
}

export function useSetException() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ date, reason }: { date: string; reason: string }) =>
      api<void>(`/excepciones/${date}`, { method: "PUT", body: { reason } }),
    onSuccess: () => invalidateTraining(qc),
  });
}

// --------------------------------------------------------------------------
// Ajustes y peso
// --------------------------------------------------------------------------

export const useSettings = () =>
  useQuery({ queryKey: keys.settings, queryFn: () => api<Record<string, unknown>>("/ajustes") });

export function useSetSetting() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ key, value }: { key: string; value: unknown }) =>
      api<unknown>(`/ajustes/${key}`, { method: "PUT", body: { value } }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: keys.settings });
      // La ventana de gracia decide qué días son "pendientes".
      invalidateTraining(qc);
    },
  });
}

export const useBodyweight = () =>
  useQuery({
    queryKey: keys.bodyweight,
    queryFn: () => api<Bodyweight | null>("/peso/actual"),
  });

export function useSetBodyweight() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { date: string; weight_kg: number }) =>
      api<Bodyweight>("/peso", { method: "PUT", body: input }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: keys.bodyweight }),
  });
}

/**
 * Traduce slugs a nombres legibles usando el catálogo ya cargado.
 *
 * El backend devuelve slugs porque son la clave estable; mostrar
 * "press_banca" en pantalla sería filtrar un detalle interno al usuario.
 */
export function useExerciseNames(): (slug: string) => string {
  const { data } = useExercises();
  return (slug: string) =>
    data?.find((e) => e.slug === slug)?.name ??
    slug.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
}
