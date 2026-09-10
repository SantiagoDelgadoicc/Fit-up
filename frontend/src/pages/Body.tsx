/**
 * Pantalla «Cuerpo»: el ranking muscular.
 *
 * Es la característica visual insignia, y por eso mismo la que más fácil
 * mentiría. Tres reglas la gobiernan:
 *
 * 1. **El rango es desarrollo; la actividad es un halo** (ADR-0003). Nunca se
 *    mezclan: el color dice de qué eres capaz, el borde si lo estás
 *    entrenando.
 * 2. **"Sin datos" no es Iron.** Un músculo sin marcas sale con trama y lo
 *    dice con palabras, no como el más débil de la lista.
 * 3. **La calibración es provisional** y se declara en pantalla. Presentar
 *    estos umbrales como una medición sería el error más caro de la fase.
 *
 * La misma información viaja por dos caminos —mapa y lista— porque el mapa
 * solo funciona si distingues los colores, y la lista funciona siempre.
 */

import { useState } from "react";
import { Link } from "react-router-dom";

import type { BalanceCheck, MuscleDetail, MuscleRanking } from "../api/client";
import { useExerciseNames, useMarkUnits, useMuscle, useRanking } from "../api/hooks";
import BodyMap, { FRESHNESS_LABEL, freshness } from "../components/BodyMap";
import { Empty, ErrorCard, Loading, TierBadge, formatDate, tierLabel } from "../components/ui";

const TIER_ORDER = [
  "radiant",
  "immortal",
  "ascendant",
  "diamond",
  "platinum",
  "gold",
  "silver",
  "bronze",
  "iron",
] as const;

export default function Body() {
  const ranking = useRanking();
  const [selected, setSelected] = useState<string | null>(null);
  const detail = useMuscle(selected);

  if (ranking.isLoading) return <Loading rows={4} />;
  if (ranking.error) return <ErrorCard error={ranking.error} />;
  if (!ranking.data) return null;

  const data = ranking.data;
  const medidos = data.entries.filter((e) => e.has_data);

  return (
    <div className="stack-lg">
      <header className="page-head">
        <div>
          <h1>Cuerpo</h1>
          <p className="faint" style={{ margin: "2px 0 0" }}>
            {medidos.length} de {data.entries.length} músculos con rango ·{" "}
            {data.bodyweight_kg ? `${data.bodyweight_kg} kg` : "sin peso corporal"}
          </p>
        </div>
      </header>

      {data.notes.map((note) => (
        <div className="card note" key={note}>
          {note}
          {note.includes("peso corporal") && (
            <>
              {" "}
              <Link to="/ajustes">Ir a Ajustes</Link>
            </>
          )}
        </div>
      ))}

      <div className="split">
        <div className="stack">
          <div className="card">
            <div className="body-views">
              <BodyMap
                view="frontal"
                entries={data.entries}
                selected={selected}
                onSelect={setSelected}
              />
              <BodyMap
                view="dorsal"
                entries={data.entries}
                selected={selected}
                onSelect={setSelected}
              />
            </div>
            <Legend />
            {data.provisional && (
              <p className="tiny muted" style={{ margin: "12px 0 0" }}>
                Calibración provisional (fórmula {data.formula_version}): los umbrales están
                razonados, no validados con datos reales todavía. Sirven para comparar tu
                progreso contigo mismo, no con nadie más.
              </p>
            )}
          </div>

          <Balance checks={data.balance} />
          <MuscleList entries={data.entries} selected={selected} onSelect={setSelected} />
        </div>

        <aside>
          {selected === null ? (
            <div className="card">
              <Empty icon="puntero">
                <p style={{ margin: 0 }}>Toca un músculo para ver de dónde sale su rango.</p>
              </Empty>
            </div>
          ) : detail.isLoading ? (
            <Loading rows={3} />
          ) : detail.data ? (
            <MuscleCard detail={detail.data} />
          ) : null}
        </aside>
      </div>
    </div>
  );
}

function Legend() {
  return (
    <div className="tier-legend" aria-hidden="true">
      {TIER_ORDER.slice()
        .reverse()
        .map((tier) => (
          <span key={tier} className="tier-chip" data-tier={tier}>
            {tierLabel(tier)}
          </span>
        ))}
      <span className="tier-chip" data-tier="sin_datos">
        Sin datos
      </span>
    </div>
  );
}

function Balance({ checks }: { checks: BalanceCheck[] }) {
  const avisos = checks.filter((c) => c.verdict === "desequilibrio");
  if (avisos.length === 0) return null;

  return (
    <section className="stack">
      <h2>Equilibrio</h2>
      {avisos.map((check) => (
        <div className="card note" key={check.key}>
          <strong>{check.name}</strong>
          <p style={{ margin: "6px 0 0" }}>{check.message}</p>
          <p className="tiny muted" style={{ margin: "8px 0 0" }}>
            {check.left_name} {check.left_score} · {check.right_name} {check.right_score}
          </p>
        </div>
      ))}
    </section>
  );
}

