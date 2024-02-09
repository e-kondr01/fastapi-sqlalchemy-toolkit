# Транзакции

`fastapi-sqlalchemy-toolkit` поддерживает оба подхода к работе с транзакциями `SQAlchemy`.

## Commit as you go

[Документация Commit as you go SQLAlchemy](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html#commit-as-you-go)

```python
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from app.managers import my_model_manager

...

    engine = create_async_engine(
        "...",
    )
    async with async_sessionmaker(engine) as session:
        # Вызов метода сделает SQL COMMIT
        created_obj = await my_model_manager.create(session, input_data)
        # Вызов метода не сделает SQL COMMIT
        await my_model_manager.update(session, created_obj, name="updated_name", commit=False)
    # В БД сохранится только первый вызов
```

## Begin once

[Документация Begin once SQLAlchemy](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html#begin-once)

```python
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from app.managers import my_model_manager

...

    engine = create_async_engine(
        "...",
    )
    # Транзакция начинается в контекстном менеджере
    async with async_sessionmaker(engine) as session, session.begin():
        # Этот вызов выполняет только flush, без SQL COMMIT
        created_obj = await my_model_manager.create(session, input_data)
        # Этот вызов выполняет только flush, без SQL COMMIT
        await my_model_manager.update(session, created_obj, name="updated_name")
    # Если во вложенном блоке не было исключений, то вызывается COMMIT, сохраняющий
    # изменения от обоих вызовов
```