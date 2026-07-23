FROM python:3.11-slim

WORKDIR /app

# Install poetry
RUN pip install --no-cache-dir poetry==1.8.2

# Copy dependency files
COPY pyproject.toml poetry.lock* ./

# Install dependencies (no dev)
RUN poetry config virtualenvs.create false \
    && poetry install --only main --no-interaction --no-ansi

# Copy application code
COPY . .

# Expose gateway port
EXPOSE 8003

# Start FastAPI with uvicorn
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8003"]
