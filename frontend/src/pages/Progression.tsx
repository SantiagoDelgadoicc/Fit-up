/**
 * Pantalla de progresión de una rutina.
 *
 * Dos reglas gobiernan el diseño:
 *
 * 1. **Nada se aplica sin verlo antes.** Cada ejercicio muestra el plan actual,
 *    el propuesto y el porqué; el botón solo confirma lo que ya está a la vista.
 * 2. **Lo que no se puede determinar se dice.** Los `undetermined` se listan
 *    igual que el resto, con su motivo, en vez de desaparecer de la pantalla.
 *
 * El usuario elige *qué* ejercicios progresan. *Cuánto* lo decide el motor en
 * el servidor, que vuelve a evaluarlo al aplicar.
 */

import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import type { ProgressionEvent, ProgressionItem } from "../api/client";
import {
  useApplyProgression,
  useProgression,
  useProgressionEvents,
  useRules,
  useUndoProgression,
} from "../api/hooks";
import {
  Empty,
  ErrorCard,
  formatDateTime,
  Loading,
  OutcomeBadge,
  useToast,
} from "../components/ui";

export default function Progression() {
  const { id } = useParams();
  const routineId = Number(id);

  const evaluation = useProgression(Number.isNaN(routineId) ? null : routineId);
  const events = useProgressionEvents(Number.isNaN(routineId) ? null : routineId);
  const apply = useApplyProgression(routineId);
  const undo = useUndoProgression(routineId);
  const toast = useToast();

  const [selected, setSelected] = useState<string[]>([]);

  const items = useMemo(() => evaluation.data?.items ?? [], [evaluation.data]);

  useEffect(() => {
    // Las subidas vienen marcadas; la descarga no. Bajar la carga es una
    // decisión que merece un clic propio, no heredarse de un valor por defecto.
    setSelected(items.filter((i) => i.outcome === "ready").map((i) => i.exercise_slug));
  }, [items]);

  if (evaluation.isLoading) return <Loading rows={4} />;
  if (evaluation.error) return <ErrorCard error={evaluation.error} />;
  if (!evaluation.data) return null;

  const data = evaluation.data;
  const applicable = items.filter((i) => i.applicable);
  const toggle = (slug: string) =>
    setSelected((prev) =>
      prev.includes(slug) ? prev.filter((s) => s !== slug) : [...prev, slug],
    );

  const aplicar = () =>
    apply.mutate(selected, {
      onSuccess: (result) =>
        toast(
          `Aplicado en la versión ${result.routine.version_no}: ` +
            result.events.map((e) => `${e.exercise_name} ${e.after_summary}`).join(", "),
        ),
      onError: (e) => toast(e instanceof Error ? e.message : "No se pudo aplicar", "error"),
    });

  return (
    <div className="stack-lg">
      <header className="page-head">
        <div>
          <h1>Progresión</h1>
          <p className="faint" style={{ margin: "2px 0 0" }}>
            {data.routine_name} · versión {data.version_no}
          </p>
        </div>
        <Link className="btn btn-sm" to={`/rutinas/${routineId}`}>
          Editar rutina
        </Link>
      </header>

      <Summary
        ready={data.ready}
        deload={data.deload}
        total={items.length}
        selected={selected.length}
        busy={apply.isPending}
        disabled={applicable.length === 0}
        onApply={aplicar}
      />

      <section className="stack">
        {items.length === 0 ? (
          <div className="card">
            <Empty icon="📋">
              <p style={{ margin: 0 }}>Esta rutina no tiene ejercicios.</p>
            </Empty>
          </div>
        ) : (
          items.map((item) => (
            <ItemCard
              key={item.exercise_slug}
              item={item}
              checked={selected.includes(item.exercise_slug)}
              onToggle={() => toggle(item.exercise_slug)}
            />
          ))
        )}
      </section>

      <History
        events={events.data ?? []}
        busy={undo.isPending}
        onUndo={(eventId) =>
          undo.mutate(eventId, {
            onSuccess: () => toast("Progresión deshecha"),
            onError: (e) => toast(e instanceof Error ? e.message : "No se pudo deshacer", "error"),
          })
        }
      />
    </div>
  );
}

