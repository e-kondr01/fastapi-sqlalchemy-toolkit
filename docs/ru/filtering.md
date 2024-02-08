Для получения списка объектов с фильтрацией `fastapi_sqlalchemy_toolkit` предоставляет два метода:
`list`, который осуществляет предобработку значений, и `filter`, который не производит дополнительных обработок.
Аналогично ведут себя методы `paginated_list` и `paginated_filter`, за исключением того, что они пагинирует результат
с помощью `fastapi_pagination`.

Пусть имеются следующие модели:

```python
class Base(DeclarativeBase):
    id: Mapped[_py_uuid] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Parent(Base):
    title: Mapped[str]
    slug: Mapped[str] = mapped_column(unique=True)
    children: Mapped[list["Child"]] = relationship(back_populates="parent")


class Child(Base):
    title: Mapped[str]
    slug: Mapped[str] = mapped_column(unique=True)
    parent_id: Mapped[UUID] = mapped_column(ForeignKey("parent.id", ondelete="CASCADE"))
    parent: Mapped[Parent] = relationship(back_populates="children")
```

И менеджер:

```python
from fastapi_sqlalchemy_toolkit import ModelManager

child_manager = ModelManager[Child, CreateChildSchema, PatchChildSchema](
    Child, default_ordering=Child.title
)
```

### Простая фильтрация по точному соответствию

```python
@router.get("/children")
async def get_list(
    session: Session,
    slug: str | None = None,
) -> list[ChildListSchema]:
    return await child_manager.list(
        session,
        slug=slug,
    )
```

Запрос `GET /children` сгенерирует следующий SQL:

```SQL
SELECT child.title, child.slug, child.parent_id, child.id, child.created_at 
FROM child
```

Запрос `GET /children?slug=child-1` сгенерирует следующий SQL:

```SQL
SELECT child.title, child.slug, child.parent_id, child.id, child.created_at 
FROM child 
WHERE child.slug = :slug_1
```

По конвенции `FastAPI`, необязательные параметры запроса типизируются как `slug: str | None = None`.
При этом клиенты API обычно ожидают, что при запросе `GET /children` будут возвращены все объекты `Child`,
а не только те, у которых `slug is null`. Поэтому метод `list` (`paginated_list`) отбрасывает фильтрацию
по этому параметру, если его значение не передано.

### Более сложная фильтрация

Чтобы использовать фильтрацию не только по точному соответствию атрибуту модели,
в методах `list` и `paginated_list` можно передать параметр `filter_expressions`.

Параметр `filter_expressions` принимает словарь, в котором ключи могут быть:

1. Атрибутами основной модели (`Child.title`) 

2. Операторами атрибутов модели (`Child.title.ilike`)

3. Функциями `sqlalchemy` над атрибутами модели (`func.date(Child.created_at)`)

4. Атрибутами связанной модели (`Parent.title`). Работает в том случае, если
это модель, напрямую связанная с основной, а также если модели связывает только один внешний ключ.

Значение по ключу в словаре `filter_expressions` -- это значение,
по которому должна осуществляться фильтрация.

Пример фильтрации по **оператору** атрибута модели:

```python
@router.get("/children")
async def get_list(
    session: Session,
    title: str | None = None,
) -> list[ChildListSchema]:
    return await child_manager.list(
        session,
        filter_expressions={
            Child.title.ilike: title
        },
    )
```

Запрос `GET /children` сгенерирует следующий SQL:

```SQL
SELECT child.title, child.slug, child.parent_id, child.id, child.created_at 
FROM child
```

Запрос `GET /children?title=ch` сгенерирует следующий SQL:

```SQL
SELECT child.title, child.slug, child.parent_id, child.id, child.created_at 
FROM child 
WHERE lower(child.title) LIKE lower(:title_1)
```

Пример фильтрации по **функции `sqlalchemy`** над атрибутом модели:

```python
@router.get("/children")
async def get_list(
    session: Session,
    created_at_date: date | None = None,
) -> list[ChildListSchema]:
    return await child_manager.list(
        session,
        filter_expressions={
            func.date(Child.created_at): created_at_date
        },
    )
```

Запрос `GET /children?created_at_date=2023-11-19` сгенерирует следующий SQL:

