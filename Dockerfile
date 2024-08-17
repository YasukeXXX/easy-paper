FROM python:3.12.4-slim-bookworm

RUN apt-get update && apt-get install -y curl

RUN curl -sSL https://install.python-poetry.org | python -
ENV PATH /root/.local/bin:$PATH
RUN poetry config virtualenvs.create false

WORKDIR /app

COPY pyproject.toml /app/
COPY *.lock /app/
RUN poetry install

COPY . .

