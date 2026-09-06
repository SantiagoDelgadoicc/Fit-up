-- =============================================================================
-- Fit-Up · Migración 0001 — Esquema inicial
--
-- Convenciones:
--   · Las fechas de "día de entrenamiento" son TEXT con fecha local ISO
--     (YYYY-MM-DD). Nunca UTC: el día es un concepto local (regla A8).
--   · Los instantes de auditoría (created_at, logged_at, ts) son TEXT ISO-8601
--     con offset, porque ahí sí interesa el momento exacto.
--   · Los booleanos son INTEGER 0/1 (SQLite no tiene BOOLEAN).
--   · No se almacena nada derivable (regla R15). Única excepción justificada:
--     muscle_score_snapshot, caché reconstruible marcada con formula_version.
-- =============================================================================


-- =============================================================================
-- CATÁLOGO — datos permanentes
-- =============================================================================

CREATE TABLE muscle_group (
    id            INTEGER PRIMARY KEY,
    slug          TEXT    NOT NULL UNIQUE,
    name          TEXT    NOT NULL,
    region        TEXT    NOT NULL CHECK (region IN (
                      'torso_anterior', 'torso_posterior', 'brazos', 'piernas', 'core')),
    body_view     TEXT    NOT NULL CHECK (body_view IN ('frontal', 'dorsal', 'ambas')),
    svg_key       TEXT    NOT NULL UNIQUE,
    display_order INTEGER NOT NULL DEFAULT 0
);


CREATE TABLE progression_rule (
    id          INTEGER PRIMARY KEY,
    slug        TEXT    NOT NULL UNIQUE,
    name        TEXT    NOT NULL,
    strategy    TEXT    NOT NULL CHECK (strategy IN (
                    'reps_lineal', 'doble_progresion', 'peso_lineal',
                    'series', 'tiempo', 'variante', 'manual')),
    -- Parámetros de la estrategia (rep_min, rep_max, incremento…). El dominio
    -- valida su forma; la BD solo garantiza que sea un objeto JSON.
    params_json TEXT    NOT NULL DEFAULT '{}',
    -- Guardas de seguridad (max_incremento_semanal_pct, cooldown_dias, techos…).
    guards_json TEXT    NOT NULL DEFAULT '{}',
    is_builtin  INTEGER NOT NULL DEFAULT 0 CHECK (is_builtin IN (0, 1))
);


CREATE TABLE exercise (
    id                   INTEGER PRIMARY KEY,
    slug                 TEXT    NOT NULL UNIQUE,
    name                 TEXT    NOT NULL,
    modality             TEXT    NOT NULL CHECK (modality IN ('reps', 'tiempo', 'distancia')),
    load_type            TEXT    NOT NULL CHECK (load_type IN (
                             'externa', 'corporal', 'asistida', 'ninguna')),
    -- Fracción del peso corporal movilizada. Aproximación documentada y
    -- editable, no una verdad física (ADR-0003). 0 para carga puramente externa.
    load_factor          REAL    NOT NULL DEFAULT 0.0
                             CHECK (load_factor >= 0.0 AND load_factor <= 2.0),
    is_unilateral        INTEGER NOT NULL DEFAULT 0 CHECK (is_unilateral IN (0, 1)),
    equipment            TEXT,
    default_rule_id      INTEGER REFERENCES progression_rule(id) ON DELETE SET NULL,
    -- Siguiente eslabón de la cadena de variantes (estrategia 'variante').
    next_variant_id      INTEGER REFERENCES exercise(id) ON DELETE SET NULL,
    default_rest_seconds INTEGER NOT NULL DEFAULT 90 CHECK (default_rest_seconds >= 0),
    notes                TEXT,
    is_custom            INTEGER NOT NULL DEFAULT 0 CHECK (is_custom IN (0, 1)),
    is_active            INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    CHECK (next_variant_id IS NULL OR next_variant_id <> id)
);

CREATE INDEX ix_exercise_active ON exercise(is_active);


-- El factor numérico de cada rol (primario 1.0 / secundario 0.5 /
-- estabilizador 0.2) NO se almacena: es derivable del rol vía configuración
-- (regla R15). Guardarlo por fila impediría reajustar la fórmula.
CREATE TABLE exercise_muscle (
    exercise_id INTEGER NOT NULL REFERENCES exercise(id) ON DELETE CASCADE,
    muscle_id   INTEGER NOT NULL REFERENCES muscle_group(id) ON DELETE CASCADE,
    role        TEXT    NOT NULL CHECK (role IN ('primario', 'secundario', 'estabilizador')),
    PRIMARY KEY (exercise_id, muscle_id)
);

CREATE INDEX ix_exercise_muscle_muscle ON exercise_muscle(muscle_id);


CREATE TABLE settings (
    key        TEXT NOT NULL PRIMARY KEY,
    value_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);


CREATE TABLE bodyweight_log (
    date      TEXT NOT NULL PRIMARY KEY,   -- fecha local ISO
    weight_kg REAL NOT NULL CHECK (weight_kg > 0 AND weight_kg < 500)
);


