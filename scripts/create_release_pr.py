#!/usr/bin/env python3
"""Create a GitHub PR with production-facing changes only.

The script is intentionally strict:
- it refuses to include local-only files
- it commits only the allowed production paths
- it creates a PR from the current branch into `main`

Usage:
    .venv/bin/python scripts/create_release_pr.py \
        --title "Describe change" \
        --body "Optional PR body"
"""

from __future__ import annotations

import argparse
import datetime as dt
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAIN_BRANCH = "main"

ALLOWED_PREFIXES = (
    "config/",
    "finch/",
    "templates/",
    "locale/",
    "requirements.txt",
    "manage.py",
    "gunicorn.conf.py",
    "nginx.conf",
    "Procfile",
    "DEPLOYMENT_CHECKLIST.md",
)

FORBIDDEN_PREFIXES = (
    ".env",
    "db.sqlite3",
    "staticfiles/",
    ".venv/",
    "scripts/",
    "__pycache__/",
)


def run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=check,
    )


def git(*args: str, check: bool = True) -> str:
    result = run(["git", *args], check=check)
    return result.stdout.strip()


def current_branch() -> str:
    return git("rev-parse", "--abbrev-ref", "HEAD")


def current_head() -> str:
    return git("rev-parse", "--short", "HEAD")


def changed_files() -> list[str]:
    output = git("diff", "--name-only", f"{MAIN_BRANCH}...HEAD")
    files = [line.strip() for line in output.splitlines() if line.strip()]
    return files


def working_tree_files() -> list[str]:
    output = git("status", "--short")
    files: list[str] = []
    for line in output.splitlines():
        if not line.strip():
            continue
        path = line[4:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        files.append(path)
    return files


def validate_files(files: list[str]) -> None:
    if not files:
        raise SystemExit("No changes found compared to main.")

    forbidden = []
    for path in files:
        if any(path == prefix or path.startswith(prefix) for prefix in FORBIDDEN_PREFIXES):
            forbidden.append(path)

    if forbidden:
        joined = "\n  - ".join(forbidden)
        raise SystemExit(
            "Refusing to create a release PR because these local-only files are present:\n"
            f"  - {joined}\n"
            "Move them out of the branch or commit them separately."
        )

    outside_allowlist = [
        path for path in files
        if not any(path == prefix or path.startswith(prefix) for prefix in ALLOWED_PREFIXES)
    ]
    if outside_allowlist:
        joined = "\n  - ".join(outside_allowlist)
        raise SystemExit(
            "Refusing to create a release PR because these files are outside the "
            "production allowlist:\n"
            f"  - {joined}\n"
            "If they are genuinely production-facing, add them to the allowlist."
        )


def create_commit(branch: str, title: str) -> None:
    files = changed_files()
    validate_files(files)
    git("add", *files)
    git("commit", "-m", title)
    print(f"Committed production changes on branch: {branch}")


def auto_commit_working_tree(branch: str, title: str) -> None:
    files = working_tree_files()
    validate_files(files)
    if not files:
        return
    git("add", *files)
    git("commit", "-m", title)
    print(f"Committed working tree changes on {branch}.")


def create_pr(title: str, body: str) -> str:
    cmd = [
        "gh",
        "pr",
        "create",
        "--base",
        MAIN_BRANCH,
        "--head",
        current_branch(),
        "--title",
        title,
        "--body",
        body,
    ]
    result = run(cmd)
    return result.stdout.strip()


def github_compare_url(branch: str) -> str:
    remote_url = git("remote", "get-url", "origin")
    if remote_url.endswith(".git"):
        remote_url = remote_url[:-4]
    if remote_url.startswith("git@github.com:"):
        remote_url = "https://github.com/" + remote_url.removeprefix("git@github.com:")
    if remote_url.startswith("https://github.com/"):
        return f"{remote_url}/compare/{MAIN_BRANCH}...{branch}"
    return f"Compare {MAIN_BRANCH}...{branch} on your remote: {remote_url}"


def create_release_branch_from_main() -> str:
    timestamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    branch_name = f"codex/release-{timestamp}"
    git("stash", "push", "-u", "-m", f"release-pr auto-stash {timestamp}")
    git("checkout", "-b", branch_name, MAIN_BRANCH)
    try:
        git("stash", "pop")
    except subprocess.CalledProcessError as exc:
        raise SystemExit(
            "Created a release branch, but restoring stashed changes failed.\n"
            "Resolve the conflict manually, then rerun the release script."
        ) from exc
    return branch_name


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a GitHub PR for production-facing Finch changes."
    )
    parser.add_argument("--title", required=True, help="PR title.")
    parser.add_argument(
        "--body",
        default="",
        help="Optional PR body. If omitted, an empty body is used.",
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Create a commit from the current production changes before opening the PR.",
    )
    args = parser.parse_args()

    branch = current_branch()
    if branch == MAIN_BRANCH:
        branch = create_release_branch_from_main()
        print(f"Created release branch: {branch}")

    if args.commit or working_tree_files():
        auto_commit_working_tree(branch, args.title)

    try:
        pr_url = create_pr(args.title, args.body)
        if pr_url:
            print(f"Branch: {branch}")
            print(pr_url)
        else:
            print(f"Branch: {branch}")
            print("PR created.")
    except subprocess.CalledProcessError as exc:
        print(f"Branch: {branch}")
        print("Automatic PR creation failed.")
        if exc.stderr:
            print(exc.stderr.strip())
        print(github_compare_url(branch))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
