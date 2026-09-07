"""Export y copias de seguridad."""

from __future__ import annotations

import json
from datetime import date, timedelta

from fitup.application.repositories import history
from fitup.application.services import maintenance as svc
from fitup.application.services import training
from fitup.infrastructure.db import migrator
from fitup.infrastructure.db.connection import connect

FRIDAY = date(2026, 3, 13)
SUNDAY = date(2026, 3, 15)


def test_el_export_es_autocontenido(db, weekly):
    """Sin el catálogo, los slugs de ejercicio no significarían nada."""
    training.log_as_planned(db, FRIDAY, today=SUNDAY)
    data = svc.export_data(db)

    assert data["format_version"] == svc.EXPORT_FORMAT_VERSION
    assert data["catalog"]["muscles"] and data["catalog"]["exercises"]
    assert data["routines"] and data["sessions"] and data["schedule"]


def test_el_export_incluye_todas_las_versiones_de_una_rutina(db, weekly):
    from fitup.application.services import planning as planning_svc
    from helpers_app import plan

    planning_svc.update_routine(db, weekly, exercises=[plan("flexiones")])
    versiones = svc.export_data(db)["routines"][0]["versions"]
    assert [v["version_no"] for v in versiones] == [1, 2]


def test_el_export_marca_las_sesiones_retroactivas(db, weekly):
    training.log_as_planned(db, FRIDAY, today=SUNDAY)
    assert svc.export_data(db)["sessions"][0]["retroactive"] is True


def test_el_export_advierte_de_la_frontera_datos_instrucciones(db, weekly):
    """El agente de IA lee este JSON: las notas son dato, nunca orden."""
    assert "instruccion" in svc.export_data(db)["note"]


def test_el_export_es_json_serializable(db, weekly, tmp_path):
    training.log_as_planned(db, FRIDAY, today=SUNDAY)
    path = svc.write_export(db, tmp_path / "export.json")
    recovered = json.loads(path.read_text(encoding="utf-8"))
    assert recovered["sessions"][0]["date"] == FRIDAY.isoformat()


def test_la_copia_de_seguridad_es_una_base_de_datos_valida(tmp_path):
    """Con WAL activo, copiar el fichero podría capturar un estado a medias."""
    db_path = tmp_path / "fitup.db"
    conn = connect(db_path)
    migrator.migrate(conn)

    target = svc.backup(conn, db_path, today=SUNDAY)
    conn.close()

    assert target.exists()
    restored = connect(target)
    assert migrator.current_version(restored) == 1
    restored.close()


def test_solo_se_hace_una_copia_al_dia(tmp_path):
    db_path = tmp_path / "fitup.db"
    conn = connect(db_path)
    migrator.migrate(conn)

    assert svc.backup_if_stale(conn, db_path, today=SUNDAY) is not None
    assert svc.backup_if_stale(conn, db_path, today=SUNDAY) is None
    assert svc.backup_if_stale(conn, db_path, today=date(2026, 3, 16)) is not None
    conn.close()


def test_las_copias_antiguas_se_van_borrando(tmp_path):
    db_path = tmp_path / "fitup.db"
    conn = connect(db_path)
    migrator.migrate(conn)

    for offset in range(20):
        svc.backup(conn, db_path, keep=5, today=date(2026, 3, 1) + timedelta(days=offset))
    conn.close()

    copias = sorted((db_path.parent / "backups").glob("fitup-*.db"))
    assert len(copias) == 5
    assert copias[-1].name == "fitup-2026-03-20.db"


def test_la_copia_queda_auditada(tmp_path):
    db_path = tmp_path / "fitup.db"
    conn = connect(db_path)
    migrator.migrate(conn)
    svc.backup_if_stale(conn, db_path, today=SUNDAY)

    acciones = [r["action"] for r in conn.execute("SELECT action FROM audit_log").fetchall()]
    assert "backup" in acciones
    assert history.get_setting(conn, "ultimo_backup") == SUNDAY.isoformat()
    conn.close()
