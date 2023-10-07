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

## Доступные методы `ModelManager`

Ниже перечислены CRUD методы, предоставляемые `ModelManager`.
Документация параметров, принимаемых методами, находится в докстрингах методов.

- `create` - создание объекта; выполняет валидацию значений полей на уровне БД
- `get` - получение объекта
- `get_or_404` - получение объекта или ошибки HTTP 404
- `exists` - проверка существования объекта
- `paginated_list` - получение списка объектов с фильтрами и пагинацией через `fastapi_pagination`
- `list` - получение списка объектов с фильтрами
- `count` - получение количества объектов
- `update` - обновление объекта; выполняет валидацию значений полей на уровне БД
- `delete` - удаление объекта
- `bulk_create` - создание объектов пачкой; выполняет валидацию значений полей на уровне БД
- `bulk_update` - обновление объектов пачкой; выполняет валидацию значений полей на уровне БД

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
from app.models import MyModel, MyParentModel
from app.schemas import MyObjectListSchema

router = APIRouter()
CurrentSession = Annotated[AsyncSession, Depends(get_async_session)]


@router.get("/my-objects")
async def get_my_objects(
    session: CurrentSession,
    user_id: UUID | None = None,
    name: str | None = None,
    parent_name: str | None = None,
) -> list[MyObjectListSchema]:
    stmt = select(MyModel)
    if user_id is not None:
        stmt = stmt.filter_by(user_id=user_id)
    if name is not None:
        stmt = stmt.filter(MyModel.name.ilike == name)
    if parent_name is not None:
        stmt = stmt.join(MyModel.parent)
        stmt = stmt.filter(ParentModel.name.ilike == parent_name)
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
    session: CurrentSession,
    user_id: UUID | None = None,
    name: str | None = None,
    parent_name: str | None = None,
) -> list[MyObjectListSchema]:
    return await my_object_manager.list(
        session,
        user_id=user_id,
        name=FieldFilter(name, operator="ilike"),
        parent_name=FieldFilter(parent_name, operator="ilike", model=ParentModel, alias="name"),
    )
```
### Использование FieldFilter
Дополнительные возможности декларативной фильтрации поддерживаются использованием класса `FieldFilter`.
`FieldFilter` позволяет:
- фильтровать по значениям полей связанных моделей при установке атрибута `model`. 
При этом `ModelManager` автоматически сделает необходимые join'ы, если это модель, которая напрямую связана с главной
- использовать любые методы и атрибуты полей SQLAlchemy через атрибут `operator`
- применять функции SQLAlchemy к полям (например, `date()`) через атрибут `func`

```python
from app.managers import parent_manager
from app.models import Child

from fastapi_sqlalchemy_toolkit import FieldFilter

await parent_manager.list(
    session, title=FieldFilter(child_title, model=Child, operator="ilike")
)
```

### Фильтрация по `null` и необязательные квери параметры

Для получения списка объектов в `fastapi-sqlalchemy-toolkit` могут
использоваться два метода: `list` и `filter`. Их отличие в том, что
`list` **игнорирует** параметры фильтрации со значением `None`,
в то время как `filter` **применяет** параметры фильтрации 
со значением `None` как SQL фильтр по `NULL`.


Таким образом, метод `list` подходит для использования в **API эндпоинтах**,
где зачастую нужны необязательные квери параметры. Метод `filter`
подходит для использования в качестве аналогичного метода **ORM** SQLAlchemy
(в методах менеджеров и т. п.).


Аналогичным образом работают методы `paginated_list` и `paginated_filter`.

*Примечание:* метода `list` был добавлен, чтобы сохранить конвенции FastAPI,
когда необязательные квери параметры объявляются как `q: type_ | None = None`.
При этом ожидается, что при отсутствии параметра фильтр не будет применён.

**Примеры**:

1. Эндпоинт с необязательными квери параметрами:
```python
from fastapi_sqlalchemy_toolkit import FieldFilter

