An optional section demonstrating the reduction of boilerplate code when using `fastapi_sqlalchemy_toolkit`.

If you need to add filters based on field values in a `FastAPI` endpoint, the code would look something like this:

```python
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_async_session
from app.models import MyModel, MyParentModel
from app.schemas import MyObjectListSchema

router = APIRouter()
Session = Annotated[AsyncSession, Depends(get_async_session)]


@router.get("/my-objects")
async def get_my_objects(
    session: Session,
    user_id: UUID | None = None,
    name: str | None = None,
    parent_name: str | None = None,
) -> list[MyObjectListSchema]:
    stmt = select(MyModel)
    if user_id is not None:
        stmt = stmt.filter_by(user_id=user_id)
    if name is not None:
        stmt = stmt.filter(MyModel.name.ilike == f"%{name}%")
    if parent_name is not None:
        stmt = stmt.join(MyModel.parent)
        stmt = stmt.filter(ParentModel.name.ilike == f"%{parent_name}%")
    result = await session.execute(stmt)
    return result.scalars().all()
```
As you can see, implementing filtering requires duplicating template code.

With `fastapi-sqlalchemy-toolkit`, this endpoint looks like this:

```python
from fastapi_sqlalchemy_toolkit import FieldFilter

from app.managers import my_object_manager

@router.get("/my-objects")
async def get_my_objects(
    session: Session,
    user_id: UUID | None = None,
    name: str | None = None,
    parent_name: str | None = None,
) -> list[MyObjectListSchema]:
    return await my_object_manager.list(
        session,
        user_id=user_id,
        filter_expressions={
            MyObject.name: name,
            MyObjectParent.name: parent_name
        }
    )
```