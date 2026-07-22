FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OTEL_SDK_DISABLED=true \
    CREWAI_TRACING_ENABLED=false

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

COPY config ./config
COPY knowledge ./knowledge
COPY scripts ./scripts

CMD ["python", "scripts/run_eval.py"]
