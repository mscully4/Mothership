# syntax=docker/dockerfile:1
FROM mcr.microsoft.com/playwright/python:v1.50.0-noble

WORKDIR /var/task

ENV PIP_ROOT_USER_ACTION=ignore

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./
RUN uv export --no-dev --no-hashes --frozen --no-emit-project | pip install --no-cache-dir -r /dev/stdin

COPY mothership/ ./mothership/

ENTRYPOINT ["python3", "-m", "awslambdaric"]
CMD ["mothership.main.process_event"]
