"""Save or restore the production database while the web container is stopped."""

import os
import sqlite3
import sys
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory


def copy_database(source, destination):
    with (
        closing(sqlite3.connect(f"{source.as_uri()}?mode=ro", uri=True)) as original,
        closing(sqlite3.connect(destination)) as copy,
    ):
        original.backup(copy)


def save_snapshot(database, backup):
    if backup.exists():
        raise RuntimeError("The deployment backup already exists.")

    with TemporaryDirectory(prefix=".deploy-", dir=backup.parent) as directory:
        staged = Path(directory) / "backup.sqlite3"
        copy_database(database, staged)
        with closing(sqlite3.connect(staged)) as db:
            if db.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
                raise RuntimeError("The SQLite database did not pass its integrity check.")
            db.execute("SELECT 1 FROM diptychs_diptych LIMIT 1")
            db.execute("SELECT 1 FROM auth_user LIMIT 1")
        staged.chmod(0o600)
        staged.replace(backup)


if __name__ == "__main__":
    database = Path(os.environ["DJANGO_DB_PATH"])
    backup = Path(os.environ["DISMANTLING_DEPLOYMENT_BACKUP"])
    action, = sys.argv[1:]
    if action == "save":
        save_snapshot(database, backup)
    elif action == "restore":
        copy_database(backup, database)
    elif action == "clear":
        backup.unlink(missing_ok=True)
    else:
        raise SystemExit(f"Unknown snapshot action: {action}")
