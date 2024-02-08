# FastAPI SQLAlchemy Toolkit

**FastAPI SQLAlchemy Toolkit** — a library for the `FastAPI` + Async `SQLAlchemy` stack that helps solve the following tasks:

- reducing the amount of templated, copy-pasted code that arises when developing REST APIs and interacting with databases through `SQLAlchemy`;

- automatic validation of values at the database level when creating and modifying objects through the API.

To achieve this, `FastAPI SQLAlachemy Toolkit` provides the `fastapi_sqlalchemy_toolkit.ModelManager` manager class for interacting with the `SQLAlchemy`.

## Features

- Methods for CRUD operations with objects in the database

- Filtering with optional query parameters handling (see the [Filtering](#filtering) section)

Declarative sorting using `ordering_dep` (see the [Sorting](#sorting) section)

- Validation of foreign key existence

- Validation of unique constraints

- Simplification of CRUD actions with M2M relationships

## Installation

```bash
pip install fastapi-sqlalchemy-toolkit
```

## Quick Start

Example of `fastapi-sqlalchemy-toolkit` usage is available in the `examples/app` directory


## Read More
- [ModelManager](./model_manager.md)
- [Filtering](./filtering.md)
- [Sorting](./sorting.md)
- [Extension](./extension.md)
- [Other useful features](./features.md)