-- =============================================================================
-- PLANIFICADO — lo que pretendo hacer
-- =============================================================================

CREATE TABLE routine (
    id         INTEGER PRIMARY KEY,
    name       TEXT    NOT NULL,
    status     TEXT    NOT NULL DEFAULT 'active'
                   CHECK (status IN ('draft', 'active', 'archived')),
    created_at TEXT    NOT NULL
);


-- Versiones inmutables (regla R1). Editar una rutina NUNCA muta filas
-- existentes: crea version_no + 1. El historial pasado queda intacto.
CREATE TABLE routine_version (
    id         INTEGER PRIMARY KEY,
    routine_id INTEGER NOT NULL REFERENCES routine(id) ON DELETE CASCADE,
    version_no INTEGER NOT NULL CHECK (version_no >= 1),
    created_at TEXT    NOT NULL,
    note       TEXT,
    actor      TEXT    NOT NULL DEFAULT 'usuario'
                   CHECK (actor IN ('usuario', 'agente', 'sistema')),
    UNIQUE (routine_id, version_no)
);

CREATE INDEX ix_routine_version_routine ON routine_version(routine_id, version_no DESC);


CREATE TABLE routine_exercise (
    id                 INTEGER PRIMARY KEY,
    routine_version_id INTEGER NOT NULL REFERENCES routine_version(id) ON DELETE CASCADE,
    exercise_id        INTEGER NOT NULL REFERENCES exercise(id),
    position           INTEGER NOT NULL CHECK (position >= 0),
    rest_seconds       INTEGER CHECK (rest_seconds IS NULL OR rest_seconds >= 0),
    rule_id            INTEGER REFERENCES progression_rule(id) ON DELETE SET NULL,
    notes              TEXT,
    UNIQUE (routine_version_id, position)
);


-- Series explícitas: 3x15 son 3 filas (decisión d7). Permite pirámides y
-- drop sets, y da una única forma de comparar planificado vs realizado.
CREATE TABLE planned_set (
    id                  INTEGER PRIMARY KEY,
    routine_exercise_id INTEGER NOT NULL REFERENCES routine_exercise(id) ON DELETE CASCADE,
    set_no              INTEGER NOT NULL CHECK (set_no >= 1),
    target_reps         INTEGER CHECK (target_reps IS NULL OR target_reps > 0),
    target_reps_max     INTEGER CHECK (target_reps_max IS NULL OR target_reps_max > 0),
    target_weight_kg    REAL    CHECK (target_weight_kg IS NULL OR target_weight_kg >= 0),
    target_time_s       INTEGER CHECK (target_time_s IS NULL OR target_time_s > 0),
    target_rir          INTEGER CHECK (target_rir IS NULL OR (target_rir BETWEEN 0 AND 10)),
    is_warmup           INTEGER NOT NULL DEFAULT 0 CHECK (is_warmup IN (0, 1)),
    UNIQUE (routine_exercise_id, set_no),
    CHECK (target_reps IS NOT NULL OR target_time_s IS NOT NULL),
    CHECK (target_reps_max IS NULL OR target_reps IS NULL OR target_reps_max >= target_reps)
);


-- weekday: 0 = lunes … 6 = domingo. La vigencia (active_from/active_to)
-- permite cambiar la planificación sin reescribir el pasado (regla R3).
CREATE TABLE schedule_slot (
    id          INTEGER PRIMARY KEY,
    weekday     INTEGER NOT NULL CHECK (weekday BETWEEN 0 AND 6),
    routine_id  INTEGER NOT NULL REFERENCES routine(id) ON DELETE CASCADE,
    active_from TEXT    NOT NULL,
    active_to   TEXT,
    CHECK (active_to IS NULL OR active_to >= active_from)
);

CREATE INDEX ix_schedule_slot_weekday ON schedule_slot(weekday, active_from);


-- Un día excusado (descanso, lesión, viaje) no es un incumplimiento (regla R4).
CREATE TABLE schedule_exception (
    date       TEXT NOT NULL PRIMARY KEY,   -- fecha local ISO
    routine_id INTEGER REFERENCES routine(id) ON DELETE SET NULL,
    reason     TEXT NOT NULL CHECK (reason IN (
                   'descanso', 'lesion', 'viaje', 'movido', 'otro')),
    note       TEXT
);


-- =============================================================================
-- HISTÓRICO — lo que realmente hice
-- =============================================================================

CREATE TABLE workout_session (
    id                 INTEGER PRIMARY KEY,
    date               TEXT    NOT NULL,          -- fecha local ISO del entrenamiento
    routine_version_id INTEGER REFERENCES routine_version(id),
    origin             TEXT    NOT NULL CHECK (origin IN ('planificada', 'adhoc')),
    status             TEXT    NOT NULL CHECK (status IN ('completed', 'partial', 'skipped')),
    perceived_effort   INTEGER CHECK (perceived_effort IS NULL
                                      OR perceived_effort BETWEEN 1 AND 10),
    duration_min       INTEGER CHECK (duration_min IS NULL OR duration_min > 0),
    notes              TEXT,
    -- Instante del registro. Comparado con `date` revela si fue retroactivo
    -- y permite auditar la calidad del dato (regla R9).
    logged_at          TEXT    NOT NULL,
    actor              TEXT    NOT NULL DEFAULT 'usuario'
                           CHECK (actor IN ('usuario', 'agente', 'sistema')),
    -- Evita que un agente que reintenta duplique la sesión (ADR-0004).
    idempotency_key    TEXT UNIQUE,
    CHECK (origin = 'adhoc' OR routine_version_id IS NOT NULL)
);

