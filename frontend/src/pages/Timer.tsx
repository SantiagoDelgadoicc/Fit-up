/**
 * Pantalla «Descanso».
 *
 * Se diseña para mirarla de reojo, con el móvil en el suelo y sin gafas: el
 * dato es el tiempo y ocupa el centro. Todo lo demás —anillo, color, botones—
 * está por debajo en la jerarquía y nunca compite con los dígitos.
 */

import { useEffect, useState } from "react";

import { useSetSetting, useSettings } from "../api/hooks";
import { Icon } from "../components/icons";
import {
  askNotifications,
  canAskNotifications,
  FALLBACK_PRESETS,
  formatClock,
  formatPreset,
  useTimer,
} from "../components/timer";
import { useToast } from "../components/ui";

/* Geometría del anillo. El radio manda: el resto se deriva de él para que
   cambiar el tamaño sea cambiar un número. */
const R = 120;
const CIRCUMFERENCE = 2 * Math.PI * R;

/** Umbral del tramo final, donde el anillo avisa por color. */
const WARN_SECONDS = 10;

export default function Timer() {
  const timer = useTimer();
  const settings = useSettings();
  const toast = useToast();
  const [canAsk, setCanAsk] = useState(canAskNotifications);

  const raw = settings.data?.["timer_presets_s"];
  const presets =
    Array.isArray(raw) && raw.every((v) => typeof v === "number" && v > 0)
      ? (raw as number[])
      : FALLBACK_PRESETS;

  // El título de la pestaña es el único sitio donde se ve el descanso con la
  // app en segundo plano y el navegador minimizado.
  useEffect(() => {
    const original = document.title;
    if (timer.phase === "running" || timer.phase === "paused") {
      document.title = `${formatClock(timer.remaining)} · Fit-Up`;
    } else if (timer.phase === "done") {
      document.title = "¡Listo! · Fit-Up";
    }
    return () => {
      document.title = original;
    };
  }, [timer.phase, timer.remaining]);

  const state =
    timer.phase === "done" ? "done" : timer.remaining <= WARN_SECONDS ? "warn" : timer.phase;

  return (
    <div className="stack-lg">
      <header className="page-head">
        <div>
          <h1>Descanso</h1>
          <p className="faint" style={{ margin: "2px 0 0" }}>
            Sigue contando aunque cambies de pantalla o cierres la pestaña.
          </p>
        </div>
      </header>

      <section className="timer" data-state={state}>
        <div className="timer-dial">
          <svg viewBox={`0 0 ${(R + 20) * 2} ${(R + 20) * 2}`} aria-hidden="true">
            <circle className="timer-track" cx={R + 20} cy={R + 20} r={R} />
            <circle
              className="timer-arc"
              cx={R + 20}
              cy={R + 20}
              r={R}
              strokeDasharray={CIRCUMFERENCE}
              /* El arco se vacía a medida que pasa el tiempo: lo que queda de
                 color es lo que queda de descanso. Al terminar se rellena
                 entero: un anillo vacío se lee como "apagado", justo lo
                 contrario de lo que hay que mirar en ese momento. */
              strokeDashoffset={
                timer.phase === "done"
                  ? 0
                  : CIRCUMFERENCE * Math.min(1, Math.max(0, timer.progress))
              }
            />
          </svg>
          <div className="timer-readout">
            <output className="timer-clock" aria-live="off">
              {formatClock(timer.remaining)}
            </output>
            <span className="timer-state">
              {timer.phase === "done"
                ? "Descanso terminado"
                : timer.phase === "running"
                  ? "En marcha"
                  : timer.phase === "paused"
                    ? "En pausa"
                    : `Listo · ${formatPreset(timer.duration)}`}
            </span>
          </div>
        </div>

        {/* Los lectores de pantalla no deben oír cada segundo: solo el final. */}
        <p className="sr-only" role="status">
          {timer.phase === "done" ? "Descanso terminado" : ""}
        </p>

        <div className="timer-presets">
          {presets.map((seconds) => (
            <button
              key={seconds}
              className="timer-preset"
              data-active={timer.duration === seconds || undefined}
              onClick={() => timer.start(seconds)}
            >
              {formatPreset(seconds)}
            </button>
          ))}
        </div>

        <div className="timer-actions">
          {timer.phase === "running" ? (
            <button className="btn btn-hero" onClick={timer.pause}>
              <Icon name="pausa" />
              Pausar
            </button>
          ) : timer.phase === "paused" ? (
            <button className="btn btn-primary btn-hero" onClick={timer.resume}>
              <Icon name="reproducir" />
              Reanudar
            </button>
          ) : (
            <button className="btn btn-primary btn-hero" onClick={() => timer.start()}>
              <Icon name="reproducir" />
              Empezar
            </button>
          )}

          <div className="row">
            <button
              className="btn btn-ghost btn-sm"
              onClick={timer.reset}
              disabled={timer.phase === "idle"}
            >
              <Icon name="reiniciar" />
              Reiniciar
            </button>
            <div className="spacer" />
            <button
              className="btn btn-ghost btn-sm"
              onClick={timer.finish}
              disabled={timer.phase === "idle"}
            >
              <Icon name="cerrar" />
              Finalizar
            </button>
          </div>
        </div>
      </section>

      {canAsk && (
        <div className="card row">
          <div>
            <strong>Avisarme cuando termine</strong>
            <div className="faint">
              Con una notificación del sistema, además del sonido.
            </div>
          </div>
          <div className="spacer" />
          <button
            className="btn btn-sm"
            onClick={async () => {
              const ok = await askNotifications();
              setCanAsk(canAskNotifications());
              toast(ok ? "Avisos activados" : "Avisos no permitidos", ok ? "ok" : "error");
            }}
          >
            Activar
          </button>
        </div>
      )}

      <PresetEditor presets={presets} />
    </div>
  );
}

