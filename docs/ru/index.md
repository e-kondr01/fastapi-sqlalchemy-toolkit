# FastAPI SQLAlchemy Toolkit

**FastAPI SQLAlchemy Toolkit** — это библиотека для стека `FastAPI` + Async `SQLAlchemy`,
которая помогает решать следующие задачи:

- cнижение количества шаблонного, копипастного кода, который возникает при разработке
REST API и взаимодействии с СУБД через `SQLAlchemy`;

- автоматическая валидация значений на уровне БД при создании и изменении объектов через API.

Для этого `FastAPI SQLAlachemy Toolkit` предоставляет класс менеджера `fastapi_sqlalchemy_toolkit.ModelManager` 
для взаимодействия с моделью `SQLAlchemy`.

## Функционал

- Методы для CRUD-операций с объектами в БД

- [Фильтрация](./filtering.md) с обработкой необязательных параметров запроса

- Декларативная [сортировка](./sorting.md) с помощью `ordering_depends`

- Валидация существования внешних ключей

- Валидация уникальных ограничений

- Упрощение CRUD-действий с M2M связями

## Установка

```bash
pip install fastapi-sqlalchemy-toolkit
```

## Демонстрация

Пример использования `fastapi-sqlalchemy-toolkit` в FastAPI приложении:

[https://github.com/e-kondr01/fastapi-sqlalchemy-toolkit/tree/master/examples/app](https://github.com/e-kondr01/fastapi-sqlalchemy-toolkit/tree/master/examples/app)

## Далее
- [Использование](./usage.md)
- [Фильтрация](./filtering.md)
- [Сортировка](./sorting.md)
- [Транзакции](./transactions.md)
- [Валидация на уровне БД](./db_validation.md)
- [Расширения](./extension.md)
- [Утилиты](./utils.md)
