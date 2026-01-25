# Stats Compass Remote Server
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install poetry
RUN pip install poetry

# Copy dependency files and source
COPY pyproject.toml poetry.lock README.md ./
COPY stats_compass_mcp/ ./stats_compass_mcp/

# Install dependencies (no dev, no virtualenv in container)
RUN poetry config virtualenvs.create false \
    && poetry install --only=main --no-interaction --no-ansi

# Create non-root user and upload/export directories
RUN useradd -m -u 1000 appuser \
    && mkdir -p /tmp/stats-compass-uploads /tmp/stats-compass-exports \
    && chown -R appuser:appuser /app /tmp/stats-compass-uploads /tmp/stats-compass-exports
USER appuser

# Environment variables with defaults
ENV STATS_COMPASS_HOST=0.0.0.0
ENV STATS_COMPASS_PORT=8000
ENV STATS_COMPASS_MEMORY_LIMIT_MB=500
ENV STATS_COMPASS_SESSION_TTL_HOURS=24
ENV STATS_COMPASS_MAX_SESSIONS=100
ENV STORAGE_BACKEND=local
ENV LOCAL_STORAGE_PATH=/tmp/stats-compass-uploads

# Expose port
EXPOSE 8000

# Health check - verify server is listening (any response means it's up)
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -s --max-time 5 http://localhost:8000/mcp > /dev/null && exit 0 || exit 1

# Run server using new unified CLI
CMD ["stats-compass-mcp", "serve"]
