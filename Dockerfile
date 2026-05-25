# syntax=docker/dockerfile:1
FROM mcr.microsoft.com/playwright/python:v1.50.0-noble

WORKDIR /var/task

ENV PIP_ROOT_USER_ACTION=ignore

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY mothership/ ./mothership/

ENTRYPOINT ["python3", "-m", "awslambdaric"]
CMD ["mothership.main.process_event"]
