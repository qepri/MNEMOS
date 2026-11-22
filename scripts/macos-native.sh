#!/usr/bin/env bash
# macos-native.sh — run MNEMOS natively on macOS (Apple Silicon), no container runtime.
#
# Same processes as docker-compose: the Flask app under gunicorn and the Celery worker, plus the Redis
# they share. Postgres (with pgvector) and Ollama are expected to be already running on the host, the
# same assumption docker-compose.mac.yml makes.
#
#   scripts/macos-native.sh install   create .venv-macos and install the pinned dependencies (CPU build)
#   scripts/macos-native.sh up        start Redis (if needed), run migrations, start app + worker
#   scripts/macos-native.sh down      stop app + worker (and Redis, if this script started it)
#   scripts/macos-native.sh status    what is running and whether the API answers
#   scripts/macos-native.sh logs      tail the app and worker logs
#
# Configuration comes from .env.macos (copy .env.macos.example). Nothing in it is committed.
#
# Why the lock is filtered: requirements.lock.txt is compiled in a CUDA environment and pins nvidia-*,
# cuda-* and triton packages that have no macOS wheels. On macOS, PyPI's torch wheel is already the
# CPU/MPS build, so dropping those lines is the same thing the Dockerfile does for its CPU image
# (TORCH_INDEX), minus the extra index.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$ROOT/.venv-macos"
RUN="$ROOT/data/macos-native"
ENV_FILE="$ROOT/.env.macos"
PYTHON="${MNEMOS_PYTHON:-python3.11}"
mkdir -p "$RUN"

load_env() {
  [ -f "$ENV_FILE" ] || { echo "missing $ENV_FILE (copy .env.macos.example)" >&2; exit 1; }
  set -a; # shellcheck disable=SC1090
  . "$ENV_FILE"; set +a
  export FLASK_APP="${FLASK_APP:-app:create_app}"
  export GUNICORN_BIND="${GUNICORN_BIND:-127.0.0.1:8300}"
  export GUNICORN_WORKERS="${GUNICORN_WORKERS:-2}"
  export UPLOAD_FOLDER="${UPLOAD_FOLDER:-$ROOT/data/uploads}"
  export ARCHIVE_FOLDER="${ARCHIVE_FOLDER:-$ROOT/data/archive}"
  mkdir -p "$UPLOAD_FOLDER" "$ARCHIVE_FOLDER"
}

redis_port() { echo "${REDIS_URL:-redis://127.0.0.1:6379/0}" | sed -E 's#.*:([0-9]+)/.*#\1#'; }
alive() { [ -f "$1" ] && kill -0 "$(cat "$1")" 2>/dev/null; }
api_code() { curl -s -m 3 -o /dev/null -w '%{http_code}' "http://${GUNICORN_BIND}/api/health" 2>/dev/null || true; }

case "${1:-status}" in
  install)
    command -v "$PYTHON" >/dev/null || { echo "need Python 3.11 ($PYTHON); set MNEMOS_PYTHON" >&2; exit 1; }
    [ -d "$VENV" ] || "$PYTHON" -m venv "$VENV"
    grep -viE '^(nvidia-|cuda-|triton)' "$ROOT/requirements.lock.txt" > "$RUN/requirements.macos.txt"
    "$VENV/bin/pip" install --upgrade pip >/dev/null
    "$VENV/bin/pip" install -r "$RUN/requirements.macos.txt"
    echo "installed into $VENV"
    ;;
  up)
    load_env
    [ -x "$VENV/bin/gunicorn" ] || { echo "run '$0 install' first" >&2; exit 1; }
    PORT=$(redis_port)
    if ! redis-cli -p "$PORT" ping >/dev/null 2>&1; then
      command -v redis-server >/dev/null || { echo "need redis-server (brew install redis)" >&2; exit 1; }
      redis-server --port "$PORT" --bind 127.0.0.1 --dir "$RUN" --daemonize yes --pidfile "$RUN/redis.pid" \
        --logfile "$RUN/redis.log" --save "" --appendonly no
      echo "redis started on $PORT"
    fi
    cd "$ROOT"
    echo "applying migrations..."; "$VENV/bin/flask" db upgrade
    alive "$RUN/app.pid" || "$VENV/bin/gunicorn" -c gunicorn.conf.py --daemon --pid "$RUN/app.pid" \
      --access-logfile "$RUN/app.log" --error-logfile "$RUN/app.log" "app:create_app()"
    alive "$RUN/worker.pid" || { nohup "$VENV/bin/celery" -A app.celery_app worker --loglevel=info --pool=solo \
      > "$RUN/worker.log" 2>&1 & echo $! > "$RUN/worker.pid"; }
    printf "waiting for the API on %s" "$GUNICORN_BIND"
    for _ in $(seq 1 60); do [ "$(api_code)" = 200 ] && { echo " -> 200, ready."; exit 0; }; printf "."; sleep 2; done
    echo " -> no answer in 120 s; see $RUN/app.log" >&2; exit 1
    ;;
  down)
    for p in app worker redis; do
      if alive "$RUN/$p.pid"; then kill "$(cat "$RUN/$p.pid")" && echo "$p stopped"; fi
      rm -f "$RUN/$p.pid"
    done
    ;;
  status)
    load_env
    for p in app worker redis; do alive "$RUN/$p.pid" && echo "$p: running" || echo "$p: stopped"; done
    echo "api: HTTP $(api_code)"
    ;;
  logs)
    tail -n 50 -f "$RUN/app.log" "$RUN/worker.log"
    ;;
  *) echo "usage: $0 install|up|down|status|logs" >&2; exit 2 ;;
esac
