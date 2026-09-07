/**
 * Temporizador de descanso: estado, persistencia y aviso.
 *
 * Se guarda **el instante de fin**, no los segundos que quedan. Un contador
 * que se decrementa se desincroniza en cuanto el navegador ralentiza la
 * pestaña en segundo plano, que es justo lo que pasa mientras entrenas con el
 * móvil en el bolsillo. Con un instante absoluto, el tiempo restante se
 * recalcula del reloj y da igual cuántos ticks se hayan perdido.
 *
 * El estado vive en `localStorage` y se sincroniza entre pestañas con el
 * evento `storage`: abrir la app en el móvil y en el PC no debe dar dos
 * descansos distintos.
 */

import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { Link, useLocation } from "react-router-dom";

const KEY = "fitup.timer";

/** Presets de reserva mientras no se han leído los ajustes. */
export const FALLBACK_PRESETS = [120, 90, 240];

type Persisted = {
  /** Duración elegida, en segundos. */
  duration: number;
  /** Instante de fin (epoch ms) mientras corre; `null` si está parado. */
  endsAt: number | null;
  /** Restante congelado (ms) mientras está en pausa; `null` si no lo está. */
  pausedMs: number | null;
  /**
   * Instante en que ya se avisó de este descanso. Evita que varias pestañas
   * abiertas piten a coro y que un aviso se repita al recargar.
   */
  alertedAt: number | null;
};

const INITIAL: Persisted = { duration: 120, endsAt: null, pausedMs: null, alertedAt: null };

export type TimerPhase = "idle" | "running" | "paused" | "done";

function read(): Persisted {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return INITIAL;
    const parsed = JSON.parse(raw) as Partial<Persisted>;
    return {
      duration: typeof parsed.duration === "number" ? parsed.duration : INITIAL.duration,
      endsAt: typeof parsed.endsAt === "number" ? parsed.endsAt : null,
      pausedMs: typeof parsed.pausedMs === "number" ? parsed.pausedMs : null,
      alertedAt: typeof parsed.alertedAt === "number" ? parsed.alertedAt : null,
    };
  } catch {
    // Modo privado, almacenamiento lleno o JSON corrupto: el temporizador es
    // una comodidad, no puede tumbar la pantalla.
    return INITIAL;
  }
}

function write(state: Persisted) {
  try {
    localStorage.setItem(KEY, JSON.stringify(state));
  } catch {
    /* Sin persistencia el temporizador sigue funcionando en esta pestaña. */
  }
}

/*
 * Store compartido por todos los `useTimer` de la pestaña.
 *
 * `localStorage` por sí solo no basta: su evento `storage` avisa a las **otras**
 * pestañas, nunca a la que escribió. Sin este store, la pantalla de descanso y
 * la píldora de la navegación tendrían cada una su propia copia del estado y la
 * píldora no se enteraría de que el descanso ha empezado.
 */
let snapshot: Persisted = read();
const listeners = new Set<() => void>();

function emit() {
  for (const listener of listeners) listener();
}

