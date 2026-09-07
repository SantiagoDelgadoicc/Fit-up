"""Apertura de la base de datos SQLite.

La configuración de esta función no es cosmética: el agente de IA es un
proceso externo y autónomo que puede abrir el fichero por su cuenta
(ADR-0004). WAL y ``busy_timeout`` hacen que esa concurrencia no rompa nada,
aunque el contrato documentado sea "usa la API, no el fichero".
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

#: Espera antes de rendirse si otro proceso tiene la escritura tomada.
BUSY_TIMEOUT_MS = 5000


def connect(
    path: str | Path, *, readonly: bool = False, same_thread: bool = True
) -> sqlite3.Connection:
    """Abre la base de datos con los PRAGMA que el proyecto da por sentados.

    ``same_thread=False`` desactiva la comprobación de hilo de SQLite. Hace
    falta bajo FastAPI, que resuelve la dependencia y ejecuta el endpoint en
    hilos distintos de su threadpool: la conexión se crea en uno y se usa en
    otro. Es seguro porque cada petición abre y cierra la suya y esos pasos
    ocurren en secuencia, nunca a la vez; lo que SQLite prohíbe de verdad es el
    uso **concurrente**, no el cambio de hilo.
    """
    path = Path(path)
    if not readonly:
        path.parent.mkdir(parents=True, exist_ok=True)

    if readonly and path.exists():
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=same_thread)
    else:
        conn = sqlite3.connect(path, check_same_thread=same_thread)

    conn.row_factory = sqlite3.Row
    # Sin esto SQLite ignora silenciosamente las FOREIGN KEY declaradas.
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
    if not readonly:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def connect_memory() -> sqlite3.Connection:
    """Base de datos en memoria para tests."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def integrity_ok(conn: sqlite3.Connection) -> bool:
    """Comprobación de integridad, para ejecutar al arrancar."""
    row = conn.execute("PRAGMA integrity_check").fetchone()
    return row is not None and row[0] == "ok"
