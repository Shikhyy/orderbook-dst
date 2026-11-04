# Clean-room environment for judges: tests, grader validation, and grading.
#   docker build -t orderbook-dst .
#   docker run --rm orderbook-dst                       # grader validation V1-V8
#   docker run --rm orderbook-dst .venv/bin/python -m pytest -q tests
#   docker run --rm -v "$PWD/results:/app/results" orderbook-dst \
#       .venv/bin/python -m harness.run_eval --regrade results/main
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN python -m venv .venv && .venv/bin/pip install --no-cache-dir -r requirements.txt
COPY . /app
CMD [".venv/bin/python", "tools/validate_graders.py"]
