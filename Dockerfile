# ============================================
# Stage 1: Builder (includes build tools)
# ============================================
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies (only needed during pip install)
RUN apt-get update && apt-get install -y \
    gcc \
    git \
    pkg-config \
    libcairo2-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies to /install directory.
# requirements.lock.txt is fully pinned (compiled from requirements.in by
# pip-compile inside this same base image) so builds are reproducible.
# Edit requirements.in, then regenerate - never hand-edit the lock file.
COPY requirements.lock.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.lock.txt

# Pre-download Whisper base model (will be copied to runtime stage).
# Baking it into the image is what lets containers start without network.
RUN PYTHONPATH=/install/lib/python3.11/site-packages \
    python -c "import whisper; whisper.load_model('base')"

# ============================================
# Stage 2: Runtime (slim, production-ready)
# ============================================
FROM python:3.11-slim

# Run as a non-root user. HOME must be set explicitly because Whisper,
# HuggingFace and Torch all resolve their caches from it - and the compose
# files bind-mount host directories onto these exact paths.
ENV HOME=/home/mnemos \
    PYTHONUNBUFFERED=1

RUN groupadd --gid 1000 mnemos \
    && useradd --uid 1000 --gid 1000 --home-dir ${HOME} --create-home mnemos

WORKDIR /app

# Install ONLY runtime dependencies (no build tools)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libcairo2 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Whisper cache moves off /root so the non-root user can read it.
COPY --from=builder --chown=mnemos:mnemos /root/.cache/whisper ${HOME}/.cache/whisper

# Copy application code
COPY --chown=mnemos:mnemos . .

RUN chmod +x entrypoint.sh \
    && mkdir -p ${HOME}/.cache/huggingface /app/uploads /app/archive \
    && chown -R mnemos:mnemos ${HOME}/.cache /app/uploads /app/archive

USER mnemos

EXPOSE 5000

# Entrypoint runs migrations when RUN_MIGRATIONS=true, then execs the command.
ENTRYPOINT ["./entrypoint.sh"]

CMD ["gunicorn", "-c", "gunicorn.conf.py", "app:create_app()"]
