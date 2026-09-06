"""Migrador mínimo de esquema.

Sin Alembic: el proyecto es de un solo usuario, con migraciones lineales y
sin necesidad de ramas ni autogeneración. Un fichero ``.sql`` numerado por
migración, aplicado en orden dentro de una transacción, cubre el caso entero
y no añade una dependencia que habría que mantener años.

El registro de qué se ha aplicado existe desde la primera versión: los datos
de entrenamiento son irreemplazables y no admiten un esquema improvisado.
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
_FILENAME = re.compile(r"^(\d{4})_([a-z0-9_]+)\.sql$")

_SCHEMA_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migration (
    version    INTEGER NOT NULL PRIMARY KEY,
    name       TEXT    NOT NULL,
    checksum   TEXT    NOT NULL,
    applied_at TEXT    NOT NULL
)
"""


class MigrationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class Migration:
    version: int
    name: str
    sql: str

    @property
    def checksum(self) -> str:
        return hashlib.sha256(self.sql.encode("utf-8")).hexdigest()[:16]


def discover(directory: Path | None = None) -> list[Migration]:
    """Migraciones disponibles, ordenadas por versión."""
    directory = directory or MIGRATIONS_DIR
    found: list[Migration] = []
    seen: set[int] = set()

    for path in sorted(directory.glob("*.sql")):
        match = _FILENAME.match(path.name)
        if not match:
            raise MigrationError(f"'{path.name}' no sigue el formato NNNN_nombre.sql")
        version = int(match.group(1))
        if version in seen:
            raise MigrationError(f"Versión de migración duplicada: {version}")
        seen.add(version)
        found.append(Migration(version, match.group(2), path.read_text(encoding="utf-8")))

    return sorted(found, key=lambda m: m.version)


def applied_versions(conn: sqlite3.Connection) -> dict[int, str]:
    """Versiones ya aplicadas, mapeadas a su checksum."""
    conn.execute(_SCHEMA_TABLE)
    rows = conn.execute("SELECT version, checksum FROM schema_migration").fetchall()
    return {
        row["version"] if isinstance(row, sqlite3.Row) else row[0]: row["checksum"]
        if isinstance(row, sqlite3.Row)
        else row[1]
        for row in rows
    }


def migrate(conn: sqlite3.Connection, directory: Path | None = None) -> list[Migration]:
    """Aplica las migraciones pendientes. Devuelve las aplicadas en esta llamada.

    Verifica el checksum de las ya aplicadas: editar una migración que ya
    corrió deja la base de datos en un estado que el código no describe, y es
    mejor fallar ruidosamente que seguir sobre una suposición falsa.
    """
    already = applied_versions(conn)
    applied: list[Migration] = []

    for migration in discover(directory):
        previous = already.get(migration.version)
        if previous is not None:
            if previous != migration.checksum:
                raise MigrationError(
                    f"La migración {migration.version:04d}_{migration.name} cambió "
                    f"después de haberse aplicado (checksum {previous} → "
                    f"{migration.checksum}). Crea una migración nueva en vez de "
                    "editar una ya aplicada."
                )
            continue

        try:
            conn.executescript(migration.sql)
            conn.execute(
                "INSERT INTO schema_migration (version, name, checksum, applied_at) "
                "VALUES (?, ?, ?, ?)",
                (
                    migration.version,
                    migration.name,
                    migration.checksum,
                    datetime.now(UTC).isoformat(timespec="seconds"),
                ),
            )
            conn.commit()
        except sqlite3.Error as exc:  # pragma: no cover - depende del SQL
            conn.rollback()
            raise MigrationError(
                f"Fallo aplicando {migration.version:04d}_{migration.name}: {exc}"
            ) from exc

        applied.append(migration)

    return applied


def current_version(conn: sqlite3.Connection) -> int:
    versions = applied_versions(conn)
    return max(versions) if versions else 0
