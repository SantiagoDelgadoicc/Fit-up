-- =============================================================================
-- 0002 · Series al fallo
--
-- Una serie "al fallo" no tiene objetivo de repeticiones: el objetivo es
-- llegar al fallo. Hasta ahora el esquema obligaba a poner un número, y
-- rellenarlo con una estimación sería inventar un dato — justo lo que el
-- proyecto no hace (invariante 5: si no se puede determinar, se dice).
--
-- El CHECK de `planned_set` exigía `target_reps` o `target_time_s`, así que
-- hay que recrear la tabla: SQLite no permite modificar un CHECK en sitio.
-- Se recrea con el mismo orden de columnas y los mismos índices, más la
-- columna nueva.
--
-- `session_set` no necesita cambio: lo realizado siempre tiene un número de
-- repeticiones concreto, que es precisamente el dato que interesa de una
-- serie al fallo.
-- =============================================================================

PRAGMA foreign_keys = OFF;

CREATE TABLE planned_set_nuevo (
    id                  INTEGER PRIMARY KEY,
    routine_exercise_id INTEGER NOT NULL REFERENCES routine_exercise(id) ON DELETE CASCADE,
    set_no              INTEGER NOT NULL CHECK (set_no >= 1),
    target_reps         INTEGER CHECK (target_reps IS NULL OR target_reps > 0),
    target_reps_max     INTEGER CHECK (target_reps_max IS NULL OR target_reps_max > 0),
    target_weight_kg    REAL    CHECK (target_weight_kg IS NULL OR target_weight_kg >= 0),
    target_time_s       INTEGER CHECK (target_time_s IS NULL OR target_time_s > 0),
    target_rir          INTEGER CHECK (target_rir IS NULL OR (target_rir BETWEEN 0 AND 10)),
    is_warmup           INTEGER NOT NULL DEFAULT 0 CHECK (is_warmup IN (0, 1)),
    -- Al fallo: sin objetivo numérico, se repite hasta no poder más.
    to_failure          INTEGER NOT NULL DEFAULT 0 CHECK (to_failure IN (0, 1)),
    UNIQUE (routine_exercise_id, set_no),
    -- Ahora hay tres formas válidas de prescribir una serie: repeticiones,
    -- tiempo, o al fallo. Lo que sigue prohibido es no decir ninguna.
    CHECK (target_reps IS NOT NULL OR target_time_s IS NOT NULL OR to_failure = 1),
    CHECK (target_reps_max IS NULL OR target_reps IS NULL OR target_reps_max >= target_reps),
    -- Una serie al fallo con objetivo de repeticiones sería una contradicción:
    -- o llegas al fallo, o llegas al número.
    CHECK (to_failure = 0 OR target_reps IS NULL)
);

INSERT INTO planned_set_nuevo (
    id, routine_exercise_id, set_no, target_reps, target_reps_max,
    target_weight_kg, target_time_s, target_rir, is_warmup
)
SELECT
    id, routine_exercise_id, set_no, target_reps, target_reps_max,
    target_weight_kg, target_time_s, target_rir, is_warmup
FROM planned_set;

DROP TABLE planned_set;

ALTER TABLE planned_set_nuevo RENAME TO planned_set;

PRAGMA foreign_keys = ON;
