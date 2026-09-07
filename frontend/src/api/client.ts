/**
 * Cliente HTTP tipado.
 *
 * Los tipos salen de `schema.d.ts`, generado desde el OpenAPI del backend: el
 * contrato se define una sola vez (ADR-0002). Si cambia un endpoint y el
 * frontend no se adapta, falla el `typecheck`, no el usuario.
 */

import type { components } from "./schema";

type S = components["schemas"];

export type Muscle = S["MuscleOut"];
export type Exercise = S["ExerciseOut"];
export type Rule = S["RuleOut"];
export type RoutineSummary = S["RoutineSummaryOut"];
export type Routine = S["RoutineOut"];
export type PlannedExercise = S["PlannedExerciseOut"];
export type PlannedSet = S["PlannedSetOut"];
export type Session = S["SessionOut"];
export type PerformedExercise = S["PerformedExerciseOut"];
export type Day = S["DayOut"];
export type DayState = S["DayState"];
export type PendingDay = S["PendingDayOut"];
export type Calendar = S["CalendarOut"];
export type Week = S["WeekOut"];
export type Bodyweight = S["BodyweightOut"];
export type RoutineInput = S["RoutineIn"];
export type SetSpec = S["SetSpec"];
export type RoutineProgression = S["RoutineProgressionOut"];
export type ProgressionItem = S["ProgressionItemOut"];
export type ProgressionOutcome = S["ProgressionOutcome"];
export type ProgressionEvent = S["ProgressionEventOut"];
export type ProgressionApplied = S["ProgressionAppliedOut"];
export type RoutineReadiness = S["RoutineReadinessOut"];

const TOKEN_KEY = "fitup.token";

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    // Modo privado o almacenamiento bloqueado: sin token, pero la app sigue
    // funcionando en local, donde no hace falta.
    return null;
  }
}

export function setToken(token: string | null): void {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* ignorado a propósito */
  }
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }

  /** El servidor pide token: hay que emparejar este dispositivo. */
  get needsToken(): boolean {
    return this.status === 401;
  }
}

type Options = {
  method?: string;
  body?: unknown;
  idempotencyKey?: string;
};

export async function api<T>(path: string, options: Options = {}): Promise<T> {
  const headers: Record<string, string> = {};
  if (options.body !== undefined) headers["Content-Type"] = "application/json";

  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (options.idempotencyKey) headers["Idempotency-Key"] = options.idempotencyKey;

  const response = await fetch(`/api${path}`, {
    method: options.method ?? "GET",
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  });

  if (!response.ok) {
    throw new ApiError(response.status, await readError(response));
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

async function readError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body?.detail === "string") return body.detail;
    // Errores de validación de Pydantic: una lista de problemas por campo.
    if (Array.isArray(body?.detail)) {
      return body.detail.map((d: { msg?: string }) => d.msg ?? "dato inválido").join("; ");
    }
  } catch {
    /* la respuesta no era JSON */
  }
  return `Error ${response.status}`;
}

/**
 * Clave de idempotencia para un registro.
 *
 * Se deriva de la acción y del día, no es aleatoria: si el móvil pierde
 * cobertura y el usuario vuelve a pulsar, el reintento lleva la misma clave y
 * el backend devuelve la sesión existente en vez de duplicarla.
 */
export function logKey(action: string, date: string): string {
  return `${action}:${date}`;
}

/** Fecha local en ISO. `toISOString()` daría UTC y podría cambiar el día. */
export function localDate(d: Date = new Date()): string {
  const offset = d.getTimezoneOffset() * 60_000;
  return new Date(d.getTime() - offset).toISOString().slice(0, 10);
}
