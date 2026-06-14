# ── Stage 1: builder ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# Install only the non-optional runtime deps first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir --user \
        fastapi "uvicorn[standard]" pydantic python-dotenv psutil

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:3.11-slim

# Non-root user for least-privilege execution
RUN useradd --create-home --shell /bin/bash crewpit
WORKDIR /home/crewpit/app

# Copy installed packages from builder stage
COPY --from=builder /root/.local /home/crewpit/.local
ENV PATH="/home/crewpit/.local/bin:$PATH"

# Copy source
COPY --chown=crewpit:crewpit . .

# Create writable directories that the app needs
RUN mkdir -p output/runs data/logs memory && \
    chown -R crewpit:crewpit output data memory

USER crewpit

ENV PORT=8000
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["python3", "app/server.py"]
