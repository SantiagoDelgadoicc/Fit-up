"""Interfaz de línea de comandos.

En F0 solo cubre lo necesario para crear y verificar la base de datos. Crece
con el proyecto; no se adelanta a él.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .infrastructure.db import connection, migrator
from .infrastructure.seed import catalog

DEFAULT_DB = Path("data/fitup.db")


def cmd_init(args: argparse.Namespace) -> int:
    """Crea la base de datos, aplica migraciones y siembra el catálogo."""
    conn = connection.connect(args.db)
    try:
        applied = migrator.migrate(conn)
        if applied:
            for m in applied:
                print(f"  migración aplicada: {m.version:04d}_{m.name}")
        else:
            print("  esquema ya actualizado")

        report = catalog.seed(conn)
        print(
            f"  catálogo: {report.muscles} músculos, {report.rules} reglas, "
            f"{report.exercises} ejercicios, {report.links} vínculos, "
            f"{report.settings} ajustes"
        )
        if report.total == 0:
            print("  (nada nuevo que sembrar)")
        print(f"OK · {args.db} en versión {migrator.current_version(conn)}")
        return 0
    finally:
        conn.close()


def cmd_check(args: argparse.Namespace) -> int:
    """Verifica integridad, versión de esquema y coherencia del catálogo."""
    catalog.validate()
    print("  catálogo semilla: coherente")

    path = Path(args.db)
    if not path.exists():
        print(f"  base de datos: no existe todavía ({path})")
        return 0

    conn = connection.connect(path)
    try:
        ok = connection.integrity_ok(conn)
        print(f"  integridad: {'ok' if ok else 'CORRUPTA'}")
        print(f"  versión de esquema: {migrator.current_version(conn)}")
        pending = [
            m for m in migrator.discover() if m.version not in migrator.applied_versions(conn)
        ]
        if pending:
            print(f"  migraciones pendientes: {len(pending)}")
        return 0 if ok else 1
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fitup", description="Fit-Up")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="ruta de la base de datos")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="crear/actualizar la base de datos y sembrar el catálogo")
    sub.add_parser("check", help="verificar integridad y coherencia")

    args = parser.parse_args(argv)
    handler = {"init": cmd_init, "check": cmd_check}[args.command]
    return handler(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
