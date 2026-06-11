FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.7.8 /uv /usr/local/bin/uv

WORKDIR /app

# Place the venv outside /app so bind-mount volume doesn't shadow it
ENV UV_PROJECT_ENVIRONMENT=/opt/venv

# Install dependencies (cached unless pyproject.toml or uv.lock changes)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy source (cache busted on any code change, but dep layer stays cached)
COPY . .

ENV PATH="/opt/venv/bin:$PATH"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
