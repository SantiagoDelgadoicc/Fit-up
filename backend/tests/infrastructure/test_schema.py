"""Migraciones, esquema y catálogo semilla."""

from __future__ import annotations

import sqlite3

import pytest

from fitup.infrastructure.db import migrator
from fitup.infrastructure.db.connection import connect, connect_memory, integrity_ok
from fitup.infrastructure.seed import catalog


@pytest.fixture
def db() -> sqlite3.Connection:
    conn = connect_memory()
    migrator.migrate(conn)
    yield conn
    conn.close()


@pytest.fixture
def seeded(db: sqlite3.Connection) -> sqlite3.Connection:
    catalog.seed(db)
    return db


# --------------------------------------------------------------------------
# Migraciones
# --------------------------------------------------------------------------


def test_las_migraciones_se_aplican_y_dejan_constancia(db):
    assert migrator.current_version(db) >= 1
    rows = db.execute("SELECT version, name FROM schema_migration").fetchall()
    assert rows[0]["name"] == "initial"


def test_migrar_dos_veces_no_hace_nada(db):
    assert migrator.migrate(db) == []


def test_editar_una_migracion_ya_aplicada_falla_ruidosamente(db, tmp_path):
    """Dejar la BD en un estado que el código no describe es peor que fallar."""
    (tmp_path / "0001_initial.sql").write_text("SELECT 1;", encoding="utf-8")
    with pytest.raises(migrator.MigrationError, match="cambió"):
        migrator.migrate(db, tmp_path)


def test_nombre_de_migracion_invalido_es_error(tmp_path):
    (tmp_path / "inicial.sql").write_text("SELECT 1;", encoding="utf-8")
    with pytest.raises(migrator.MigrationError, match="NNNN_nombre"):
        migrator.discover(tmp_path)


def test_las_migraciones_se_ordenan_por_version():
    versions = [m.version for m in migrator.discover()]
    assert versions == sorted(versions)


# --------------------------------------------------------------------------
# Garantías del esquema
# --------------------------------------------------------------------------


def test_las_claves_foraneas_estan_activas(db):
    """Sin el PRAGMA, SQLite ignora en silencio las FK declaradas."""
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO exercise_muscle (exercise_id, muscle_id, role) "
            "VALUES (999, 999, 'primario')"
        )


def test_el_esquema_rechaza_valores_fuera_de_dominio(seeded):
    with pytest.raises(sqlite3.IntegrityError):
        seeded.execute(
            "INSERT INTO exercise (slug, name, modality, load_type) "
            "VALUES ('x', 'X', 'inventada', 'externa')"
        )


def test_no_se_permiten_dos_versiones_iguales_de_una_rutina(seeded):
    seeded.execute("INSERT INTO routine (name, created_at) VALUES ('Push', '2026-01-01')")
    rid = seeded.execute("SELECT id FROM routine").fetchone()["id"]
    seeded.execute(
        "INSERT INTO routine_version (routine_id, version_no, created_at) VALUES (?, 1, ?)",
        (rid, "2026-01-01"),
    )
    with pytest.raises(sqlite3.IntegrityError):
        seeded.execute(
            "INSERT INTO routine_version (routine_id, version_no, created_at) VALUES (?, 1, ?)",
            (rid, "2026-01-02"),
        )


def test_una_serie_planificada_necesita_repeticiones_o_tiempo(seeded):
    seeded.execute("INSERT INTO routine (name, created_at) VALUES ('R', '2026-01-01')")
    seeded.execute(
        "INSERT INTO routine_version (routine_id, version_no, created_at) VALUES (1, 1, '2026-01-01')"
    )
    seeded.execute(
        "INSERT INTO routine_exercise (routine_version_id, exercise_id, position) VALUES (1, 1, 0)"
    )
    with pytest.raises(sqlite3.IntegrityError):
        seeded.execute("INSERT INTO planned_set (routine_exercise_id, set_no) VALUES (1, 1)")


def test_una_sesion_planificada_exige_version_de_rutina(seeded):
    """El histórico apunta siempre a la versión concreta que se ejecutó (R2)."""
    with pytest.raises(sqlite3.IntegrityError):
        seeded.execute(
            "INSERT INTO workout_session (date, origin, status, logged_at) "
            "VALUES ('2026-01-01', 'planificada', 'completed', '2026-01-01T10:00:00')"
        )


