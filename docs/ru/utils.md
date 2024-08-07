# Другие утилиты
## Сохранение пользователя запроса

Пользователя запроса можно задать в создаваемом/обновляемом объекте,
передав дополнительный параметр в метод `create` (`update`):
```python
@router.post("")
async def create_child(
    child_in: CreateUpdateChildSchema, session: Session, user: User
) -> CreateUpdateChildSchema:
    return await child_manager.create(session=session, in_obj=child_in, author_id=user.id)
```

## Создание и обновление объектов с M2M связями
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

## Фильтрация по списку значений
Один из способов фильтрации по списку значений -- передать этот список в качестве
квери параметра в строку через запятую.
`fastapi-sqlalchemy-toolkit` предоставляет утилиту для фильтрации по списку значений, переданного в строку через запятую:
```python
from uuid import UUID
from fastapi_sqlalchemy_toolkit.utils import comma_list_query, get_comma_list_values

@router.get("/children")
async def get_child_objects(
    session: Session,
    ids: comma_list_query = None,
) -> list[ChildListSchema]
    ids = get_comma_list_values(ids, UUID)
    return await child_manager.list(
        session,
        filter_expressions={
            Child.id.in_: ids
        }
    )
```