```SQL
SELECT child.title, child.slug, child.parent_id, child.id, child.created_at 
FROM child 
WHERE date(child.created_at) = :date_1
```

Пример фильтрации по атрибуту связанной модели:

```python
@router.get("/children")
async def get_list(
    session: Session,
    parent_title: str | None = None,
) -> list[ChildListSchema]:
    return await child_manager.list(
        session,
        filter_expressions={
            Parent.title.ilike: title
        },
    )
```

Запрос `GET /children?parent_title=ch` сгенерирует следующий SQL:

```SQL
SELECT parent.title, parent.slug, parent.id, parent.created_at, 
child.title AS title_1, child.slug AS slug_1, child.parent_id, child.id AS id_1,
child.created_at AS created_at_1 
FROM child LEFT OUTER JOIN parent ON parent.id = child.parent_id 
WHERE lower(parent.title) LIKE lower(:title_1)
```

При фильтрации по полям связанных моделей через параметр `filter_expression`,
 необходимые для фильтрации `join` будут сделаны автоматически.
**Важно**: работает только для моделей, напрямую связанных с основной, и только тогда, когда
эти модели связывает единственный внешний ключ.

### Фильтрация без дополнительной обработки

Для фильтрации без дополнительной обработки в методах `list` и `paginated_list` можно
использовать параметр `where`. Значение этого параметра будет напрямую
передано в метод `.where()` экземпляра `Select` в выражении запроса `SQLAlchemy`.

```python
    non_archived_items = await item_manager.list(session, where=(Item.archived_at == None))
```

Использовать параметр `where` методов `list` и `paginated_list` имеет смысл тогда,
когда эти методы используются в списочном API эндпоинте и предобработка части параметров
запроса полезна, однако нужно также добавить фильтр без предобработок от `fastapi_sqlalchemy_toolkit`.

В том случае, когда предобработки `fastapi_sqlalchemy_toolkit` не нужны вообще, стоит использовать методы
`filter` и `paginated_filter`:

```python
    created_at = None

    items = await item_manager.filter(session, created_at=created_at)
```

```SQL
SELECT item.id, item.name, item.created_at
FROM item
WHERE itme.created is null
```

В отличие от метода `list`, метод `filter`:

1. Не игнорирует простые фильтры (`kwargs`) со значением `None`

2. Не имеет параметра `filter_expressions`, т. е. не будет выполнять `join`,
необходимые для фильтрации по полям связанных моделей.

### Фильтрация по `null` через API

Если в списочном эндпоинте API требуется, чтобы можно было как отфильтровать значение поля
по переданному значению, так и отфильтровать его по `null`, предлагается использовать параметр
`nullable_filter_expressions` методов `list` (`paginated_list`):

```python
from datetime import datetime

from fastapi_sqlalchemy_toolkit import NullableQuery

from app.managers import my_object_manager
from app.models import MyObject

@router.get("/my-objects")
async def get_my_objects(
    session: Session,
    deleted_at: datetime | NullableQuery | None = None
) -> list[MyObjectListSchema]:
    return await my_object_manager.list(
        session,
        nullable_filter_expressions={
            MyObject.deleted_at: deleted_at
        }
    )
```

Параметру с поддержкой фильтрации по `null` нужно указать возможный тип
`fastapi_sqlalchemy_toolkit.NullableQuery`.

Теперь при запросе `GET /my-objects?deleted_at=` или `GET /my-objects?deleted_at=null`
вернутся объекты `MyObject`, у которых `deleted_at IS NULL`.

### Фильтрация по обратным связям
Также в методах получения списков есть поддержка фильтрации
по обратным связям (`relationship()` в направлении один ко многим) с использованием метода `.any()`.

```python
# Если ParentModel.children -- это связь один ко многим
await parent_manager.list(session, children=[1, 2])
# Вернёт объекты Parent, у которых есть связь с ChildModel с id 1 или 2
```

### Предпосылки
Необязательный раздел с демо сокращения количества шаблонного кода при использовании `fastapi_sqlalchemy_toolkit`.

Если в эндпоинт `FastAPI` нужно добавить фильтры по значениям полей, то код будет выглядеть примерно так:

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
Как можно заметить, для реализации фильтрации необходима дубликация шаблонного кода.

В `fastapi-sqlalchemy-toolkit` этот эндпоинт выглядит так:

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
