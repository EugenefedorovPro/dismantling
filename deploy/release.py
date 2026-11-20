"""Deploy the tested Git revision to the VPS and roll back a failed startup."""

import fcntl
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory


CHECKOUT = Path("/opt/apps/dismantling")
RELEASE_IMAGE = "dismantling-web:release"
ROLLBACK_IMAGE = "dismantling-web:rollback"


def run(*command, env=None, capture=False, input_data=None):
    return subprocess.run(
        command, check=True, env=env, input=input_data,
        stdout=subprocess.PIPE if capture else None,
    ).stdout


def check_mount(mounts, data_dir):
    if mounts != [("bind", str(data_dir), True)]:
        raise RuntimeError(
            f"Expected {data_dir} mounted read-write at /data. "
            "Use the production bind mount with the current database before deploying."
        )


def activate(compose, previous, environment):
    def snapshot(action):
        compose(
            "run", "--no-deps", "--rm", "-T", "--entrypoint", "python",
            "web", "deploy/sqlite_snapshot.py", action,
        )

    start = ("up", "-d", "--no-build", "--pull", "never", "--wait", "--wait-timeout", "180", "web")
    was_running = previous is not None and previous["State"]["Running"]
    try:
        if was_running:
            compose("stop", "web")
        snapshot("save")
    except (subprocess.CalledProcessError, KeyboardInterrupt):
        if was_running:
            run("docker", "start", previous["Id"])
        raise

    try:
        compose(*start)
    except (subprocess.CalledProcessError, KeyboardInterrupt):
        print("Release failed its startup check. Restoring the previous database.", flush=True)
        compose("stop", "web")
        snapshot("restore")
        if was_running:
            compose(*start, env={**environment, "DISMANTLING_IMAGE": ROLLBACK_IMAGE})
        snapshot("clear")
        if was_running:
            print("The previous release is healthy again.", flush=True)
        raise

    snapshot("clear")


def deploy(checkout, revision):
    run("git", "-C", checkout, "fetch", "--no-tags", "origin", "refs/heads/main")
    head = run("git", "-C", checkout, "rev-parse", "FETCH_HEAD", capture=True).decode().strip()
    if head != revision:
        print(f"Skipping {revision}. The current main revision is {head}.", flush=True)
        return

    env_file = checkout / ".env"
    data_dir = checkout / "data"
    database = data_dir / "db.sqlite3"
    if not env_file.is_file() or not database.is_file() or not database.stat().st_size:
        raise RuntimeError(f"Production .env and an initialized {database} are required.")
    if (data_dir / ".deploy-backup.sqlite3").exists():
        raise RuntimeError("A deployment backup is still present. Check the previous rollout before retrying.")

    with TemporaryDirectory(prefix="dismantling-release-") as release:
        archive = run("git", "-C", checkout, "archive", revision, capture=True)
        run("tar", "-xf", "-", "-C", release, input_data=archive)

        environment = {
            **os.environ,
            "DISMANTLING_DATA_DIR": str(data_dir),
            "DISMANTLING_IMAGE": RELEASE_IMAGE,
        }
        files = Path(release)
        compose_args = (
            "docker", "compose", "--env-file", env_file,
            "-f", files / "docker-compose.yaml", "-f", files / "deploy/compose.production.yaml",
        )

        def compose(*args, env=environment, capture=False):
            return run(*compose_args, *args, env=env, capture=capture)

        web = json.loads(compose("config", "--format", "json", capture=True))["services"]["web"]
        config = web["environment"]
        key = config.get("DJANGO_SECRET_KEY") or ""
        if (
            config.get("DJANGO_DEBUG") != "0"
            or len(key) < 32
            or key.startswith(("django-insecure-", "REPLACE_WITH_"))
        ):
            raise RuntimeError("Production requires DJANGO_DEBUG=0 and a strong DJANGO_SECRET_KEY.")
        if config.get("DJANGO_DB_PATH") != "/data/db.sqlite3":
            raise RuntimeError("Production Django must use /data/db.sqlite3.")

        configured_mounts = [
            (volume["type"], volume.get("source"), not volume.get("read_only", False))
            for volume in web["volumes"] if volume["target"] == "/data"
        ]
        check_mount(configured_mounts, data_dir)

        containers = compose("ps", "--all", "--quiet", "web", capture=True).decode().split()
        if len(containers) > 1:
            raise RuntimeError("Expected one production web container.")
        previous = None
        if containers:
            previous, = json.loads(run("docker", "inspect", containers[0], capture=True))
            current_mounts = [
                (mount["Type"], mount["Source"], mount["RW"])
                for mount in previous["Mounts"] if mount["Destination"] == "/data"
            ]
            check_mount(current_mounts, data_dir)
            if previous["State"]["Running"]:
                run("docker", "image", "tag", previous["Image"], ROLLBACK_IMAGE)

        print(f"Building tested revision {revision}.", flush=True)
        compose("build", "web")
        activate(compose, previous, environment)


if __name__ == "__main__":
    revision, = sys.argv[1:]
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise SystemExit("A full tested Git commit SHA is required.")
    with (CHECKOUT / ".deploy.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        deploy(CHECKOUT, revision)
