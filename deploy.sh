#!/usr/bin/env bash
set -euo pipefail

BRANCH="${1:-main}"
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="${VENV:-$APP_DIR/.venv}"
PYTHON="${PYTHON:-$VENV/bin/python}"
PIP="${PIP:-$VENV/bin/pip}"
SERVICE_NAME="${SERVICE_NAME:-finch}"
MANAGE="$PYTHON $APP_DIR/manage.py"

if [[ ! -d "$APP_DIR/.git" ]]; then
  echo "Error: $APP_DIR is not a git repository." >&2
  exit 1
fi

if [[ ! -x "$PYTHON" ]]; then
  echo "Error: virtual environment not found at $VENV." >&2
  echo "Create it first, for example: python3 -m venv .venv" >&2
  exit 1
fi

echo "==> Updating code from origin/$BRANCH"
git -C "$APP_DIR" fetch origin "$BRANCH"
git -C "$APP_DIR" checkout -B "$BRANCH" "origin/$BRANCH"
git -C "$APP_DIR" reset --hard "origin/$BRANCH"
git -C "$APP_DIR" clean -fd

echo "==> Installing Python dependencies"
"$PIP" install -r "$APP_DIR/requirements.txt"

echo "==> Running migrations"
$MANAGE migrate --noinput

if $MANAGE help compilemessages >/dev/null 2>&1; then
  echo "==> Compiling translation messages"
  $MANAGE compilemessages
fi

echo "==> Collecting static files"
$MANAGE collectstatic --noinput

echo "==> Checking deployment health"
$MANAGE check --deploy

if command -v systemctl >/dev/null 2>&1; then
  echo "==> Restarting service"
  systemctl restart "$SERVICE_NAME"
  systemctl --no-pager --full status "$SERVICE_NAME" || true
else
  echo "==> systemctl not available, skipping service restart"
fi

echo "Deployment finished successfully."
