# Сортировка

`fastapi-sqlalchemy-toolkit` поддеживает декларативную сортировку по полям модели, 
а также по полям связанных моделей (если это модель, напрямую связанная с основной,
а также эти модели связывает единственный внешний ключ). При этом необходимые для сортировки по полям
связанных моделей join'ы будут сделаны автоматически.

Для применения декларативной сортировки нужно:

## Определить поля, по которым доступна фильтрация

Это может быть:

- Cписок или кортеж полей основной модели:

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

- Маппинг строковых полей для сортировки на соответствующие поля моделей:

```python
from app.models import Child, Parent

child_ordering_fields = {
    "title": MyModel.title,
    "parent_title": ParentModel.title
}
```

В таком случае, будут доступны следующий параметря для сортировки:
`title`, `-title`, `parent_title`, `-parent_title`.

## В параметрах энпдоинта передать определённый выше список
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

## Передать параметр сортировки как параметр `order_by` в методы `ModelManager`

```python
    return await child_manager.list(session=session, order_by=order_by)
```

Если `order_by` передаётся в методы `list` или `paginated_list`,
и поле для сортировки относится к модели, напрямую связанную с основной,
то будет выполнен необходимый `join` для применения сортировки.

