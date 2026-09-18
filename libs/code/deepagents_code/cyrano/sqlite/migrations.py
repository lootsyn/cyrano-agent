"""Guarded schema migration: dry-run, explicit mapping, backup.

An existing database is never silently merged with target DDL.
Opening requires a supported ``user_version``; migration requires an
explicit plan, a backup, and a checksum/integrity verification.
"""

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from deepagents_code.cyrano.contracts.canonical import digest
from deepagents_code.cyrano.contracts.types import CyranoError

SUPPORTED_SCHEMA_VERSION = 1

FOUNDATION_TABLES = ("streams", "events", "requests", "outbox")


@dataclass(frozen=True, slots=True)
class DatabaseInfo:
    """Observed database shape before any migration decision."""

    user_version: int
    tables: tuple[str, ...]
    integrity_ok: bool


@dataclass(frozen=True, slots=True)
class MigrationPlan:
    """An explicit, reviewable migration; never applied implicitly."""

    from_version: int
    to_version: int
    ddl: str
    field_mapping: dict[str, str]
    requires_backup: bool


def inspect_database(connection: sqlite3.Connection) -> DatabaseInfo:
    """Read version, tables, and integrity without mutating."""
    version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    tables = tuple(
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
    )
    integrity = connection.execute("PRAGMA integrity_check").fetchone()
    return DatabaseInfo(
        user_version=version,
        tables=tables,
        integrity_ok=bool(integrity) and integrity[0] == "ok",
    )


def guard_supported(connection: sqlite3.Connection) -> DatabaseInfo:
    """Refuse future or corrupt databases instead of downgrading."""
    info = inspect_database(connection)
    if not info.integrity_ok:
        raise CyranoError("CORRUPT_DATABASE", "integrity_check failed")
    if info.user_version > SUPPORTED_SCHEMA_VERSION:
        raise CyranoError(
            "FUTURE_SCHEMA",
            f"database version {info.user_version} exceeds "
            f"supported {SUPPORTED_SCHEMA_VERSION}",
        )
    if info.user_version == 0 and info.tables:
        raise CyranoError(
            "UNVERSIONED_DATABASE",
            "tables exist without a schema version; "
            "explicit migration required",
        )
    return info


def _is_foundation(connection: sqlite3.Connection) -> bool:
    """A foundation DB has the pre-scope ``streams(stream,...)``."""
    names = {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    if "streams" not in names:
        return False
    columns = {
        str(row[1]) for row in connection.execute("PRAGMA table_info(streams)")
    }
    return "stream" in columns and "stream_id" not in columns


def plan_migration(
    connection: sqlite3.Connection, target_ddl: str
) -> MigrationPlan:
    """Dry-run the migration and report the required mapping."""
    info = inspect_database(connection)
    if not info.integrity_ok:
        raise CyranoError("CORRUPT_DATABASE", "integrity_check failed")
    if info.user_version > SUPPORTED_SCHEMA_VERSION:
        raise CyranoError(
            "FUTURE_SCHEMA",
            f"database version {info.user_version} exceeds "
            f"supported {SUPPORTED_SCHEMA_VERSION}",
        )
    mapping: dict[str, str] = {}
    if info.user_version == 0 and _is_foundation(connection):
        mapping = {
            "streams.stream": "streams.stream_id",
            "streams.revision": "streams.revision",
            "events.revision": "events.stream_revision",
            "requests.request_key": "requests.idempotency_key",
            "outbox.job_key": "outbox.job_id",
        }
    elif info.user_version == 0 and info.tables:
        raise CyranoError(
            "MIGRATION_MAPPING_REQUIRED",
            "unversioned layout needs an explicit mapping",
        )
    return MigrationPlan(
        from_version=info.user_version,
        to_version=SUPPORTED_SCHEMA_VERSION,
        ddl=target_ddl,
        field_mapping=mapping,
        requires_backup=bool(info.tables),
    )


def _copy_foundation_rows(
    connection: sqlite3.Connection, scope_id: str
) -> None:
    """Copy mapped foundation rows into the target tables."""
    connection.execute(
        "INSERT INTO streams(stream_id,scope_id,revision,"
        "entity_type,status) "
        "SELECT stream,?,revision,'migrated','open' FROM "
        "foundation_streams",
        (scope_id,),
    )
    rows = connection.execute(
        "SELECT rowid,stream,revision,payload,payload_digest "
        "FROM foundation_events ORDER BY stream,revision"
    ).fetchall()
    for index, (rowid, stream, revision, payload, pdigest) in enumerate(rows):
        connection.execute(
            "INSERT OR IGNORE INTO artifacts VALUES (?,?,?,?,?,?,?,?)",
            (
                pdigest,
                scope_id,
                f"migrated/{rowid}",
                "application/json",
                len(str(payload)),
                "internal",
                "migrated",
                0,
            ),
        )
        connection.execute(
            "INSERT INTO events(event_id,stream_id,"
            "stream_revision,producer,producer_seq,kind,"
            "schema_version,payload_digest,observed_at,"
            "ingested_at,observation_kind) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                digest(
                    {"migrated": rowid, "stream": stream, "revision": revision}
                ),
                stream,
                revision,
                "migration",
                index,
                "migrated",
                1,
                pdigest,
                "migrated",
                "migrated",
                "control",
            ),
        )


