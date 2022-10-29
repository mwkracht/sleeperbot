FROM python:3.10-bullseye

LABEL maintainer="Matt Kracht" \
      email="mwkracht@gmail.com" \
      description="Example containerized app which generates own configruation using consul-template"

RUN apt-get update && \
    apt-get install -y  \
    make

RUN pip install poetry==1.2.2

WORKDIR /app
COPY poetry.lock pyproject.toml /app/

RUN poetry config virtualenvs.create false && \
    poetry install --without dev
