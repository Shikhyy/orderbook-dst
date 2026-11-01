FROM python:3.12-slim
WORKDIR /app
COPY . /app
RUN python -m venv .venv && .venv/bin/pip install -r requirements.txt
CMD ["make", "validate"]
