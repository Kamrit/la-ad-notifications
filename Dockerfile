FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY data ./data
RUN mkdir -p /app/runtime
RUN pip install --no-cache-dir .

CMD ["python", "-m", "alliance_duel_bot"]
