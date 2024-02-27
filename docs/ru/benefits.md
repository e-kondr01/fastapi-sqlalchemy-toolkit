# Предпосылки
Необязательный раздел с примером сокращения количества шаблонного кода при использовании `fastapi_sqlalchemy_toolkit`.

Если в эндпоинт `FastAPI` с использованием `SQLAlchemy`
нужно добавить фильтры по значениям полей при получении списка,
то код будет выглядеть примерно так:

```python
from uuid import UUID

from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy import select

from .deps import Session
from .models import MyModel, ParentModel
from .schemas import MyObjectListSchema


@router.get("/my-objects")
async def get_my_objects(
    session: Session,
    user_id: UUID | None = None,
    name: str | None = None,
    parent_name: str | None = None,
) -> Page[MyObjectListSchema]:
    stmt = select(MyModel)
    if user_id is not None:
        stmt = stmt.filter_by(user_id=user_id)
    if name is not None:
        stmt = stmt.filter(MyModel.name.ilike == f"%{name}%")
    if parent_name is not None:
        stmt = stmt.join(MyModel.parent)
        stmt = stmt.filter(ParentModel.name.ilike == f"%{parent_name}%")
    return await paginate(session, stmt)
```

В `fastapi-sqlalchemy-toolkit` этот эндпоинт выглядит так:

```python
from app.managers import my_object_manager

@router.get("/my-objects")
async def get_my_objects(
    session: Session,
    user_id: UUID | None = None,
    name: str | None = None,
    parent_name: str | None = None,
) -> Page[MyObjectListSchema]:
    return await my_object_manager.paginated_list(
        session,
        user_id=user_id,
        filter_expressions={
            MyObject.name: name,
            MyObjectParent.name: parent_name
        }
    )
```

Теперь рассмотрим создание объекта, который имеет FK и уникальное поле. Без `fastapi-sqlalchemy-toolkit`:

```python
@router.post("/my-objects")
async def create_my_object(
    session: Session, in_obj: MyObjectCreateSchema
) -> MyObjectListSchema:
    if in_obj.parent_id:
        parent_exists = (
            await session.execute(select(ParentModel.id).filter_by(id=in_obj.parent_id))
        ).first() is not None
        if not parent_exists:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail=f"Parent with id {in_obj.parent_id} does not exist",
            )

    slug_exists = (
        await session.execute(select(MyModel.id).filter_by(slug=in_obj.slug))
    ).first() is not None
    if slug_exists:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"MyModel with slug {in_obj.slug} already exists",
        )

    db_obj = MyModel(**in_obj.model_dump())
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj
```

С использованием `fastapi-sqlalchemy-toolkit`:

```python
@router.post("/my-objects")
async def create_my_object(
    session: Session, in_obj: MyObjectCreateSchema
) -> MyObjectListSchema:
    return await my_object_manager.create(session, in_obj=in_obj)
```

В обоих случаях, использование `fastapi-sqlalchemy-toolkit` значительно сокращает
код приложения за счёт внутренней реализации в методах `ModelManager` стандартной логики,
необходимой при создании REST API.
