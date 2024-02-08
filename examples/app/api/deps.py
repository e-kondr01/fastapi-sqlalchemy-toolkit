from typing import Annotated, AsyncGenerator

from app.db import async_session_factory
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async_session = async_session_factory()  # type: ignore
    async with async_session:
        yield async_session


Session = Annotated[AsyncSession, Depends(get_async_session)]
