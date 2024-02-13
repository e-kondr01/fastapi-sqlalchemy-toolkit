# Working with transactions

`fastapi-sqlalchemy-toolkit` supports both approaches for working with transactions in `SQLAlchemy`.

## Commit as you go

[Commit as you go SQLAlchemy Documentation](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html#commit-as-you-go)

```python
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from app.managers import my_model_manager

...

    engine = create_async_engine(
        "...",
    )
    async with async_sessionmaker(engine) as session:
        # Calling this method will perform an SQL COMMIT
        created_obj = await my_model_manager.create(session, input_data)
        # Calling this method will perform an SQL COMMIT
        await my_model_manager.update(session, created_obj, name="updated_name", commit=False)
    # Only the first call will be saved in the database
```

## Begin once

[Begin once SQLAlchemy Documentation](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html#begin-once)

```python
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from app.managers import my_model_manager

...

    engine = create_async_engine(
        "...",
    )
    # Transaction begins within the context manager
    async with async_sessionmaker(engine) as session, session.begin():
        # This call only performs a flush, without an SQL COMMIT
        created_obj = await my_model_manager.create(session, input_data)
        # This call only performs a flush, without an SQL COMMIT
        await my_model_manager.update(session, created_obj, name="updated_name")
    # If there were no exceptions in the nested block, a COMMIT is invoked, saving
    # changes from both calls
```