# FastAPI SQLAlchemy Toolkit

---

**Документация**: [https://e-kondr01.github.io/fastapi-sqlalchemy-toolkit/ru/](https://e-kondr01.github.io/fastapi-sqlalchemy-toolkit/ru/)

---

**FastAPI SQLAlchemy Toolkit** — это библиотека для стека `FastAPI` + Async `SQLAlchemy`,
которая помогает решать следующие задачи:

- cнижение количества шаблонного, копипастного кода, который возникает при разработке
REST API и взаимодействии с СУБД через `SQLAlchemy`;

- автоматическая валидация значений на уровне БД при создании и изменении объектов через API.

## Функционал

- Методы для CRUD-операций с объектами в БД

- Фильтрация с обработкой необязательных параметров запроса (см. раздел **Фильтрация**)

- Декларативная сортировка с помощью `ordering_depends` (см. раздел **Сортировка**)

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
