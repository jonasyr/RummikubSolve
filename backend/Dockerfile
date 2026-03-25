FROM python:3.12-slim

WORKDIR /app

# Create a non-root user for security
RUN groupadd --system app && useradd --system --gid app app

# Install dependencies first (layer-cached unless pyproject.toml changes)
COPY pyproject.toml .
RUN pip install --no-cache-dir hatchling && pip install --no-cache-dir .

# Copy application source
COPY solver/ ./solver/
COPY api/ ./api/

# Switch to non-root user
USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
