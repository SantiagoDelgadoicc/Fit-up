"""Interfaz de línea de comandos.

Crece con el proyecto; no se adelanta a él. Hoy cubre preparar la base de
datos, verificarla, exportar y levantar el servidor.
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


def cmd_reglas(args: argparse.Namespace) -> int:
    """Repunta las rutinas a la regla de sobrecarga que declara el catálogo.

    Existe porque la regla se copia dentro de la versión de rutina cuando se
    crea: recalibrar el catálogo no alcanza a lo ya planificado. Y como una
    versión ya ejecutada no se muta (regla R2), reasignar significa **crear una
    versión nueva**, que es exactamente lo que hace esto —auditado y con la
    anterior intacta—. Sin `--aplicar` solo enseña lo que cambiaría.
    """
    from .application.repositories import catalog as catalog_repo
    from .application.services import planning

    conn = connection.connect(args.db)
    try:
        defaults = {e.slug: e.default_rule_slug for e in catalog_repo.list_exercises(conn)}
        total = 0
        for summary in planning.list_routines(conn):
            detail = planning.get_routine(conn, summary.id)
            cambios = [
                (e.exercise_slug, e.rule_slug, defaults.get(e.exercise_slug))
                for e in detail.exercises
                if defaults.get(e.exercise_slug) and e.rule_slug != defaults.get(e.exercise_slug)
            ]
            if not cambios:
                continue
            print(f"  {detail.name} (v{detail.version_no}):")
            for slug, antes, despues in cambios:
                # Sin flechas ni guiones largos: la consola de Windows va en
                # cp1252 y un UnicodeEncodeError aqui tumbaria el comando.
                print(f"    {slug:28} {antes or 'sin regla'} -> {despues}")
            total += len(cambios)

            if args.aplicar:
                from dataclasses import replace

                planning.update_routine(
                    conn,
                    summary.id,
                    exercises=[
                        replace(e, rule_slug=defaults.get(e.exercise_slug) or e.rule_slug)
                        for e in detail.exercises
                    ],
                    note="Reglas de sobrecarga alineadas con las escaleras de rango",
                )

        if total == 0:
            print("  todas las rutinas ya usan la regla del catálogo")
        elif args.aplicar:
            print(f"OK · {total} ejercicio(s) repuntado(s), en versiones nuevas")
        else:
            print(f"  {total} ejercicio(s) cambiarían. Repite con --aplicar para hacerlo")
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


def _abrir_cuando_responda(url: str, intentos: int = 60) -> None:  # pragma: no cover
    """Abre el navegador en cuanto el servidor conteste.

    Se sondea en vez de esperar un tiempo fijo: el primer arranque aplica
    migraciones y siembra el catálogo, y una espera a ojo se queda corta justo
    la primera vez, que es cuando peor sienta.
    """
    import http.client
    import time
    import urllib.parse
    import webbrowser

    partes = urllib.parse.urlsplit(url)
    for _ in range(intentos):
        try:
            conexion = http.client.HTTPConnection(partes.netloc, timeout=0.5)
            conexion.request("GET", "/api/salud")
            respuesta = conexion.getresponse()
            conexion.close()
            if respuesta.status < 500:
                webbrowser.open(url)
                return
        except OSError:
            pass
        time.sleep(0.5)


def cmd_serve(args: argparse.Namespace) -> int:  # pragma: no cover - arranca el servidor
    """Levanta la API y la PWA."""
    import threading

    from .api.app import serve
    from .api.deps import ensure_token

    db_path = Path(args.db)
    # Con --lan la app queda expuesta en la red doméstica y el token deja de
    # ser opcional: ahí sí es una frontera real frente a otros dispositivos.
    host = "0.0.0.0" if args.lan else "127.0.0.1"
    token = ensure_token(db_path.parent / "config") if args.lan else None

    print(f"  base de datos: {db_path}")
    print(f"  escuchando en: http://{host}:{args.puerto}")
    if token:
        print(f"  token de acceso: {token}")
        print("  (guardado en data/config/token; necesario desde el móvil)")
    else:
        print("  solo accesible desde este equipo; usa --lan para el móvil")

    if args.abrir:
        # En un hilo aparte porque `serve()` no vuelve hasta que se para el
        # servidor: esperar aquí dejaría el navegador sin abrir nunca.
        url = f"http://127.0.0.1:{args.puerto}"
        threading.Thread(target=_abrir_cuando_responda, args=(url,), daemon=True).start()

    serve(db_path=db_path, host=host, port=args.puerto, token=token, require_token=bool(token))
    return 0


def cmd_mcp(args: argparse.Namespace) -> int:  # pragma: no cover - arranca el servidor
    """Levanta el servidor MCP por stdio, que es como lo lanza un cliente local.

    No imprime nada: en stdio, la salida estandar **es** el canal del protocolo
    y un mensaje de bienvenida lo corromperia.
    """
    import os

    from .mcp_server import main as mcp_main

    os.environ.setdefault("FITUP_DB", str(Path(args.db)))
    mcp_main()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fitup", description="Fit-Up")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="ruta de la base de datos")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="crear/actualizar la base de datos y sembrar el catálogo")
    sub.add_parser("check", help="verificar integridad y coherencia")

    reglas = sub.add_parser("reglas", help="alinear la sobrecarga de las rutinas con el catálogo")
    reglas.add_argument(
        "--aplicar", action="store_true", help="crear las versiones nuevas de verdad"
    )

    export = sub.add_parser("export", help="volcar todos los datos a un JSON")
    export.add_argument("--salida", default="data/export.json", help="fichero de destino")

    serve_cmd = sub.add_parser("serve", help="levantar la API y la interfaz")
    serve_cmd.add_argument("--puerto", type=int, default=8000)
    serve_cmd.add_argument(
        "--lan",
        action="store_true",
        help="exponer en la red local para usar desde el móvil (genera token)",
    )
    serve_cmd.add_argument(
        "--abrir",
        action="store_true",
        help="abrir el navegador cuando el servidor esté listo",
    )

    sub.add_parser("mcp", help="servidor MCP por stdio, para el agente de IA")

    args = parser.parse_args(argv)
    handler = {
        "init": cmd_init,
        "check": cmd_check,
        "reglas": cmd_reglas,
        "export": cmd_export,
        "serve": cmd_serve,
        "mcp": cmd_mcp,
    }[args.command]
    return handler(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
