# FastAPI SQLAlchemy Toolkit

**FastAPI SQLAlchemy Toolkit** — это библиотека для стека `FastAPI` + Async `SQLAlchemy`,
которая помогает решать следующие задачи:

- cнижение количества шаблонного, копипастного кода, который возникает при разработке
REST API и взаимодействии с СУБД через `SQLAlchemy`;

- автоматическая валидация значений на уровне БД при создании и изменении объектов через API.

Для этого `FastAPI SQLAlachemy Toolkit` предоставляет класс менеджера `fastapi_sqlalchemy_toolkit.ModelManager` 
для взаимодействия с моделью `SQLAlchemy`.

## Features

- Методы для CRUD-операций с объектами в БД

- Фильтрация с обработкой необязательных параметров запроса (см. раздел **Фильтрация**)

- Декларативная сортировка с помощью `ordering_depends` (см. раздел **Сортировка**)

- Валидация существования внешних ключей

- Валидация уникальных ограничений

- Упрощение CRUD-действий с M2M связями

## Установка

```bash
pip install fastapi-sqlalchemy-toolkit
```

## Quick Start

Пример использования `fastapi-sqlalchemy-toolkit` доступен в директории `examples/app`

## Инициализация ModelManager

Для использования `fastapi-sqlaclhemy-toolkit` необходимо создать экземпляр `ModelManager` для своей модели:

```python
from fastapi_sqlalchemy_toolkit import ModelManager

from .models import MyModel
from .schemas import MyModelCreateSchema, MyModelUpdateSchema

my_model_manager = ModelManager[MyModel, MyModelCreateSchema, MyModelUpdateSchema](MyModel)
```

Атрибут `default_ordering` определяет сортировку по умолчанию при получении списка объектов. В него нужно передать поле основной модели.

```python
from fastapi_sqlalchemy_toolkit import ModelManager

from .models import MyModel
from .schemas import MyModelCreateSchema, MyModelUpdateSchema

my_model_manager = ModelManager[MyModel, MyModelCreateSchema, MyModelUpdateSchema](
    MyModel, default_ordering=MyModel.title
)
```

## Методы `ModelManager`

Ниже перечислены CRUD методы, предоставляемые `ModelManager`.
Документация параметров, принимаемых методами, находится в докстрингах методов.

- `create` - создание объекта; выполняет валидацию значений полей на уровне БД
- `get` - получение объекта
- `get_or_404` - получение объекта или ошибки HTTP 404
- `exists` - проверка существования объекта
- `paginated_list` / `paginated_filter` - получение списка объектов с фильтрами и пагинацией через `fastapi_pagination`
- `list` / `filter` - получение списка объектов с фильтрами
- `count` - получение количества объектов
- `update` - обновление объекта; выполняет валидацию значений полей на уровне БД
- `delete` - удаление объекта

## Фильтрация

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

## Сортировка

`fastapi-sqlalchemy-toolkit` поддеживает декларативную сортировку по полям модели, 
а также по полям связанных моделей (если это модель, напрямую связанная с основной,
а также эти модели связывает единственный внешний ключ). При этом необходимые для сортировки по полям
связанных моделей join'ы будут сделаны автоматически.

Для применения декларативной сортировки нужно:
1. Определить поля, по которым доступна фильтрация.

Это может быть либо списком/кортежем полей основной модели:

```python
from app.models import Child

child_ordering_fields = (
    Child.title,
    Child.created_at
)
```

В таком случае, будут доступны следующий параметря для сортировки:
`title`, `-title`, `created_at`, `-created_at`.

Дефис первым символом означает направление сортировки по убыванию.

Либо можно определить маппинг строковых полей для сортировки
на соответствующие поля моделей:

```python
from app.models import Child, Parent

child_ordering_fields = (
    "title": MyModel.title,
    "parent_title": ParentModel.title
)
```

В таком случае, будут доступны следующий параметря для сортировки:
`title`, `-title`, `parent_title`, `-parent_title`.

2. В параметрах энпдоинта передать определённый выше список
в `ordering_depends`

```python
from fastapi_sqlalchemy_toolkit import ordering_depends

@router.get("/children")
async def get_child_objects(
    session: Session,
    order_by: ordering_depends(child_ordering_fields)
) -> list[ChildListSchema]
    ...
```

3. Передать параметр сортировки как параметр `order_by` в методы `ModelManager`

```python
    return await child_manager.list(session=session, order_by=order_by)
```

Если `order_by` передаётся в методы `list` или `paginated_list`,
и поле для сортировки относится к модели, напрямую связанную с основной,
то будет выполнен необходимый `join` для применения сортировки.

## Транзакции

`fastapi-sqlalchemy-toolkit` поддерживает оба подхода к работе с транзакциями `SQAlchemy`.

### Commit as you go

https://docs.sqlalchemy.org/en/20/orm/session_transaction.html#commit-as-you-go

```python
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from app.managers import my_model_manager

...

    engine = create_async_engine(
        "...",
    )
    async with async_sessionmaker(engine) as session:
        # This call produces SQL COMMIT
        created_obj = await my_model_manager.create(session, input_data)
        # This call does not produce SQL COMMIT
        await my_model_manager.update(session, created_obj, name="updated_name", commit=False)
    # Only 1st statement is persisted
```

### Begin once

https://docs.sqlalchemy.org/en/20/orm/session_transaction.html#begin-once