def test_la_clave_de_idempotencia_impide_duplicar_una_sesion(seeded):
    """Un agente que reintenta no debe crear dos entrenamientos (ADR-0004)."""
    sql = (
        "INSERT INTO workout_session (date, origin, status, logged_at, idempotency_key) "
        "VALUES ('2026-01-01', 'adhoc', 'completed', '2026-01-01T10:00:00', 'abc')"
    )
    seeded.execute(sql)
    with pytest.raises(sqlite3.IntegrityError):
        seeded.execute(sql)


def test_integridad_de_una_base_recien_creada(tmp_path):
    conn = connect(tmp_path / "fitup.db")
    migrator.migrate(conn)
    assert integrity_ok(conn)
    conn.close()


# --------------------------------------------------------------------------
# Catálogo semilla
# --------------------------------------------------------------------------


def test_el_catalogo_es_coherente():
    catalog.validate()


def test_la_siembra_puebla_el_catalogo(seeded):
    muscles = seeded.execute("SELECT COUNT(*) c FROM muscle_group").fetchone()["c"]
    exercises = seeded.execute("SELECT COUNT(*) c FROM exercise").fetchone()["c"]
    rules = seeded.execute("SELECT COUNT(*) c FROM progression_rule").fetchone()["c"]
    assert muscles >= 15
    assert exercises >= 50
    assert rules >= 8


def test_sembrar_dos_veces_no_duplica_nada(seeded):
    before = seeded.execute("SELECT COUNT(*) c FROM exercise").fetchone()["c"]
    report = catalog.seed(seeded)
    after = seeded.execute("SELECT COUNT(*) c FROM exercise").fetchone()["c"]
    assert before == after
    assert report.total == 0


def test_las_cadenas_de_variantes_quedan_enlazadas(seeded):
    row = seeded.execute(
        "SELECT v.slug AS siguiente FROM exercise e "
        "JOIN exercise e2 ON e2.id = e.next_variant_id "
        "JOIN exercise v ON v.id = e2.id WHERE e.slug = 'flexiones'"
    ).fetchone()
    assert row["siguiente"] == "flexiones_declinadas"


def test_todo_ejercicio_tiene_al_menos_un_musculo_primario(seeded):
    huerfanos = seeded.execute(
        "SELECT e.slug FROM exercise e "
        "WHERE e.load_type <> 'ninguna' AND NOT EXISTS ("
        "  SELECT 1 FROM exercise_muscle em "
        "  WHERE em.exercise_id = e.id AND em.role = 'primario')"
    ).fetchall()
    assert [r["slug"] for r in huerfanos] == []


def test_todo_musculo_del_mapa_tiene_algun_ejercicio(seeded):
    """Un músculo sin ejercicios saldría siempre 'sin datos' en el ranking."""
    huerfanos = seeded.execute(
        "SELECT m.slug FROM muscle_group m "
        "WHERE NOT EXISTS (SELECT 1 FROM exercise_muscle em WHERE em.muscle_id = m.id)"
    ).fetchall()
    assert [r["slug"] for r in huerfanos] == []


def test_todo_ejercicio_del_catalogo_tiene_escalera_de_rango(seeded):
    """Sin escalera propia un ejercicio cae en la genérica.

    Funciona, pero su rango deja de ser comparable con el de los demás, y eso
    es justo lo que el mapa corporal invita a hacer de un vistazo. Por eso la
    genérica se declara provisional y no puede dar rango alto: un ejercicio
    sin calibrar debe quedarse corto, nunca regalar Radiant.
    """
    from fitup.domain.enums import Tier
    from fitup.domain.ranking.standards import STANDARDS, standard_for

    slugs = {r["slug"] for r in seeded.execute("SELECT slug FROM exercise").fetchall()}
    assert set(STANDARDS) <= slugs, "hay escaleras de ejercicios que no existen"

    for slug in slugs:
        escalera = standard_for(slug)
        if slug not in STANDARDS:
            assert escalera.provisional
            assert escalera.max_tier is not Tier.RADIANT


