FROM python:3.12-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Layer caching: copy dependency files before code
COPY pyproject.toml uv.lock ./

# Pre-built site-packages (Python 3.12, glibc, x86_64) — bundled to avoid
# requiring internet access inside the container
COPY .venv/lib/python3.12/site-packages/ /usr/local/lib/python3.12/site-packages/

# Copy application code
COPY app/ ./app/
COPY rules/ ./rules/

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