CREATE INDEX ix_session_date ON workout_session(date DESC);


CREATE TABLE session_exercise (
    id             INTEGER PRIMARY KEY,
    session_id     INTEGER NOT NULL REFERENCES workout_session(id) ON DELETE CASCADE,
    exercise_id    INTEGER NOT NULL REFERENCES exercise(id),
    position       INTEGER NOT NULL CHECK (position >= 0),
    -- Enlace al ejercicio planificado del que proviene, si lo hubo.
    planned_ref_id INTEGER REFERENCES routine_exercise(id) ON DELETE SET NULL,
    notes          TEXT,
    UNIQUE (session_id, position)
);

CREATE INDEX ix_session_exercise_exercise ON session_exercise(exercise_id);


CREATE TABLE session_set (
    id                  INTEGER PRIMARY KEY,
    session_exercise_id INTEGER NOT NULL REFERENCES session_exercise(id) ON DELETE CASCADE,
    set_no              INTEGER NOT NULL CHECK (set_no >= 1),
    reps                INTEGER CHECK (reps IS NULL OR reps >= 0),
    weight_kg           REAL    CHECK (weight_kg IS NULL OR weight_kg >= 0),
    time_s              INTEGER CHECK (time_s IS NULL OR time_s >= 0),
    rir                 INTEGER CHECK (rir IS NULL OR (rir BETWEEN 0 AND 10)),
    completed           INTEGER NOT NULL DEFAULT 1 CHECK (completed IN (0, 1)),
    is_warmup           INTEGER NOT NULL DEFAULT 0 CHECK (is_warmup IN (0, 1)),
    UNIQUE (session_exercise_id, set_no)
);


-- Traza auditable y reversible de cada sobrecarga aplicada (regla R14).
CREATE TABLE progression_event (
    id                   INTEGER PRIMARY KEY,
    exercise_id          INTEGER NOT NULL REFERENCES exercise(id),
    routine_id           INTEGER NOT NULL REFERENCES routine(id) ON DELETE CASCADE,
    from_version_id      INTEGER REFERENCES routine_version(id),
    to_version_id        INTEGER NOT NULL REFERENCES routine_version(id),
    rule_slug            TEXT    NOT NULL,
    before_json          TEXT    NOT NULL,
    after_json           TEXT    NOT NULL,
    rationale            TEXT    NOT NULL,   -- justificación legible por humanos
    applied_at           TEXT    NOT NULL,
    actor                TEXT    NOT NULL
                             CHECK (actor IN ('usuario', 'agente', 'sistema')),
    -- Deshacer = nuevo evento que revierte. Nunca se borra historia.
    reverted_by_event_id INTEGER REFERENCES progression_event(id) ON DELETE SET NULL
);

CREATE INDEX ix_progression_event_exercise ON progression_event(exercise_id, applied_at DESC);


CREATE TABLE audit_log (
    id           INTEGER PRIMARY KEY,
    ts           TEXT    NOT NULL,
    actor        TEXT    NOT NULL CHECK (actor IN ('usuario', 'agente', 'sistema')),
    action       TEXT    NOT NULL,
    payload_json TEXT,
    result       TEXT    NOT NULL CHECK (result IN ('ok', 'error', 'rechazado')),
    error        TEXT
);

CREATE INDEX ix_audit_log_ts ON audit_log(ts DESC);


-- =============================================================================
-- DERIVADO — caché reconstruible
--
-- Única excepción a la regla R15. Se guarda para poder graficar la evolución
-- histórica del rango; puede borrarse y recalcularse íntegramente desde el
-- registro crudo. `formula_version` permite que convivan varias versiones.
-- =============================================================================

CREATE TABLE muscle_score_snapshot (
    date              TEXT    NOT NULL,   -- fecha local ISO
    muscle_id         INTEGER NOT NULL REFERENCES muscle_group(id) ON DELETE CASCADE,
    formula_version   TEXT    NOT NULL,
    development_score REAL    NOT NULL,
    activity_score    REAL    NOT NULL,
    tier              TEXT    NOT NULL CHECK (tier IN (
                          'sin_datos', 'iron', 'bronze', 'silver', 'gold',
                          'platinum', 'diamond', 'ascendant', 'immortal', 'radiant')),
    -- Desglose de los factores que produjeron el score, para explicabilidad.
    inputs_json       TEXT    NOT NULL,
    computed_at       TEXT    NOT NULL,
    PRIMARY KEY (date, muscle_id, formula_version)
);
