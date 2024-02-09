FROM python:3.12

WORKDIR /fastapi-sqlalchemy-toolkit

RUN pip install --upgrade pip
COPY ../requirements/base.txt .
COPY ../requirements/test.txt .
RUN pip install -r base.txt
RUN pip install -r test.txt

COPY ../fastapi_sqlalchemy_toolkit ./fastapi_sqlalchemy_toolkit
COPY ../tests ./tests

ENTRYPOINT ["/bin/sh", "-c", "pytest"]
