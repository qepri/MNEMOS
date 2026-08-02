"""Gunicorn configuration.

Replaces the inline CMD flags so worker count and timeouts are set in one
deliberate place rather than being buried in the Dockerfile.
"""
import os

bind = os.getenv("GUNICORN_BIND", "0.0.0.0:5000")

# Each worker builds its own Flask app. Keep this modest: RAG requests are
# long-running and I/O-bound on the LLM, so threads carry the concurrency.
workers = int(os.getenv("GUNICORN_WORKERS", "4"))
threads = int(os.getenv("GUNICORN_THREADS", "2"))

# Long timeout: a single RAG generation against a local model can legitimately
# run for many minutes, and gunicorn must not kill it mid-stream.
timeout = int(os.getenv("GUNICORN_TIMEOUT", "1800"))
graceful_timeout = 30
keepalive = 5

accesslog = "-"
errorlog = "-"
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")

# preload_app stays off: it would load the app (and any model handles) before
# forking, which shares CUDA state across workers.
preload_app = False