function publish(next: Persisted) {
  snapshot = next;
  write(next);
  emit();
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

if (typeof window !== "undefined") {
  window.addEventListener("storage", (e) => {
    if (e.key !== KEY) return;
    snapshot = read();
    emit();
  });
}

/** mm:ss — con `padStart` para que los dígitos no bailen al pasar de 100 a 99. */
export function formatClock(seconds: number): string {
  const s = Math.max(0, Math.ceil(seconds));
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

/** «2:00», para etiquetar un preset sin el cero de relleno de la izquierda. */
export const formatPreset = (seconds: number) =>
  `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;

/**
 * Tres pitidos sintetizados con WebAudio.
 *
 * Sin fichero de audio a propósito: un `.mp3` en el repositorio es un binario
 * que versionar, servir y mantener para 200 ms de sonido.
 */
function beep() {
  try {
    const Ctx = window.AudioContext ?? (window as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!Ctx) return;
    const ctx = new Ctx();
    [0, 0.28, 0.56].forEach((offset, i) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.value = i === 2 ? 1046 : 784;
      const t = ctx.currentTime + offset;
      // Rampas en vez de cortes secos: un gate abrupto suena a chasquido.
      gain.gain.setValueAtTime(0.0001, t);
      gain.gain.exponentialRampToValueAtTime(0.35, t + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.22);
      osc.connect(gain).connect(ctx.destination);
      osc.start(t);
      osc.stop(t + 0.24);
    });
    setTimeout(() => void ctx.close(), 1200);
  } catch {
    /* El navegador puede bloquear el audio sin interacción previa. */
  }
}

function notify() {
  try {
    if (typeof Notification === "undefined" || Notification.permission !== "granted") return;
    new Notification("Descanso terminado", { body: "A por la siguiente serie.", tag: "fitup-timer" });
  } catch {
    /* Algunos navegadores exigen service worker para notificar. */
  }
}

export type Timer = {
  phase: TimerPhase;
  /** Segundos restantes, ya redondeados hacia arriba. */
  remaining: number;
  duration: number;
  /** 0 → recién empezado · 1 → agotado. */
  progress: number;
  start: (seconds?: number) => void;
  pause: () => void;
  resume: () => void;
  reset: () => void;
  finish: () => void;
  setDuration: (seconds: number) => void;
};

export function useTimer(): Timer {
  const state = useSyncExternalStore(subscribe, () => snapshot, () => snapshot);
  const [now, setNow] = useState(() => Date.now());
  const alerted = useRef(false);

  const update = useCallback((next: Persisted) => publish(next), []);

  // Solo se tiquea mientras corre: parado no hay nada que recalcular.
  useEffect(() => {
    if (state.endsAt === null) return;
    setNow(Date.now());
    const id = window.setInterval(() => setNow(Date.now()), 250);
    return () => window.clearInterval(id);
  }, [state.endsAt]);

  const remainingMs = useMemo(() => {
    if (state.endsAt !== null) return Math.max(0, state.endsAt - now);
    if (state.pausedMs !== null) return state.pausedMs;
    return state.duration * 1000;
  }, [state, now]);

  const phase: TimerPhase = useMemo(() => {
    if (state.endsAt !== null) return remainingMs <= 0 ? "done" : "running";
    if (state.pausedMs !== null) return "paused";
    return "idle";
  }, [state, remainingMs]);

  // El aviso salta una sola vez por descanso, y solo en la pestaña que llega
  // primero: `alertedAt` viaja por localStorage y las demás lo ven puesto.
  useEffect(() => {
    if (phase !== "done") {
      alerted.current = false;
      return;
    }
    if (alerted.current) return;
    alerted.current = true;
    const fresh = read();
    if (fresh.alertedAt !== null) return;
    update({ ...fresh, alertedAt: Date.now() });
    beep();
    notify();
  }, [phase, update]);

  const start = useCallback(
    (seconds?: number) => {
      const duration = seconds ?? state.duration;
      update({ duration, endsAt: Date.now() + duration * 1000, pausedMs: null, alertedAt: null });
    },
    [state.duration, update],
  );

  const pause = useCallback(() => {
    if (state.endsAt === null) return;
    update({ ...state, endsAt: null, pausedMs: Math.max(0, state.endsAt - Date.now()) });
  }, [state, update]);

  const resume = useCallback(() => {
    if (state.pausedMs === null) return;
    update({ ...state, endsAt: Date.now() + state.pausedMs, pausedMs: null });
  }, [state, update]);

  const reset = useCallback(() => {
    update({ ...state, endsAt: null, pausedMs: null, alertedAt: null });
  }, [state, update]);

  const finish = useCallback(() => {
    update({ duration: state.duration, endsAt: null, pausedMs: null, alertedAt: null });
  }, [state.duration, update]);

  const setDuration = useCallback(
    (seconds: number) => update({ duration: seconds, endsAt: null, pausedMs: null, alertedAt: null }),
    [update],
  );

  return {
    phase,
    remaining: Math.ceil(remainingMs / 1000),
    duration: state.duration,
    progress: state.duration > 0 ? 1 - remainingMs / (state.duration * 1000) : 1,
    start,
    pause,
    resume,
    reset,
    finish,
    setDuration,
  };
}

/** ¿Se puede pedir permiso para notificar? */
export const canAskNotifications = () =>
  typeof Notification !== "undefined" && Notification.permission === "default";

export const askNotifications = async () => {
  if (typeof Notification === "undefined") return false;
  return (await Notification.requestPermission()) === "granted";
};

/**
 * Píldora del temporizador en la navegación.
 *
 * Solo aparece cuando hay un descanso en marcha o recién terminado: una
 * pastilla siempre visible con 00:00 es ruido permanente por un uso puntual.
 * Y nunca en la propia pantalla de descanso, donde repetiría el mismo dato
 * que ocupa el centro.
 */
export function TimerPill() {
  const timer = useTimer();
  const { pathname } = useLocation();
  if (timer.phase === "idle" || pathname === "/descanso") return null;

  return (
    <Link className="timer-pill" to="/descanso" data-phase={timer.phase}>
      <span aria-hidden="true">{timer.phase === "done" ? "🔔" : "⏱"}</span>
      <span className="timer-pill-clock">{formatClock(timer.remaining)}</span>
    </Link>
  );
}