function MuscleList({
  entries,
  selected,
  onSelect,
}: {
  entries: MuscleRanking[];
  selected: string | null;
  onSelect: (slug: string) => void;
}) {
  // Por rango descendente; los que no tienen, al final y en su propio bloque:
  // mezclarlos con los medidos sugeriría que están los últimos de la lista.
  const medidos = entries
    .filter((e) => e.has_data)
    .sort((a, b) => (b.development ?? 0) - (a.development ?? 0));
  const sinDatos = entries.filter((e) => !e.has_data);

  return (
    <section className="stack">
      <h2>Ranking por músculo</h2>
      {medidos.length === 0 ? (
        <div className="card">
          <Empty icon="grafica">
            <p style={{ margin: 0 }}>Todavía no hay ningún músculo con rango.</p>
            <p className="faint" style={{ marginBottom: 0 }}>
              Registra entrenamientos con carga y repeticiones, y anota tu peso corporal.
            </p>
          </Empty>
        </div>
      ) : (
        <div className="card card-flush">
          {medidos.map((entry) => (
            <MuscleRow
              key={entry.muscle_slug}
              entry={entry}
              selected={selected === entry.muscle_slug}
              onSelect={() => onSelect(entry.muscle_slug)}
            />
          ))}
        </div>
      )}

      {sinDatos.length > 0 && (
        <details className="card">
          <summary>{sinDatos.length} músculos sin datos</summary>
          <p className="tiny muted" style={{ margin: "10px 0 0" }}>
            No están débiles: no están medidos. Aparecerán en cuanto registres un
            entrenamiento que los trabaje con carga o tiempo anotados.
          </p>
          <div className="stack" style={{ marginTop: 10 }}>
            {sinDatos.map((entry) => (
              <button
                className="row-button"
                key={entry.muscle_slug}
                onClick={() => onSelect(entry.muscle_slug)}
              >
                <span>{entry.name}</span>
                <span className="spacer" />
                <span className="faint tiny">{FRESHNESS_LABEL[freshness(entry.days_since_stimulus)]}</span>
              </button>
            ))}
          </div>
        </details>
      )}
    </section>
  );
}

function MuscleRow({
  entry,
  selected,
  onSelect,
}: {
  entry: MuscleRanking;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button className="muscle-row" onClick={onSelect} aria-pressed={selected}>
      <span className="muscle-name">{entry.name}</span>
      <span className="bar" aria-hidden="true">
        <span
          className="bar-fill"
          data-tier={entry.tier}
          style={{ width: `${Math.max(3, entry.development ?? 0)}%` }}
        />
      </span>
      <span className="muscle-score">{entry.development?.toFixed(0)}</span>
      <TierBadge tier={entry.tier} />
      <span className="halo-dot" data-fresh={freshness(entry.days_since_stimulus)} title={FRESHNESS_LABEL[freshness(entry.days_since_stimulus)]} />
    </button>
  );
}

