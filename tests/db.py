"""
Sets up postgres connection pool.
"""

from pydantic import PostgresDsn
import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

load_dotenv(os.path.join(os.path.dirname(__file__), "infra/test.env"))

SQLALCHEMY_DATABASE_URL = str(
    PostgresDsn.build(
        scheme="postgresql+asyncpg",
        username=os.environ.get("POSTGRES_USER"),
        password=os.environ.get("POSTGRES_PASSWORD"),
        host=os.environ.get("POSTGRES_HOST"),
        port=int(os.environ.get("POSTGRES_PORT")),
        path=os.environ.get("POSTGRES_DB"),
    )
)


engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL,
    echo=False,
    connect_args={"server_settings": {"jit": "off"}},
)

async_session_factory = async_sessionmaker(engine, expire_on_commit=False)
