"""
Sets up postgres connection pool.
"""

from pydantic import PostgresDsn
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

SQLALCHEMY_DATABASE_URL = str(
    PostgresDsn.build(
        scheme="postgresql+asyncpg",
        username="postgres",
        password="postgres",
        host="postgres",
        port=5432,
        path="toolkit-test",
    )
)


engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL,
    echo=False,
    connect_args={"server_settings": {"jit": "off"}},
)

async_session_factory = async_sessionmaker(engine, expire_on_commit=False)