def test_las_reglas_de_sobrecarga_del_catalogo_existen(seeded):
    """Un `default_rule` que apunte a una regla inexistente dejaría el ejercicio
    sin progresión y sin decir por qué."""
    reglas = {r["slug"] for r in seeded.execute("SELECT slug FROM progression_rule").fetchall()}
    huerfanos = seeded.execute(
        "SELECT e.slug FROM exercise e WHERE e.default_rule_id IS NULL AND e.is_custom = 0"
    ).fetchall()
    assert [r["slug"] for r in huerfanos] == []
    assert "reps_hasta_150" in reglas


def test_los_ejercicios_de_peso_corporal_declaran_load_factor(seeded):
    faltan = seeded.execute(
        "SELECT slug FROM exercise WHERE load_type = 'corporal' AND load_factor <= 0"
    ).fetchall()
    assert [r["slug"] for r in faltan] == []


def test_los_ajustes_por_defecto_quedan_sembrados(seeded):
    keys = {r["key"] for r in seeded.execute("SELECT key FROM settings").fetchall()}
    assert {"unidades", "dias_gracia", "ranking_formula_version"} <= keys


# --------------------------------------------------------------------------
# Validación del catálogo
# --------------------------------------------------------------------------


def write_catalog(tmp_path, *, muscles=None, rules=None, exercises=None):
    import json

    (tmp_path / "muscles.json").write_text(
        json.dumps(
            muscles
            if muscles is not None
            else [
                {
                    "slug": "pectoral",
                    "name": "P",
                    "region": "torso_anterior",
                    "body_view": "frontal",
                    "svg_key": "chest",
                }
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "progression_rules.json").write_text(
        json.dumps(
            rules if rules is not None else [{"slug": "r", "name": "R", "strategy": "manual"}]
        ),
        encoding="utf-8",
    )
    (tmp_path / "exercises.json").write_text(
        json.dumps(exercises if exercises is not None else []),
        encoding="utf-8",
    )
    return tmp_path


def test_un_slug_de_musculo_mal_escrito_falla_al_sembrar(tmp_path):
    """Debe romper aquí, no producir un ranking incompleto meses después."""
    write_catalog(
        tmp_path,
        exercises=[
            {
                "slug": "x",
                "name": "X",
                "modality": "reps",
                "load_type": "externa",
                "muscles": [["pectorel", "primario"]],
            }
        ],
    )
    with pytest.raises(catalog.SeedError, match="músculo inexistente"):
        catalog.validate(tmp_path)


def test_una_regla_inexistente_falla(tmp_path):
    write_catalog(
        tmp_path,
        exercises=[
            {
                "slug": "x",
                "name": "X",
                "modality": "reps",
                "load_type": "externa",
                "default_rule": "no_existe",
                "muscles": [["pectoral", "primario"]],
            }
        ],
    )
    with pytest.raises(catalog.SeedError, match="regla inexistente"):
        catalog.validate(tmp_path)


def test_una_cadena_de_variantes_circular_falla(tmp_path):
    """Colgaría la progresión por variante indefinidamente."""
    write_catalog(
        tmp_path,
        exercises=[
            {
                "slug": "a",
                "name": "A",
                "modality": "reps",
                "load_type": "externa",
                "next_variant": "b",
                "muscles": [["pectoral", "primario"]],
            },
            {
                "slug": "b",
                "name": "B",
                "modality": "reps",
                "load_type": "externa",
                "next_variant": "a",
                "muscles": [["pectoral", "primario"]],
            },
        ],
    )
    with pytest.raises(catalog.SeedError, match="circular"):
        catalog.validate(tmp_path)


def test_un_ejercicio_corporal_sin_load_factor_falla(tmp_path):
    write_catalog(
        tmp_path,
        exercises=[
            {
                "slug": "x",
                "name": "X",
                "modality": "reps",
                "load_type": "corporal",
                "muscles": [["pectoral", "primario"]],
            }
        ],
    )
    with pytest.raises(catalog.SeedError, match="load_factor"):
        catalog.validate(tmp_path)


def test_un_rol_invalido_falla(tmp_path):
    write_catalog(
        tmp_path,
        exercises=[
            {
                "slug": "x",
                "name": "X",
                "modality": "reps",
                "load_type": "externa",
                "muscles": [["pectoral", "principal"]],
            }
        ],
    )
    with pytest.raises(catalog.SeedError, match="rol inválido"):
        catalog.validate(tmp_path)