```python
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from app.managers import my_model_manager

...

    engine = create_async_engine(
        "...",
    )
    # Start transaction with context manager
    async with async_sessionmaker(engine) as session, session.begin():
        # This call only flushes, no SQL COMMIT yet
        created_obj = await my_model_manager.create(session, input_data)
        # This call only flushes, no SQL COMMIT yet
        await my_model_manager.update(session, created_obj, name="updated_name")
    # Everything is SQL COMMITed, if no errors occured in nested block
```

## Создание и обновление объектов

TODO...


## Расширение
Методы `ModelManager` легко расширить дополнительной логикой.


В первую очередь необходимо определить свой класс ModelManager:

```python
from fastapi_sqlalchemy_toolkit import ModelManager


class MyModelManager[MyModel, MyModelCreateSchema, MyModelUpdateSchema](ModelManager):
    ...
```
### Дополнительная валидация
Дополнительную валидацию можно добавить, переопределив метод `validate`:

```python
class MyModelManager[MyModel, MyModelCreateSchema, MyModelUpdateSchema](ModelManager):
    async def validate_parent_type(self, session: AsyncSession, validated_data: ModelDict) -> None:
        """
        Проверяет тип выбранного объекта Parent
        """
        # объект Parent с таким ID точно есть, так как это проверяется ранее в super().validate
        parent = await parent_manager.get(session, id=in_obj["parent_id"])
        if parent.type != ParentTypes.CanHaveChildren:
            raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="This parent has incompatible type",
                )
    
    async def run_db_validation(
            self,
            session: AsyncSession,
            db_obj: MyModel | None = None,
            in_obj: ModelDict | None = None,
        ) -> ModelDict:
        validated_data = await super().validate(session, db_obj, in_obj)
        await self.validate_parent_type(session, validated_data)
        return validated_data
```

### Дополнительная бизнес логика при CRUD операциях
Если при CRUD операциях с моделью необходимо выполнить какую-то дополнительную бизнес логику,
это можно сделать, переопределив соответствующие методы ModelManager:

```python
class MyModelManager[MyModel, MyModelCreateSchema, MyModelUpdateSchema](ModelManager):
    async def create(
        self, *args, background_tasks: BackgroundTasks | None = None, **kwargs
    ) -> MyModel:
    created = await super().create(*args, **kwargs)
    background_tasks.add_task(send_email, created.id)
    return created
```

Такой подход соответствует принципу "Fat Models, Skinny Views" из Django.

### Использование декларативных фильтров в нестандартных списочных запросах
Если необходимо получить не просто список объектов, но и какие-то другие поля (допустим, кол-во дочерних объектов)
или агрегации, но также необходима декларативная фильтрация, то можно новый свой метод менеджера,
вызвав в нём метод `super().get_filter_expression`:
```python
class MyModelManager[MyModel, MyModelCreateSchema, MyModelUpdateSchema](MyModel):
    async def get_parents_with_children_count(
        self, session: AsyncSession, **kwargs
    ) -> list[RetrieveParentWithChildrenCountSchema]:
        children_count_query = (
            select(func.count(Child.id))
            .filter(Child.parent_id == Parent.id)
            .scalar_subquery()
        )
        query = (
            select(Parent, children_count_query.label("children_count"))
        )

        # Вызываем метод для получения фильтров SQLAlchemy из аргументов методов
        # list и paginated_list
        query = query.filter(self.get_filter_expression(**kwargs))

        result = await session.execute(query)
        result = result.unique().all()
        for i, row in enumerate(result):
            row.Parent.children_count = row.children_count
            result[i] = row.Parent
        return result
```

## Другие полезности
### Сохранение пользователя запроса

Пользователя запроса можно задать в создаваемом/обновляемом объекте,
передав дополнительный параметр в метод `create` (`update`):
```python
@router.post("")
async def create_child(
    child_in: CreateUpdateChildSchema, session: Session, user: CurrentUser
) -> CreateUpdateChildSchema:
    return await child_manager.create(session=session, in_obj=child_in, author_id=user.id)
```

### Создание и обновление объектов с M2M связями
Если на модели определена M2M связь, то использование `ModelManager` позволяет передать в это поле список ID объектов.

`fastapi-sqlalchemy-toolkit` провалидирует существование этих объектов и установит им M2M связь,
без необходимости создавать отдельные эндпоинты для работы с M2M связями.

```python
# Пусть модели Person и House имеют M2M связь
from pydantic import BaseModel


class PersonCreateSchema(BaseModel):
    house_ids: list[int]

...

    in_obj = PersonCreateSchema(house_ids=[1, 2, 3])
    await person_manager.create(session, in_obj)
    # Создаст объект Person и установит ему M2M связь с House с id 1, 2 и 3
```

### Фильтрация по списку значений
Один из способов фильтрации по списку значений -- передать этот список в качестве
квери параметра в строку через запятую.
`fastapi-sqlalchemy-toolkit` предоставляет утилиту для фильтрации по списку значений, переданного в строку через запятую:
```python
from uuid import UUID
from fastapi_sqlalchemy_toolkit.utils import CommaSepQuery, comma_sep_q_to_list

@router.get("/children")
async def get_child_objects(
    session: Session,
    ids: CommaSepQuery = None,
) -> list[ChildListSchema]
    ids = comma_sep_q_to_list(ids, UUID)
    return await child_manager.list(session, filter_expressions={Child.id.in_: ids})
```
