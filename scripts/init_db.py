#!/usr/bin/env python
"""
Initialize the database using Alembic migrations.

Usage:
    python scripts/init_db.py          # Create/upgrade database
    python scripts/init_db.py --reset  # Wipe and recreate from scratch

This script:
1. Creates required directories (data/, data/raw_files/, data/checkpoints/,
   data/traces/, data/projects/, data/sample_data/, logs/)
2. Warns about stale files (e.g., data/ivt_kinetics.db)
3. Runs Alembic migrations to create/update the database schema
4. Enables WAL mode for concurrent read performance
5. Verifies database state

Database location: <project_root>/ivt_kinetics.db  (NOT data/ivt_kinetics.db)

If Alembic migrations fail (e.g., missing migration files on a fresh clone),
falls back to db.create_all() and then stamps the Alembic version so future
migrations work correctly.
"""
import argparse
import subprocess
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app import create_app
from app.extensions import db
from app.config import Config

ALEMBIC_INI = project_root / "alembic" / "alembic.ini"

# All directories the application expects to exist
REQUIRED_DIRS = [
    Config.DATA_DIR,                        # data/
    Config.DATA_DIR / "raw_files",          # data/raw_files/  (UploadService)
    Config.DATA_DIR / "checkpoints",        # data/checkpoints/ (HierarchicalService)
    Config.DATA_DIR / "traces",             # data/traces/      (HierarchicalService)
    Config.DATA_DIR / "projects",           # data/projects/    (exports, MCMC traces)
    Config.DATA_DIR / "sample_data",        # data/sample_data/ (example files)
    Config.LOGS_DIR,                        # logs/
]


def check_stale_files():
    """Warn about known stale files that can cause confusion."""
    stale_db = Config.DATA_DIR / "ivt_kinetics.db"
    if stale_db.exists():
        size = stale_db.stat().st_size
        if size == 0:
            print(f"  WARNING: Stale empty file {stale_db}")
            print(f"           The real database is at {Config.DATABASE_PATH}")
            print(f"           You can safely delete: rm {stale_db}")
        else:
            print(f"  WARNING: {stale_db} exists ({size} bytes)")
            print(f"           The app uses {Config.DATABASE_PATH} — verify this file is not needed")


def wipe_database():
    """Remove existing database files for a fresh start."""
    db_path = Config.DATABASE_PATH
    huey_path = Config.HUEY_DATABASE_PATH

    removed = []
    for path in [
        db_path, Path(f"{db_path}-wal"), Path(f"{db_path}-shm"),
        huey_path, Path(f"{huey_path}-wal"), Path(f"{huey_path}-shm"),
    ]:
        if path.exists():
            path.unlink()
            removed.append(path.name)

    if removed:
        print(f"  Removed: {', '.join(removed)}")
    else:
        print("  No existing database files found")


def run_alembic(command: list[str]) -> subprocess.CompletedProcess:
    """Run an Alembic CLI command."""
    return subprocess.run(
        ["alembic", "-c", str(ALEMBIC_INI)] + command,
        cwd=str(project_root),
        capture_output=True,
        text=True,
    )


def run_alembic_upgrade() -> bool:
    """Run Alembic migrations to latest version."""
    if not ALEMBIC_INI.exists():
        print(f"  ERROR: Alembic config not found at {ALEMBIC_INI}")
        return False

    print("  Running alembic upgrade head ...")
    result = run_alembic(["upgrade", "head"])

    if result.returncode == 0:
        # Print only non-empty output lines
        for line in result.stdout.strip().splitlines():
            if line.strip():
                print(f"    {line.strip()}")
        return True

    stderr = result.stderr.strip()
    # "already exists" errors are OK in development
    if "already exists" in stderr.lower():
        print("  Tables already exist — schema may be up to date")
        return True

    print(f"  Migration error:\n    {stderr}")
    return False


def stamp_alembic_head() -> bool:
    """Stamp the database with the latest Alembic revision.

    This tells Alembic the schema is at head even though migrations
    didn't run (because db.create_all() created everything directly).
    Without this, the next 'alembic upgrade head' would fail trying
    to create tables that already exist.
    """
    print("  Stamping alembic version to head ...")
    result = run_alembic(["stamp", "head"])
    if result.returncode != 0:
        print(f"  WARNING: alembic stamp failed: {result.stderr.strip()}")
        return False
    return True


