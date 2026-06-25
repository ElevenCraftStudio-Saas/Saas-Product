# WedFind AI — backend (API + Celery worker share this image).
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System libs InsightFace / OpenCV / onnxruntime need at runtime.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 build-essential curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Upload directory — created at build time so the image always contains it.
# At runtime Docker Compose may mount a host volume over this path.
RUN mkdir -p /app/uploads && chmod -R 755 /app/uploads

COPY backend/requirements.txt ./
RUN pip install -r requirements.txt

# Pre-download the InsightFace buffalo_l model into the image so containers do
# NOT download ~300 MB on first request (deterministic cold start).
RUN python -c "from insightface.app import FaceAnalysis; FaceAnalysis(name='buffalo_l').prepare(ctx_id=-1)"

# If backend/firebase-service-account.json exists locally it is copied here.
# At runtime the app also checks GOOGLE_APPLICATION_CREDENTIALS and
# FIREBASE_SERVICE_ACCOUNT_B64 before falling back to this path.
COPY backend/ .

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -fsS http://localhost:8000/livez || exit 1

# API. The worker container overrides CMD (see docker-compose.yml).
# Celery handles CPU-intensive AI tasks (face embeddings, thumbnails,
# maintenance) so the API tier stays lightweight — a single worker is
# sufficient and avoids loading the InsightFace model four times.
CMD ["gunicorn", "app.main:app", "-k", "uvicorn.workers.UvicornWorker", \
     "-w", "1", "-b", "0.0.0.0:8000"]
