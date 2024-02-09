`fastapi-sqlalchemy-toolkit` supports declarative sorting by model fields, as well as by fields of related models (if it is a model directly related to the main one and if these models are linked by a single foreign key). The necessary joins for sorting by fields of related models will be automatically performed.

To apply declarative sorting:
1. Define a list of fields available for filtering. The field can be a string if it is a field of the main model, or a model attribute if it is on a related model.

```python
from app.models import Parent

child_ordering_fields = (
    "title",
    "created_at",
    Parent.title,
    Parent.created_at
)
```

For each of the specified fields, sorting in ascending and descending order will be available. To sort by a field in descending order, pass its name in the query parameter starting with a hyphen (Django style). Thus, `?order_by=title` sorts by `title` in ascending order, and `?order_by=-title` sorts by `title` in descending order.

2. Pass the above-defined list to the `ordering_dep` parameter in the endpoint parameters

```python
from fastapi_sqlalchemy_toolkit import ordering_dep

@router.get("/children")
async def get_child_objects(
    session: Session,
    order_by: ordering_dep(child_ordering_fields)
) -> list[ChildListSchema]
    ...
```

3. Pass the sorting parameter as the `order_by` parameter in the `ModelManager` methods

```python
    return await child_manager.list(session=session, order_by=order_by)
```
