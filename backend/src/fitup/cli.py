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


def cmd_export(args: argparse.Namespace) -> int:
    """Vuelca todo a JSON: copia legible y entrada para el agente de IA."""
    from .application.services import maintenance

    conn = connection.connect(args.db)
    try:
        path = maintenance.write_export(conn, Path(args.salida))
        print(f"OK · export en {path}")
        return 0
    finally:
        conn.close()


def cmd_serve(args: argparse.Namespace) -> int:  # pragma: no cover - arranca el servidor
    """Levanta la API y la PWA."""
    from .api.app import serve
    from .api.deps import ensure_token

    db_path = Path(args.db)
    # Con --lan la app queda expuesta en la red doméstica y el token deja de
    # ser opcional: ahí sí es una frontera real frente a otros dispositivos.
    host = "0.0.0.0" if args.lan else "127.0.0.1"  # noqa: S104
    token = ensure_token(db_path.parent / "config") if args.lan else None

    print(f"  base de datos: {db_path}")
    print(f"  escuchando en: http://{host}:{args.puerto}")
    if token:
        print(f"  token de acceso: {token}")
        print("  (guardado en data/config/token; necesario desde el móvil)")
    else:
        print("  solo accesible desde este equipo; usa --lan para el móvil")

    serve(db_path=db_path, host=host, port=args.puerto, token=token, require_token=bool(token))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fitup", description="Fit-Up")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="ruta de la base de datos")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="crear/actualizar la base de datos y sembrar el catálogo")
    sub.add_parser("check", help="verificar integridad y coherencia")

    export = sub.add_parser("export", help="volcar todos los datos a un JSON")
    export.add_argument("--salida", default="data/export.json", help="fichero de destino")

    serve_cmd = sub.add_parser("serve", help="levantar la API y la interfaz")
    serve_cmd.add_argument("--puerto", type=int, default=8000)
    serve_cmd.add_argument(
        "--lan",
        action="store_true",
        help="exponer en la red local para usar desde el móvil (genera token)",
    )

    args = parser.parse_args(argv)
    handler = {
        "init": cmd_init,
        "check": cmd_check,
        "export": cmd_export,
        "serve": cmd_serve,
    }[args.command]
    return handler(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
