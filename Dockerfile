FROM public.ecr.aws/lambda/python:3.11 as build

LABEL maintainer="Matt Kracht" \
      email="mwkracht@gmail.com"

RUN pip install poetry==1.2.2

WORKDIR ${LAMBDA_TASK_ROOT}
COPY poetry.lock pyproject.toml lambda_function.py ${LAMBDA_TASK_ROOT}

RUN poetry config virtualenvs.create false && \
    poetry install --without dev --no-interaction --no-ansi

COPY sleeperbot ${LAMBDA_TASK_ROOT}/sleeperbot
COPY README.md ${LAMBDA_TASK_ROOT}

CMD ["lambda_function.handler"]

from build as develop

RUN poetry install --only dev
