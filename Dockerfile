FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY gauntlet ./gauntlet
COPY tasks ./tasks
RUN pip install --no-cache-dir -e .

ENTRYPOINT ["gauntlet"]