function Summary({
  ready,
  deload,
  total,
  selected,
  busy,
  disabled,
  onApply,
}: {
  ready: number;
  deload: number;
  total: number;
  selected: number;
  busy: boolean;
  disabled: boolean;
  onApply: () => void;
}) {
  return (
    <div className="card">
      <div className="row">
        <div>
          <strong>
            {ready === 0 && deload === 0
              ? "Nada que progresar por ahora"
              : `${ready} listo${ready === 1 ? "" : "s"} para progresar`}
          </strong>
          <div className="faint">
            {deload > 0 && `${deload} con descarga sugerida · `}
            {total} ejercicio{total === 1 ? "" : "s"} evaluados
          </div>
        </div>
        <div className="spacer" />
        <button
          className="btn btn-primary"
          onClick={onApply}
          disabled={busy || disabled || selected === 0}
        >
          Aplicar {selected > 0 ? `(${selected})` : ""}
        </button>
      </div>
      <p className="tiny muted" style={{ margin: "10px 0 0" }}>
        Aplicar crea una versión nueva de la rutina. Los entrenamientos ya registrados
        siguen apuntando a la versión con la que se hicieron, y siempre se puede deshacer.
      </p>
    </div>
  );
}

function ItemCard({
  item,
  checked,
  onToggle,
}: {
  item: ProgressionItem;
  checked: boolean;
  onToggle: () => void;
}) {
  const rules = useRules();
  const ruleName =
    rules.data?.find((r) => r.slug === item.rule_slug)?.name ?? item.rule_slug ?? "sin regla";

  return (
    <div className="card" data-outcome={item.outcome}>
      <div className="row">
        {item.applicable ? (
          <label className="pick">
            <input type="checkbox" checked={checked} onChange={onToggle} />
            <strong>{item.exercise_name}</strong>
          </label>
        ) : (
          <strong>{item.exercise_name}</strong>
        )}
        <div className="spacer" />
        <OutcomeBadge outcome={item.outcome} />
      </div>

      <div className="diff">
        <span className="diff-from">{item.current}</span>
        {item.proposed && (
          <>
            <span aria-hidden="true">→</span>
            <span className="diff-to">{item.proposed}</span>
          </>
        )}
      </div>

      {item.next_exercise_name && (
        <p className="variant">
          Cambia de ejercicio: <strong>{item.next_exercise_name}</strong>
        </p>
      )}

      <p className="faint" style={{ margin: "8px 0 0" }}>
        {item.reason}
      </p>

      <p className="tiny muted" style={{ margin: "6px 0 0" }}>
        Regla: {ruleName}
        {item.rule_inherited && " (heredada del catálogo)"}
        {item.last_progression && ` · última progresión el ${item.last_progression}`}
      </p>
    </div>
  );
}

function History({
  events,
  busy,
  onUndo,
}: {
  events: ProgressionEvent[];
  busy: boolean;
  onUndo: (eventId: number) => void;
}) {
  if (events.length === 0) return null;

  return (
    <section className="stack">
      <h2>Progresiones aplicadas</h2>
      <p className="faint" style={{ margin: 0 }}>
        Deshacer no borra nada: crea la versión que restaura el plan anterior.
      </p>
      {events.map((event) => (
        <div className="card" key={event.id}>
          <div className="row">
            <div>
              <strong>{event.exercise_name}</strong>
              <div className="faint">
                {event.before_summary} → {event.after_summary}
              </div>
            </div>
            <div className="spacer" />
            {event.is_reversal ? (
              <span className="tag">Reversión</span>
            ) : event.reverted ? (
              <span className="tag">Deshecha</span>
            ) : (
              <button
                className="btn btn-sm btn-ghost"
                disabled={busy}
                onClick={() => onUndo(event.id)}
              >
                Deshacer
              </button>
            )}
          </div>
          <p className="tiny muted" style={{ margin: "8px 0 0" }}>
            {formatDateTime(event.applied_at)} · versión {event.from_version_no} →{" "}
            {event.to_version_no} · {event.actor}
          </p>
        </div>
      ))}
    </section>
  );
}
