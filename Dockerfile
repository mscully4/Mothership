# syntax=docker/dockerfile:1
FROM public.ecr.aws/lambda/python:3.12

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./
RUN uv export --no-dev --no-hashes --frozen --no-emit-project | pip install --no-cache-dir -r /dev/stdin

COPY mothership/ ${LAMBDA_TASK_ROOT}/mothership/

CMD ["mothership.main.process_event"]
