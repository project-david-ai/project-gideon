FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN groupadd --system gideon \
    && useradd --system \
        --gid gideon \
        --create-home \
        gideon

COPY pyproject.toml /app/pyproject.toml
COPY src /app/src

RUN python -m pip install \
    --no-cache-dir \
    --upgrade pip \
    && python -m pip install \
        --no-cache-dir \
        .

USER gideon

CMD ["python", "-m", "project_gideon"]