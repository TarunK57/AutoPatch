# AutoPatch Backend & Full-Stack Platform - Production Container
FROM python:3.11-slim AS builder

WORKDIR /app

# Install system build dependencies and git for code ingestion
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create isolated virtual environment for dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install python dependencies inside virtual environment
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    chmod -R a+rX /opt/venv

# Final Runtime Stage
FROM python:3.11-slim AS runner

WORKDIR /app

# Install runtime tools (git, curl for health checks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Allow git operations across any workspace directory safely
RUN git config --system --add safe.directory '*'

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONPATH=/app/backend
ENV PYTHONUNBUFFERED=1

# Copy backend source code, frontend assets, and documentation
COPY backend /app/backend
COPY docs /app/docs
COPY lumina /app/lumina

# Security: Create non-root application user and set permissions
RUN useradd -u 10001 -m -s /bin/bash autopatch && \
    mkdir -p /tmp/autopatch && \
    chown -R autopatch:autopatch /app /tmp/autopatch

USER autopatch

EXPOSE 8000

HEALTHCHECK --interval=20s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

CMD ["sh", "-c", "python -m uvicorn autopatch.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
