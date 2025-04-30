# Install uv
FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.7.0 /uv /uvx /bin/

# Change the working directory to the app directory
WORKDIR /app

# Install dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-editable

# Copy the project into the intermediate image
ADD . /app

# Sync the project
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-editable

CMD ["uv", "run", "-m", "src"]