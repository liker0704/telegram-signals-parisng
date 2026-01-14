# ==============================================================================
# Telegram Signal Translator Bot - Dockerfile
# ==============================================================================
# Multi-stage build for smaller production image
# ==============================================================================

# Stage 1: Builder
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ==============================================================================
# Stage 2: Production
# ==============================================================================
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies + fonts for PIL text rendering
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    postgresql-client \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create non-root user for security BEFORE downloading models
RUN groupadd -r signalbot && useradd -r -g signalbot -m signalbot

# Create necessary directories
RUN mkdir -p /app/src /app/logs /app/sessions /tmp/signals && \
    chown -R signalbot:signalbot /app /tmp/signals

USER root

# Copy application code
COPY --chown=signalbot:signalbot src/ ./src/
COPY --chown=signalbot:signalbot migrations/ ./migrations/
COPY --chown=signalbot:signalbot tests/ ./tests/
COPY --chown=signalbot:signalbot config/ ./config/

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

# Switch to non-root user
USER signalbot

# Health check (optional - requires health endpoint in app)
# HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
#     CMD python -c "import requests; requests.get('http://localhost:8000/health')" || exit 1

# Default command
CMD ["python", "-m", "src.main"]
