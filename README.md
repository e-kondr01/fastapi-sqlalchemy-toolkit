# FastAPI SQLAlchemy Toolkit

**FastAPI SQLAlchemy Toolkit** — это библиотека для стека `FastAPI` + Async `SQLAlchemy`,
которая помогает решать следующие задачи:

- cнижение количества шаблонного, копипастного кода, который возникает при разработке
REST API и взаимодействии с СУБД через `SQLAlchemy`;

- валидация значений на уровне БД.

## Features

- Декларативная фильтрация с помощью `FieldFilter`, в том числе по полям связанных моделей (см. раздел **Фильтрация**)

- Декларативная сортировка с помощью `ordering_dep`, в том числе по полям связанных моделей (см. раздел **Сортировка**)

- Методы для CRUD-операций с объектами в БД

- Валидация существования внешних ключей

- Валидация уникальных ограничений

- Упрощение CRUD-действий с M2M связями

## Установка

```bash
pip install fastapi-sqlalchemy-toolkit
```

## Quick Start

Пример использования `fastapi-sqlalchemy-toolkit` доступен в директории `examples/app`

## Получение DB CRUD

Для использования `fastapi-sqlaclhemy-toolkit` необходимо создать экземпляр `BaseCRUD` для своей модели:

```python
from fastapi_sqlalchemy_toolkit import BaseCRUD

from .models import MyModel
from .schemas import MyModelCreateSchema, MyModelUpdateSchema

my_model_db = BaseCRUD[MyModel, MyModelCreateSchema, MyModelUpdateSchema](MyModel)
```

При инициализации DB CRUD также можно задать параметр `fk_mapping`, необходимый для валидации внешних ключей.
`fk_mapping` — это словарь, в котором ключи — это названия полей внешних ключей, а значения — модели SQLAlchemy, на которые эти ключи ссылаются.

```python
from fastapi_sqlalchemy_toolkit import BaseCRUD

from .models import MyModel, MyParentModel
from .schemas import MyModelCreateSchema, MyModelUpdateSchema

my_model_db = BaseCRUD[MyModel, MyModelCreateSchema, MyModelUpdateSchema](
    MyModel,
    fk_mapping={"parent_id": MyParentModel}
)
```

Атрибут `default_ordering` определяет сортировку по умолчанию при получении списков объектов. В него нужно передать поле основной модели.

```python
from fastapi_sqlalchemy_toolkit import BaseCRUD

from .models import MyModel
from .schemas import MyModelCreateSchema, MyModelUpdateSchema

my_model_db = BaseCRUD[MyModel, MyModelCreateSchema, MyModelUpdateSchema](
    MyModel,
    default_ordering=MyModel.title
)
```

## Доступные методы `BaseCRUD`

Ниже перечислены доступные CRUD методы, предоставляемые `BaseCRUD`.
Документация параметров, принимаемых методами, находится в докстрингах методов.

- `create` - создание объекта (также выполняет валидацию значений полей на уровне БД)
- `get` - получение объекта
- `get_or_404` - получение объекта или ошибки 404
- `exists` - проверка существования объекта
- `paginated_filter` - получение списка объектов с пагинацией через `fastapi_pagination`
- `filter` - получение списка объектов
- `count` - получение количества объектов
- `update` - обновление объекта (также выполняет валидацию значений полей на уровне БД)
- `delete` - удаление объекта

## Фильтрация
### Предпосылки
Если в эндпоинт `FastAPI` нужно добавить фильтры по значениям полей, то код будет выглядеть примерно так:

```python
from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.deps import get_async_session
from app.models import MyModel
from app.schemas import MyObjectListSchema


router = APIRouter()
CurrentSession = Annotated[AsyncSession, Depends(get_async_session)]

@router.get("/my-objects")
async def get_my_objects(
    session: CurrentSession,
    user_id: UUID | None = None,
    name: str | None = None
) -> list[MyObjectListSchema]:
    stmt = select(MyModel)
    if user_id is not None:
        stmt = stmt.filter_by(user_id=user_id)
    if name is not None:
        stmt = stmt.filter_by(name=name)
    result = await session.execute(stmt)
    return results.scalars().all()
```
Как можно заметить, присутствует дубликация шаблонного кода. А это только строгие сравнения, и поля находятся на основной модели.

В `fastapi-sqlalchemy-toolkit` этот эндпоинт выглядит так:

```python
from app.db_crud import my_object_db

@router.get("/my-objects")
async def get_my_objects(
    session: CurrentSession,
    user_id: UUID | None = None,
    name: str | None = None
) -> list[MyObjectListSchema]:
    return await my_object_db.filter(session, user_id=user_id, name=name)
```
### Использование FieldFilter
Дополнительные возможности декларативной фильтрации поддерживаются использованием класса `FieldFilter`.
`FieldFilter` позволяет:
- фильтровать по значениям полей связанных моделей при установке атрибута `model`. 
При этом `BaseCRUD` автоматически сделает необходимые join'ы, если это модель, которая напрямую связана с главной
- использовать любые операторы сравнения через атрибут `operator`
- применять функции SQLAlchemy к полям (например, `date()`) через атрибут `func`

```python
from fastapi_sqlalchemy_toolkit import FieldFilter
from app.db_crud import parent_db
from app.models import Child

await parent_db.filter(session, child_title=FieldFilter(value=child_title, model=Child, operator="ilike"))
```
### Фильтрация по обратным связям
Также в методах `filter` и `paginated_filter` есть поддержка фильтрации
по обратным связям (`relationship()` в направлении один ко многим) с использованием метода `.any()`.

