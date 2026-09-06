"""Interfaz de línea de comandos.

Es el punto de entrada que se ejecuta de verdad: si `fitup init` falla, no hay
proyecto. Merece cobertura aunque sea un adaptador fino.
"""

from __future__ import annotations

import pytest

from fitup.cli import main


def test_init_crea_la_base_y_siembra_el_catalogo(tmp_path, capsys):
    db = tmp_path / "fitup.db"
    assert main(["--db", str(db), "init"]) == 0

    out = capsys.readouterr().out
    assert "0001_initial" in out
    assert "ejercicios" in out
    assert db.exists()


def test_init_es_idempotente(tmp_path, capsys):
    db = tmp_path / "fitup.db"
    main(["--db", str(db), "init"])
    capsys.readouterr()

    assert main(["--db", str(db), "init"]) == 0
    out = capsys.readouterr().out
    assert "esquema ya actualizado" in out
    assert "nada nuevo que sembrar" in out


def test_check_sobre_una_base_existente(tmp_path, capsys):
    db = tmp_path / "fitup.db"
    main(["--db", str(db), "init"])
    capsys.readouterr()

    assert main(["--db", str(db), "check"]) == 0
    out = capsys.readouterr().out
    assert "integridad: ok" in out
    assert "versión de esquema: 1" in out


def test_check_sin_base_de_datos_no_es_un_error(tmp_path, capsys):
    """Antes de `init` no hay nada roto: simplemente no existe todavía."""
    assert main(["--db", str(tmp_path / "no-existe.db"), "check"]) == 0
    assert "no existe todavía" in capsys.readouterr().out


def test_se_exige_un_subcomando():
    with pytest.raises(SystemExit):
        main([])
