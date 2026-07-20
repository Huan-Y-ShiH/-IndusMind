FROM python:3.11-slim

WORKDIR /app

# Install Poetry
RUN pip install poetry

# Copy project files
COPY pyproject.toml poetry.lock* ./
RUN poetry config virtualenvs.create false     && poetry install --no-interaction --no-ansi --no-root

# Copy source
COPY . .

# Expose port
EXPOSE 8001

# Run API
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8001"]
