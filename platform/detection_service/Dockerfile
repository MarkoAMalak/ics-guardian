# ---- ICS Anomaly Detection Service -----------------------------------------
# Multi-stage, non-root, slim. Built and scanned in the DevSecOps pipeline.

FROM python:3.11-slim AS base

# Security & reproducibility hygiene
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install deps first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code
COPY model.py app.py auth.py ./
COPY web/ ./web/
# Artifacts are mounted at runtime (-v ./artifacts:/app/artifacts) or COPY'd in a
# release image. The service starts even if they are absent (health stays green).
COPY artifacts/ ./artifacts/

# Drop privileges — never run the service as root
RUN mkdir -p /app/data \
    && useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Container-level healthcheck used by compose / k8s
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health').status==200 else 1)"

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
