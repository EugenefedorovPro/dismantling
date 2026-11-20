import sqlite3
import subprocess
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock, call, patch

import release
from sqlite_snapshot import copy_database, save_snapshot


class ReleaseTests(TestCase):
    def test_stale_workflow_stops_before_running_compose(self):
        with patch.object(release, "run", side_effect=[None, b"newer-commit\n"]) as run:
            release.deploy(Path("/unused"), "older-commit")

        self.assertEqual(run.call_count, 2)

    def test_rejects_unexpected_database_mounts(self):
        data_dir = Path("/opt/apps/dismantling/data")
        release.check_mount([("bind", str(data_dir), True)], data_dir)
        for mount in (
            [],
            [("volume", "sqlite_data", True)],
            [("bind", "/other/data", True)],
            [("bind", str(data_dir), False)],
        ):
            with self.subTest(mount=mount), self.assertRaises(RuntimeError):
                release.check_mount(mount, data_dir)

    def test_failed_startup_restores_database_and_previous_image(self):
        def fail_new_image(command, *args, **kwargs):
            if command == "up" and "env" not in kwargs:
                raise subprocess.CalledProcessError(1, command)

        compose = Mock(side_effect=fail_new_image)
        previous = {"State": {"Running": True}}
        with self.assertRaises(subprocess.CalledProcessError):
            release.activate(compose, previous, {})

        actions = [
            args[-1] if args[0] == "run" else args[0]
            for args, kwargs in compose.call_args_list
        ]
        self.assertEqual(actions, ["stop", "save", "up", "stop", "restore", "up", "clear"])
        self.assertEqual(
            compose.call_args_list[5].kwargs["env"]["DISMANTLING_IMAGE"],
            release.ROLLBACK_IMAGE,
        )

    def test_failed_snapshot_restarts_the_original_container(self):
        compose = Mock(side_effect=[None, subprocess.CalledProcessError(1, "save")])
        previous = {"Id": "previous-container", "State": {"Running": True}}
        with patch.object(release, "run") as run, self.assertRaises(subprocess.CalledProcessError):
            release.activate(compose, previous, {})

        self.assertEqual(run.call_args_list, [call("docker", "start", "previous-container")])
        self.assertEqual(compose.call_count, 2)


class SQLiteSnapshotTests(TestCase):
    def test_rollback_restores_schema_and_content_from_wal_snapshot(self):
        with TemporaryDirectory() as directory:
            data_dir = Path(directory)
            database = data_dir / "db.sqlite3"
            backup = data_dir / ".deploy-backup.sqlite3"

            with closing(sqlite3.connect(database)) as db, db:
                db.execute("PRAGMA journal_mode=WAL")
                db.execute("CREATE TABLE auth_user (id INTEGER)")
                db.execute("CREATE TABLE diptychs_diptych (title TEXT)")
                db.execute("INSERT INTO diptychs_diptych VALUES ('Original poem')")
                db.commit()

                save_snapshot(database, backup)
                db.execute("ALTER TABLE diptychs_diptych ADD COLUMN changed TEXT")
                db.execute("UPDATE diptychs_diptych SET title = 'Changed by migration'")

            copy_database(backup, database)
            with closing(sqlite3.connect(database)) as db:
                self.assertEqual(db.execute("SELECT * FROM diptychs_diptych").fetchall(), [("Original poem",)])
