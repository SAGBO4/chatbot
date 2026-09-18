FROM python:3.13-slim

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock .
# Installs from the fully pinned, verified lock file (see its header for how
# it's regenerated) instead of requirements.txt's open-ended ">=" ranges, so
# every build reproduces the exact dependency tree that was tested.
RUN pip install --no-cache-dir -r requirements.lock

RUN useradd -m -r appuser && mkdir -p /app/data && chown -R appuser:appuser /app
COPY --chown=appuser:appuser . .
RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
