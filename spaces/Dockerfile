# Hugging Face Docker Space — ATLAS judge sandbox (port 7860).
# This image is the submitted sandbox_link: zero-friction, no cloud account needed.
#
# It bakes the graded ranker (rank.py + core + frozen sample artifacts), the 100-line
# real stratified sample, the vendored validator, and a small FastAPI server that serves
# a static ATLAS UI + artifacts and exposes POST /reproduce, which shells the REAL
# `python rank.py ...` with sockets blocked (netguard) and a wall-clock timer.
#
# BUILDABLE WITH NO SECRETS. No key is read at build or run time for the sandbox.
#
# Build:  docker build -f spaces/Dockerfile -t atlas-space .
# Run  :  docker run --rm -p 7860:7860 atlas-space
FROM python:3.11.15-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    PYTHONHASHSEED=0 \
    APP_ROOT=/app \
    PORT=7860

WORKDIR /app

# Optional build-only CA passthrough for TLS-terminating CI proxies (empty by default).
COPY docker/build-ca.cr[t] /tmp/build-ca.crt

# Rank-time deps (numpy + sklearn) + the tiny web server.
COPY requirements-rank.txt ./requirements-rank.txt
RUN if [ -s /tmp/build-ca.crt ]; then export PIP_CERT=/tmp/build-ca.crt; fi; \
    pip install --no-cache-dir -r requirements-rank.txt \
        fastapi==0.115.6 "uvicorn[standard]==0.34.0" && rm -f /tmp/build-ca.crt

# Graded ranker code + vendored validator + the runtime socket guard.
COPY rank.py features.py reasoning.py validate_submission.py ./
COPY core/ ./core/
COPY scripts/netguard.py ./scripts/netguard.py

# The 100-line real stratified sample + matching sample-sized frozen artifacts.
COPY data/sample_candidates.jsonl ./data/sample_candidates.jsonl
COPY artifacts_sample/ ./artifacts/

# Sandbox server + static UI.
COPY spaces/server.py ./spaces/server.py
COPY spaces/static/ ./spaces/static/

EXPOSE 7860

# HF Spaces convention: run as a non-root user.
RUN useradd -m -u 10001 atlas && chown -R atlas:atlas /app
USER atlas

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request,os;urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','7860')+'/api/health').read()" || exit 1

CMD ["sh", "-c", "uvicorn spaces.server:app --host 0.0.0.0 --port ${PORT:-7860}"]