def fallback_create_all(app):
    """Create tables directly via SQLAlchemy as a last resort."""
    print("\n  Falling back to db.create_all() ...")
    with app.server.app_context():
        from app import models  # noqa: F401 — register all models
        db.create_all()
        print("  Tables created via db.create_all()")

    # Stamp so future Alembic migrations work
    stamp_alembic_head()


def enable_wal_mode(app):
    """Enable WAL journal mode for concurrent reads."""
    with app.server.app_context():
        db.session.execute(db.text("PRAGMA journal_mode=WAL"))
        db.session.commit()


def verify_database(app):
    """Print database state summary."""
    with app.server.app_context():
        # Journal mode
        row = db.session.execute(db.text("PRAGMA journal_mode")).fetchone()
        print(f"  Journal mode: {row[0] if row else 'unknown'}")

        # Alembic version
        try:
            row = db.session.execute(
                db.text("SELECT version_num FROM alembic_version")
            ).fetchone()
            if row:
                print(f"  Alembic version: {row[0]}")
            else:
                print("  WARNING: No alembic version stamp found")
        except Exception:
            print("  WARNING: alembic_version table missing")

        # Table count
        tables = db.session.execute(
            db.text(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%' "
                "ORDER BY name"
            )
        ).fetchall()
        print(f"  Tables: {len(tables)}")
        for t in tables:
            print(f"    - {t[0]}")


def nuke_all_data():
    """Remove all data files, traces, checkpoints, logs, and PID files."""
    import shutil

    data_subdirs = [
        Config.DATA_DIR / "raw_files",
        Config.DATA_DIR / "checkpoints",
        Config.DATA_DIR / "traces",
        Config.DATA_DIR / "projects",
        Config.DATA_DIR / "sample_data",
    ]

    for d in data_subdirs:
        if d.exists():
            count = sum(1 for _ in d.rglob("*") if _.is_file())
            if count:
                shutil.rmtree(d)
                d.mkdir(parents=True, exist_ok=True)
                print(f"  Cleared {d} ({count} files)")
            else:
                print(f"  {d} (already empty)")
        else:
            print(f"  {d} (not found)")

    # Application log
    log_file = Config.LOGS_DIR / "app.jsonl"
    if log_file.exists() and log_file.stat().st_size > 0:
        log_file.unlink()
        print(f"  Removed {log_file}")

    # Stale PID file
    pid_file = project_root / "huey_worker.pid"
    if pid_file.exists():
        pid_file.unlink()
        print(f"  Removed {pid_file}")


def init_database(reset: bool = False, nuke: bool = False):
    """Main entry point."""
    print("=" * 60)
    print("IVT Kinetics Analyzer — Database Initialization")
    print("=" * 60)

    # --- Directories ---
    print("\nDirectories:")
    for d in REQUIRED_DIRS:
        d.mkdir(parents=True, exist_ok=True)
        print(f"  {d}")

    # --- Stale file check ---
    print("\nFile checks:")
    check_stale_files()

    # --- Nuke (optional) ---
    if nuke:
        print("\nNuking all data:")
        wipe_database()
        nuke_all_data()
    # --- Reset (optional) ---
    elif reset:
        print("\nResetting database:")
        wipe_database()

    # --- Migrate ---
    print(f"\nDatabase: {Config.DATABASE_PATH}")
    migration_ok = run_alembic_upgrade()

    # --- Verify core table exists ---
    app = create_app()
    with app.server.app_context():
        try:
            row = db.session.execute(
                db.text(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='table' AND name='projects'"
                )
            ).fetchone()
            tables_exist = row is not None
        except Exception:
            tables_exist = False

    if not migration_ok or not tables_exist:
        fallback_create_all(app)

    # --- WAL mode ---
    enable_wal_mode(app)

    # --- Verify ---
    print("\nVerification:")
    verify_database(app)

    print("\n" + "=" * 60)
    print("Done.")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Initialize the IVT Kinetics database")
    parser.add_argument(
        "--reset", action="store_true",
        help="Wipe existing database files before initializing",
    )
    parser.add_argument(
        "--nuke", action="store_true",
        help="Complete reset: wipe database, uploads, traces, checkpoints, and logs",
    )
    args = parser.parse_args()

    if args.nuke:
        confirm = input(
            "WARNING: This will delete ALL data (database, uploads, traces, "
            "checkpoints, logs).\nType 'yes' to confirm: "
        )
        if confirm.strip().lower() != "yes":
            print("Aborted.")
            sys.exit(0)

    init_database(reset=args.reset, nuke=args.nuke)
