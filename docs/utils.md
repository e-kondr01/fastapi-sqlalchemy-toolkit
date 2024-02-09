### Saving user of the request

You can associate the user of the request with the object being created/updated
by passing an additional parameter to the `create` (`update`) method:
```python
@router.post("")
async def create_child(
    child_in: CreateUpdateChildSchema, session: Session, user: CurrentUser
) -> CreateUpdateChildSchema:
    return await child_manager.create(session=session, in_obj=child_in, author_id=user.id)
```

### Creating and updating objects with M2M relationships
If the model has an M2M relationship defined, using `ModelManager` allows you to pass a list of object IDs to this field.

`fastapi-sqlalchemy-toolkit` validates the existence of these objects and establishes the M2M relationship for them,
without the need to create separate endpoints for working with M2M relationships.

```python
# Let the Person and House models have an M2M relationship
from pydantic import BaseModel


class PersonCreateSchema(BaseModel):
    house_ids: list[int]

...

    in_obj = PersonCreateSchema(house_ids=[1, 2, 3])
    await person_manager.create(session, in_obj)
    # Creates a Person object and establishes an M2M relationship with Houses with ids 1, 2, and 3
```

### Filtering by list of values
One way to filter by a list of values is to pass this list as a
query parameter in the URL as a comma-separated string.
`fastapi-sqlalchemy-toolkit` provides a utility for filtering by a list of values passed as a comma-separated string:
```python
from uuid import UUID
from fastapi_sqlalchemy_toolkit.utils import comma_list_query, get_comma_list_values

@router.get("/children")
async def get_child_objects(
    session: Session,
    ids: comma_list_query = None,
) -> list[ChildListSchema]
    ids = get_comma_list_values(ids, UUID)
    return await child_manager.list(session, id=FieldFilter(ids, operator="in_"))
```
