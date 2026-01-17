# ==============================================================================
# Telegram Signal Translator Bot - Dockerfile
# ==============================================================================
# Multi-stage build with uv for fast dependency management
# ==============================================================================

# Stage 1: Builder
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies into virtual environment
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
RUN uv sync --frozen --no-dev --no-install-project

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
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Create non-root user for security
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

# Default command
CMD ["python", "-m", "src.main"]
