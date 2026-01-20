FROM python:3.11-slim

WORKDIR /app

# System dependencies for Whisper (ffmpeg) and building packages
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libpq-dev \
    gcc \
    git \
    pkg-config \
    libcairo2-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download Whisper base model to avoid download at runtime
# This is a good optimization for first startup speed
RUN python -c "import whisper; whisper.load_model('base')"

# Copy application code
COPY . .

# Add entrypoint script
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

# Expose port
EXPOSE 5000

# Entrypoint to run migrations
ENTRYPOINT ["./entrypoint.sh"]

# Default command
CMD ["gunicorn", "-b", "0.0.0.0:5000", "-w", "1", "--timeout", "1800", "app:create_app()"]