function MuscleCard({ detail }: { detail: MuscleDetail }) {
  const m = detail.muscle;
  const fresh = freshness(m.days_since_stimulus);
  const nameOf = useExerciseNames();
  const marcaUnidad = useMarkUnits();

  return (
    <div className="stack">
      <div className="card">
        <div className="row">
          <div>
            <h2>{m.name}</h2>
            <div className="faint">{m.region.replace(/_/g, " ")}</div>
          </div>
          <div className="spacer" />
          <TierBadge tier={m.tier} size="lg" />
        </div>

        {m.has_data ? (
          <>
            <div className="metric-row">
              <div className="metric">
                <span className="metric-value">{m.development?.toFixed(0)}</span>
                <span className="faint">desarrollo</span>
              </div>
              <div className="metric">
                <span className="metric-value">{m.activity.toFixed(0)}</span>
                <span className="faint">actividad</span>
              </div>
            </div>
            <p className="tiny muted" style={{ margin: "10px 0 0" }}>
              {FRESHNESS_LABEL[fresh]}
              {m.days_since_stimulus !== null && ` · hace ${m.days_since_stimulus} día(s)`}
            </p>
            {detail.next_tier && (
              <div className="hito">
                <span className="hito-etiqueta">Siguiente hito</span>
                {m.next_mark && m.leading_exercise ? (
                  <>
                    {/* La cifra concreta, no los puntos: "te faltan 3 dominadas"
                        se puede entrenar mañana; "te faltan 12 puntos", no. */}
                    <p style={{ margin: 0 }}>
                      <strong>{Math.ceil(m.next_mark)}</strong>{" "}
                      {marcaUnidad(m.leading_exercise)} de{" "}
                      <strong>{nameOf(m.leading_exercise)}</strong> para{" "}
                      {tierLabel(detail.next_tier)}.
                    </p>
                    {m.leading_mark !== null && m.leading_mark !== undefined && (
                      <p className="tiny muted" style={{ margin: 0 }}>
                        Tu mejor marca confirmada: {m.leading_mark}. Cuenta cuando la
                        repites en dos sesiones.
                      </p>
                    )}
                  </>
                ) : (
                  /* Sin marca alcanzable el ejercicio ha tocado su techo.
                     Decir "faltan N puntos" prometería una subida que no
                     llega por muchas repeticiones que se hagan. */
                  <p style={{ margin: 0 }}>
                    {tierLabel(detail.next_tier)} no se alcanza con lo que entrenas
                    ahora: hace falta un ejercicio más exigente para este músculo.
                  </p>
                )}
              </div>
            )}
            {m.notes.length > 0 && !(detail.next_tier && !m.next_mark) && (
              <div className="stack" style={{ marginTop: 10, gap: 6 }}>
                {m.notes.map((note) => (
                  <p className="tiny muted" key={note} style={{ margin: 0 }}>
                    {note}
                  </p>
                ))}
              </div>
            )}
          </>
        ) : (
          <div className="stack" style={{ marginTop: 12 }}>
            {m.notes.map((note) => (
              <p className="muted" key={note} style={{ margin: 0 }}>
                {note}
              </p>
            ))}
          </div>
        )}
      </div>

      {Object.keys(detail.factors).length > 0 && (
        <div className="card">
          <h3>De dónde sale</h3>
          <dl className="factors">
            {Object.entries(detail.factors).map(([key, value]) => (
              <div key={key}>
                <dt>{key.replace(/_/g, " ")}</dt>
                <dd>{value}</dd>
              </div>
            ))}
          </dl>
        </div>
      )}

      {detail.recent && detail.quarter && (
        <div className="card">
          <h3>Volumen</h3>
          <div className="metric-row">
            <div className="metric">
              <span className="metric-value">{Math.round(detail.recent.volume_kg)}</span>
              <span className="faint">kg · 28 días</span>
            </div>
            <div className="metric">
              <span className="metric-value">{detail.recent.sessions_per_week}</span>
              <span className="faint">sesiones/semana</span>
            </div>
          </div>
          <p className="tiny muted" style={{ margin: "10px 0 0" }}>
            En 90 días: {Math.round(detail.quarter.volume_kg)} kg en {detail.quarter.sessions}{" "}
            sesiones.
          </p>
        </div>
      )}

      {detail.exercises.length > 0 && (
        <div className="card card-flush">
          <h3>Ejercicios que lo trabajan</h3>
          {detail.exercises.map((exercise) => (
            <div className="exercise" key={exercise.exercise_slug}>
              <div className="exercise-head">
                <span className="exercise-name">{exercise.exercise_name}</span>
                <span className="prescription">
                  {exercise.best_mark
                    ? `${exercise.best_mark} ${marcaUnidad(exercise.exercise_slug)}`
                    : "—"}
                </span>
              </div>
              <span className="faint tiny">
                {exercise.role} · {Math.round(exercise.volume_kg)} kg de volumen
                {exercise.last_date && ` · ${formatDate(exercise.last_date)}`}
              </span>
            </div>
          ))}
        </div>
      )}

      <div className="card">
        <h3>Evolución</h3>
        <Sparkline points={detail.history.map((p) => p.development)} />
        <p className="tiny muted" style={{ margin: "10px 0 0" }}>
          {detail.history.length < 2
            ? "El histórico se guarda una vez por semana: con el tiempo aparecerá aquí la curva."
            : `${detail.history.length} puntos, del ${detail.history[0]?.date} al ${
                detail.history[detail.history.length - 1]?.date
              }.`}
        </p>
      </div>
    </div>
  );
}

/** Línea del histórico. Sin ejes: es una forma, no una lectura precisa. */
function Sparkline({ points }: { points: number[] }) {
  if (points.length < 2) {
    return <div className="sparkline empty" aria-hidden="true" />;
  }
  const max = Math.max(...points, 1);
  const step = 100 / (points.length - 1);
  const d = points
    .map((value, i) => `${i === 0 ? "M" : "L"}${(i * step).toFixed(1)} ${(30 - (value / max) * 28).toFixed(1)}`)
    .join(" ");

  return (
    <svg className="sparkline" viewBox="0 0 100 30" role="img" aria-label="Evolución del desarrollo">
      <path d={d} />
    </svg>
  );
}
