# FastAPI SQLAlchemy Toolkit

**FastAPI SQLAlchemy Toolkit** -- это библиотека для стека `FastAPI` + Async `SQLAlchemy`,
которая призвана решить следующие задачи:

- Снижение количества шаблонного, копипастного кода, который возникает при разработке
REST API и взаимодействии с СУБД средствами `SQLAlchemy`

- Встроенная валидация значений на уровне БД

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

## Доступные методы db_crud

Ниже перечисленны доступные CRUD методы, предоставляемые `BaseCrud`.
Документация параметров, принимаемых методами, находится в докстрингах
соответствующих методов.

- `create` - создание объекта (также выполняет валидацию значений полей на уровне БД)
- `get` - получение объекта
- `get_or_404` - получение объекта или ошибки 404
- `exists` - проверка существования объекта
- `paginated_filter` - получение списка объектов с пагинацией
- `filter` - получение списка объектов
- `count` - получение количества объектов
- `update` - обновление объекта (также выполняет валидацию значений полей на уровне БД)
- `delete` - удаление объекта

## Фильтрация

Если в эндпоинт `FastAPI` нужно добавить фильтры по значениям полей, то код будет выглядеть примерно так:

```python
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
Уже видна дупликация шаблонного кода, а ведь это только строгие сравнения, и поля находятся на самой модели.

В `fastapi-sqlalchemy-toolkit` этот эндпоинт выглядит так:

```python
@router.get("/my-objects")
async def get_my_objects(
    session: CurrentSession,
    user_id: UUID | None = None,
    name: str | None = None
) -> list[MyObjectListSchema]:
    return await my_object_db.filter(session, user_id=user_id, name=name)
```

Дополнительные возможности декларативной фильтрации поддерживаются использованием класса `FieldFilter`.
`FieldFilter` позволяет:
- фильтровать по значениям полей связанных моделей при задании атрибута `model`. 
При этом db_crud автоматически сделает необходимые join'ы, если это модель, которая напрямую связана с главной
- использовать любые операторы сравнения через атрибут `operator`
- применять функции SQLAlchemy к полям (например, `date()`)

## Сортировка

`fastapi-sqlalchemy-toolkit`` поддеживает декларативную сортировку по полям модели, 
а также по полям связанных моделей. При этом необходимые для сортировки по полям
связанных моделей join'ы будут сделаны автоматически.

Для применения декларативной сортировки нужно сделать следующее:
1. Определить список полей, по которым доступна фильтрация. Поле может быть
строкой, если это поле основной модели, или атрибутом модели, если оно находится
на связанной модели.

```python
child_ordering_fields = [
    "title",
    "created_at",
    Parent.title,
    Parent.created_at
]
```

2. В параметрах энпдоинта передать определённый выше список
в `fastapi_sqlalchemy_toolkit.ordering_dep`

```python
@router.get("/children")
async def get_child_objects(
    session: CurrentSession,
    order_by: ordering_dep(child_ordering_fields)
) -> list[ChildListSchema]
```

3. Передать параметр сортировки как параметр `order_by` в функции db_crud

```python
    return await child_db.filter(session=session, order_by=order_by)
```


## Полезные примеры