def apply_migration(
    db_path: Path,
    plan: MigrationPlan,
    backup_path: Path,
    *,
    default_scope: tuple[str, str, str] | None = None,
) -> DatabaseInfo:
    """Backup, apply, verify; a failed verify restores the backup.

    Foundation rows are only copied when the caller supplies an
    explicit ``default_scope`` for scope-less legacy data.
    """
    if plan.field_mapping and default_scope is None:
        raise CyranoError(
            "MIGRATION_SCOPE_REQUIRED",
            "scope-less foundation rows need an explicit default scope",
        )
    if plan.requires_backup:
        source = sqlite3.connect(str(db_path))
        try:
            dest = sqlite3.connect(str(backup_path))
            try:
                source.backup(dest)
            finally:
                dest.close()
        finally:
            source.close()
    connection = sqlite3.connect(str(db_path), isolation_level=None)
    try:
        try:
            if plan.field_mapping:
                for table in FOUNDATION_TABLES:
                    connection.execute(
                        f"ALTER TABLE {table} RENAME TO foundation_{table}"
                    )
            connection.executescript(plan.ddl)
            if plan.field_mapping:
                if default_scope is None:
                    raise CyranoError(
                        "MIGRATION_SCOPE_REQUIRED",
                        "scope-less rows need a default scope",
                    )
                scope_id = digest(
                    {
                        "tenant": default_scope[0],
                        "user": default_scope[1],
                        "workspace": default_scope[2],
                    }
                )
                connection.execute(
                    "INSERT OR IGNORE INTO scopes VALUES (?,?,?,?,0)",
                    (scope_id, *default_scope),
                )
                _copy_foundation_rows(connection, scope_id)
            connection.execute(f"PRAGMA user_version={plan.to_version}")
        except BaseException:
            connection.rollback()
            raise
        info = inspect_database(connection)
        if not info.integrity_ok or info.user_version != plan.to_version:
            raise CyranoError(
                "MIGRATION_CHECKSUM", "post-migration verify failed"
            )
        return info
    except BaseException:
        connection.close()
        if plan.requires_backup and backup_path.exists():
            source = sqlite3.connect(str(backup_path))
            try:
                dest = sqlite3.connect(str(db_path), isolation_level=None)
                try:
                    source.backup(dest)
                finally:
                    dest.close()
            finally:
                source.close()
        raise
    finally:
        try:
            connection.close()
        except sqlite3.Error:
            pass