```python
# Если Parent.children -- это связь один ко многим
await parent_db.filter(session, children=[1, 2])
# Вернёт объекты Parent, у которых есть связь с Child с id 1 или 2
```
### Фильтрация по null
Для того чтобы осуществить фильтрацию по `null`, квери параметр должен принимать
значения из `fastapi_sqlalchemy_toolkit.NullableQuery`:

```python
from fastapi_sqlalchemy_toolkit import NullableQuery

@router.get("")
async def get_children(
    session: CurrentSession,
    title: NullableQuery | UUID | None = None,
) -> Page[ChildRetrieveSchema]:
```
`NullableQuery` это пустая строка. То есть запрос с фильтрацией по `title == None` должен выглядеть так:
`GET /children?title=`

*Почему так?*


При запросе `GET /children?title=alex` ожидается, что будут возвращены
объекты с `title == alex`, но при GET `/children` мы не ожидаем, что будут возвращены
объекты с `title == None`.

Если в эндпоинте FastAPI определён необязательный квери параметр, и он не передан
в запросе, то значение этого параметра будет равно `None`. Чтобы не возникала описанная выше некорректная фильтрация, фильтр
в `filter` и `paginated_filter` не будет применён, если значение параметра равно `None`.

## Сортировка

`fastapi-sqlalchemy-toolkit` поддеживает декларативную сортировку по полям модели, 
а также по полям связанных моделей. При этом необходимые для сортировки по полям
связанных моделей join'ы будут сделаны автоматически.

Для применения декларативной сортировки нужно сделать следующее:
1. Определить список полей, по которым доступна фильтрация. Поле может быть
строкой, если это поле основной модели, или атрибутом модели, если оно находится
на связанной модели.

```python
from app.models import Parent

child_ordering_fields = [
    "title",
    "created_at",
    Parent.title,
    Parent.created_at
]
```

Для каждого из указаных полей будет доступна сортировка по возрастанию и убыванию.
Чтобы сортировать по полю по убыванию, нужно в квери параметре сортировки
передать его название, начиная с дефиса (Django style).
Таким образом, `?order_by=title` сортирует по `title` по возрастанию,
а `?order_by=-title` сортирует по `title` по убыванию.

2. В параметрах энпдоинта передать определённый выше список
в `ordering_dep`

```python
from fastapi_sqlalchemy_toolkit import ordering_dep

@router.get("/children")
async def get_child_objects(
    session: CurrentSession,
    order_by: ordering_dep(child_ordering_fields)
) -> list[ChildListSchema]
```

3. Передать параметр сортировки как параметр `order_by` в методы `BaseCRUD`

```python
    return await child_db.filter(session=session, order_by=order_by)
```


## Расширение
Методы `BaseCRUD` легко расширить дополнительной логикой.


В первую очередь необходимо определить свой класс DB CRUD, унаследовав его от `BaseCRUD`

```python
from fastapi_sqlalchemy_toolkit import BaseCRUD


class MyModelCRUDB[MyModel, MyModelCreateSchema, MyModelUpdateSchema](BaseCRUD):
    ...
```
### Дополнительная валидация
Дополнительную валидацию можно добавить, переопределив метод `validate`:

```python
class MyModelCRUDB[MyModel, MyModelCreateSchema, MyModelUpdateSchema](BaseCRUD):
    async def validate_parent_type(self, session: AsyncSession, validated_data: ModelDict) -> None:
        """
        Проверяет тип выбранного объекта Parent
        """
        # объект Parent с таким ID точно есть, так как это проверяется ранее в super().validate
        parent = await parent_db.get(session, id=in_obj["parent_id"])
        if parent.type != ParentTypes.CanHaveChildren:
            raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="This parent has incompatible type",
                )
    
    async def run_db_validation(
            self,
            session: AsyncSession,
            db_obj: ModelType | None = None,
            in_obj: ModelDict | None = None,
        ) -> ModelDict:
        validated_data = await super().validate(session, db_obj, in_obj)
        await self.validate_parent_type(session, validated_data)
        return validated_data
```
### Использование декларативных фильтров в нестандартных списочных запросах
Если необходимо получить не просто список объектов, но и какие-то другие поля (допустим, кол-во дочерних объектов)
или агрегации, но также необходима декларативная фильтрация, то можно определить свой метод DB CRUD,
вызвав в нём метод `super().get_filter_expression`:
```python
class MyModelCRUDB[MyModel, MyModelCreateSchema, MyModelUpdateSchema](MyModel):
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
        # filter и paginated_filter BaseCRUD
        query = query.filter(self.get_filter_expression(**kwargs))

        result = await session.execute(query)
        result = result.unique().all()
        for row in result:
            row.Parent.children_count = row.children_count
        return [row.Parent for row in result]
```

## Другие полезности
### Сохранение пользователя запроса

Задать в создаваемом объекте пользователя запроса можно, передав дополнительный параметр методу `create` (аналогично с `update`)
```python
@router.post("")
async def create_child(
    child_in: CreateUpdateChildSchema, session: CurrentSession, user: CurrentUser
) -> CreateUpdateChildSchema:
    return await child_db.create(session=session, in_obj=child_in, author_id=user.id)
```

### Создание и обновление объектов с M2M связями
Если на модели определена M2M связь, то использование `BaseCRUD` позволяет передать в это поле список ID объектов.

`fastapi-sqlalchemy-toolkit` провалидирует существование этих объектов и установит им M2M связь, без необходимости создавать отдельные эндпоинты для работы с M2M связями.