/**
 * Edición de los presets.
 *
 * Vive aquí y no en Ajustes porque es donde se nota que uno no encaja: al
 * descansar. Se guarda en `timer_presets_s`, el mismo ajuste que lee el resto
 * de la app.
 */
function PresetEditor({ presets }: { presets: number[] }) {
  const save = useSetSetting();
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState(presets.map(String));

  useEffect(() => setDraft(presets.map(String)), [presets]);

  if (!open) {
    return (
      <button className="btn btn-ghost btn-sm" onClick={() => setOpen(true)}>
        Cambiar los tiempos
      </button>
    );
  }

  const seconds = draft.map(Number);
  const valid = seconds.every((s) => Number.isFinite(s) && s > 0 && s <= 3600);

  return (
    <section className="card stack">
      <h2>Tiempos rápidos</h2>
      <p className="faint" style={{ margin: 0 }}>
        En segundos. 90 son minuto y medio; 240, cuatro minutos.
      </p>
      <div className="row">
        {draft.map((value, i) => (
          <input
            key={i}
            className="num"
            type="number"
            min={1}
            max={3600}
            value={value}
            aria-label={`Tiempo rápido ${i + 1}`}
            onChange={(e) =>
              setDraft((prev) => prev.map((v, j) => (j === i ? e.target.value : v)))
            }
          />
        ))}
        <div className="spacer" />
        <button className="btn btn-ghost btn-sm" onClick={() => setOpen(false)}>
          Cancelar
        </button>
        <button
          className="btn btn-sm btn-primary"
          disabled={!valid || save.isPending}
          onClick={() =>
            save.mutate(
              { key: "timer_presets_s", value: seconds },
              {
                onSuccess: () => {
                  toast("Tiempos guardados");
                  setOpen(false);
                },
                onError: (e) => toast(e instanceof Error ? e.message : "Error", "error"),
              },
            )
          }
        >
          Guardar
        </button>
      </div>
    </section>
  );
}
