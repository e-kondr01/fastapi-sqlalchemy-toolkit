from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession, AsyncTransaction

from tests.db import async_session_factory, engine
from tests.models import Base, CustomPKBase


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(scope="session")
async def connection(
    anyio_backend: str,  # noqa: ARG001 - activates AnyIO's async-fixture runner
) -> AsyncGenerator[AsyncConnection, None]:
    async with engine.connect() as connection:
        yield connection


@pytest.fixture(scope="session", autouse=True)
async def create_metadata(
    connection: AsyncConnection,
) -> AsyncGenerator[None, None]:
    await connection.run_sync(Base.metadata.create_all)
    await connection.run_sync(CustomPKBase.metadata.create_all)
    await connection.commit()

    yield

    await connection.run_sync(CustomPKBase.metadata.drop_all)
    await connection.run_sync(Base.metadata.drop_all)
    await connection.commit()


@pytest.fixture
async def transaction(
    connection: AsyncConnection,
) -> AsyncGenerator[AsyncTransaction, None]:
    async with connection.begin() as transaction:
        yield transaction


@pytest.fixture(scope="session")
async def persistent_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session


@pytest.fixture
async def session(
    connection: AsyncConnection, transaction: AsyncTransaction
) -> AsyncGenerator[AsyncSession, None]:
    """
    Фикстура с сессией SQLAlchemy, которая откатывает все внесённые изменения
    после выхода из функции-теста
    """
    async_session = AsyncSession(
        bind=connection,
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
    )

    async with async_session as session:
        yield session

    await transaction.rollback()
