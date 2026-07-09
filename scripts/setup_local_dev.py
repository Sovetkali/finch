#!/usr/bin/env python3
"""Prepare Finch for local development with SQLite.

This script keeps the workflow simple:
- backs up the current .env file once per change
- removes production-only database settings
- forces local-safe defaults
- optionally runs Django migrations
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = PROJECT_ROOT / ".env"
BACKUP_PATH = PROJECT_ROOT / ".env.local.backup"

LOCAL_DEFAULTS = {
    "DEBUG": "True",
    "ALLOWED_HOSTS": "127.0.0.1,localhost",
    "EMAIL_BACKEND": "django.core.mail.backends.console.EmailBackend",
}

REMOVE_KEYS = {
    "DATABASE_URL",
    "REDIS_URL",
    "CELERY_BROKER_URL",
    "CELERY_RESULT_BACKEND",
    "EMAIL_HOST",
    "EMAIL_PORT",
    "EMAIL_USE_TLS",
    "EMAIL_HOST_USER",
    "EMAIL_HOST_PASSWORD",
    "DB_PASSWORD",
}


def parse_env_lines(text: str) -> list[str]:
    return text.splitlines()


def update_env_file() -> bool:
    if not ENV_PATH.exists():
        lines: list[str] = []
    else:
        if not BACKUP_PATH.exists():
            shutil.copy2(ENV_PATH, BACKUP_PATH)
            print(f"Created backup: {BACKUP_PATH.name}")
        lines = parse_env_lines(ENV_PATH.read_text(encoding="utf-8"))

    seen = set()
    updated: list[str] = []
    changed = False

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in raw_line:
            updated.append(raw_line)
            continue

        key, _, value = raw_line.partition("=")
        key = key.strip()

        if key in REMOVE_KEYS:
            changed = True
            continue

        if key in LOCAL_DEFAULTS:
            new_value = LOCAL_DEFAULTS[key]
            if value != new_value:
                changed = True
                updated.append(f"{key}={new_value}")
            else:
                updated.append(raw_line)
            seen.add(key)
            continue

        updated.append(raw_line)
        seen.add(key)

    for key, value in LOCAL_DEFAULTS.items():
        if key not in seen:
            updated.append(f"{key}={value}")
            changed = True

    new_text = "\n".join(updated).rstrip() + "\n"
    if not ENV_PATH.exists() or ENV_PATH.read_text(encoding="utf-8") != new_text:
        ENV_PATH.write_text(new_text, encoding="utf-8")
        changed = True

    return changed


def run_migrations() -> int:
    cmd = [sys.executable, "manage.py", "migrate"]
    return subprocess.call(cmd, cwd=PROJECT_ROOT)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare Finch for local development with SQLite."
    )
    parser.add_argument(
        "--migrate",
        action="store_true",
        help="Run Django migrations after updating .env.",
    )
    args = parser.parse_args()

    changed = update_env_file()
    if changed:
        print(f"Updated {ENV_PATH.name} for local development.")
        print(f"Backup stored at {BACKUP_PATH.name}")
    else:
        print(f"{ENV_PATH.name} already looks ready for local development.")

    if args.migrate:
        print("Running migrations...")
        return run_migrations()

    print("Next: run `./.venv/bin/python manage.py runserver`")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