from app.managers import my_object_manager

@router.get("/my-objects")
async def get_my_objects(
    session: CurrentSession,
    user_id: UUID | None = None,
    title: str | None = None
) -> list[MyObjectListSchema]:
    return await my_object_manager.list(
        session,
        user_id=user_id,
        title=FieldFilter(title, operator="icontains")
    )
```

Использование метода `list` обеспечивает, что при запросе `GET /my-objects`
без квери параметров вернутся все объекты `MyObject`, т. е. фильтры
по `user_id` и `title` не будет применён.

Аналогично работает с методом `paginated_list`.


2. Фильтрация по `null` при использовании `ModelManager` как ORM:

```python
    async def my_manager_method(self, session):
        not_deleted_objects = await my_object_manager.filter(
            session,
            deleted_at=None,
        )

        ...
```

Использование метода `filter` обеспечивает, что 
`note_deleted_objects` содержит те объекты, у которых `"deleted_at" IS NULL`.

Аналогично работает с методом `paginated_filter`.

3. Эндпоинт с возможностью фильтрации по `null` через квери параметры:

```python
from datetime import datetime

from fastapi_sqlalchemy_toolkit import FieldFilter, NullableQuery

from app.managers import my_object_manager

@router.get("/my-objects")
async def get_my_objects(
    session: CurrentSession,
    user_id: UUID | None = None,
    deleted_at: datetime | NullableQuery | None = None
) -> list[MyObjectListSchema]:
    return await my_object_manager.list(
        session,
        user_id=user_id,
        deleted_at=FieldFilter(deleted_at, nullable_q=True)
    )
```

Если требуется фильтрация значения поля по `null` через квери параметр,
то необходимо указать допустимый тип соответствующего аргумента как `fastapi_sqlalchemy_toolkit.NullableQuery`
и передать его в метод фильтрации с помощью `FieldFilter` с указанным параметрам `nullable_q=True`.

`NullableQuery` -- это пустая строка `""` или строка `"null"`


Теперь при запросе `GET /my-objects?deleted_at=` или `GET /my-objects?deleted_at=null`
вернутся объекты `MyObject`, у которых `"deleted_at" IS NULL`.

Аналогично работает с методом `paginated_list`.

### Фильтрация по обратным связям
Также в методах получения списков есть поддержка фильтрации
по обратным связям (`relationship()` в направлении один ко многим) с использованием метода `.any()`.

```python
# Если ParentModel.children -- это связь один ко многим
await parent_manager.list(session, children=[1, 2])
# Вернёт объекты Parent, у которых есть связь с ChildModel с id 1 или 2
```

## Сортировка

`fastapi-sqlalchemy-toolkit` поддеживает декларативную сортировку по полям модели, 
а также по полям связанных моделей. При этом необходимые для сортировки по полям
связанных моделей join'ы будут сделаны автоматически.

Для применения декларативной сортировки нужно:
1. Определить список полей, по которым доступна фильтрация. Поле может быть
строкой, если это поле основной модели, или атрибутом модели, если оно находится
на связанной модели.

```python
from app.models import Parent

child_ordering_fields = (
    "title",
    "created_at",
    Parent.title,
    Parent.created_at
)
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
    ...
```

3. Передать параметр сортировки как параметр `order_by` в методы `ModelManager`

```python
    return await child_manager.list(session=session, order_by=order_by)
```


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
    child_in: CreateUpdateChildSchema, session: CurrentSession, user: CurrentUser
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
from fastapi_sqlalchemy_toolkit.utils import comma_list_query, get_comma_list_values

@router.get("/children")
async def get_child_objects(
    session: CurrentSession,
    ids: comma_list_query = None,
) -> list[ChildListSchema]
    ids = get_comma_list_values(ids, UUID)
    return await child_manager.list(session, id=FieldFilter(ids, operator="in_"))
```
