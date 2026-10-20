FROM python:3.11-slim-bookworm@sha256:0a310eeecf4e1f5a0743f9a6520c90c88d089c903ca5fd283f501e3a805f5f89
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MODEL_DIR=/app/models \
    OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1
WORKDIR /app
COPY requirements-serving.txt ./
RUN python -m pip install --no-cache-dir --require-hashes -r requirements-serving.txt
COPY pyproject.toml ./
COPY src ./src
RUN python -m pip install --no-cache-dir --no-deps . \
    && groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home app
COPY models/pipeline.joblib models/metadata.json ./models/
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/readyz', timeout=3)"
CMD ["python", "-m", "uvicorn", "heart_risk.api:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]