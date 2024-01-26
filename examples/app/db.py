from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from .config import settings

engine = create_async_engine(settings.SQLALCHEMY_DATABASE_URL, future=True, echo=False)

async_session_factory = async_sessionmaker(engine, expire_on_commit=False)
