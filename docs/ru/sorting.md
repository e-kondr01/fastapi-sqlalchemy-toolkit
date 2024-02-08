`fastapi-sqlalchemy-toolkit` поддеживает декларативную сортировку по полям модели, 
а также по полям связанных моделей (если это модель, напрямую связанная с основной,
а также эти модели связывает единственный внешний ключ). При этом необходимые для сортировки по полям
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
    session: Session,
    order_by: ordering_dep(child_ordering_fields)
) -> list[ChildListSchema]
    ...
```

3. Передать параметр сортировки как параметр `order_by` в методы `ModelManager`

```python
    return await child_manager.list(session=session, order_by=order_by)
```

