To retrieve a list of objects with filtering, `fastapi_sqlalchemy_toolkit` provides two methods:
`list`, which preprocesses values, and `filter`, which does not perform additional processing.
Similarly, `paginated_list` and `paginated_filter` behave the same, except they paginate the result using `fastapi_pagination`.

Let's assume the following models:

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

And manager:

```python
from fastapi_sqlalchemy_toolkit import ModelManager

child_manager = ModelManager[Child, CreateChildSchema, PatchChildSchema](
    Child, default_ordering=Child.title
)
```

### Simple exact matching filter

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

`GET /children` request will generate the following SQL:

```SQL
SELECT child.title, child.slug, child.parent_id, child.id, child.created_at 
FROM child
```

`GET /children?slug=child-1` request will generate the following SQL:

```SQL
SELECT child.title, child.slug, child.parent_id, child.id, child.created_at 
FROM child 
WHERE child.slug = :slug_1
```

Following the `FastAPI` convention, optional query parameters are typed as `slug: str | None = None`. In this case, API clients typically expect that a request to `GET /children` will return all `Child` objects, not just those with a `null` `slug`. Therefore, the `list` (`paginated_list`) method discards filtering on this parameter if its value is not provided.

### More complex filtering

To use filtering not only for exact attribute matching but also for more complex scenarios, you can pass the `filter_expressions` parameter to the `list` and `paginated_list` methods.

The `filter_expressions` parameter takes a dictionary where keys can be:

1. Attributes of the main model (`Child.title`) 

2. Model attribute operators (`Child.title.ilike`)

3. `sqlalchemy` functions on model attributes (`func.date(Child.created_at)`)

4. Attributes of the related model (`Parent.title`). It works if the model is directly related to the main model and if the models are linked by only one foreign key.

The value associated with a key in the `filter_expressions` dictionary is the value for which the filtering should occur.

An example of filtering using an **operator** on a model attribute:

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

`GET /children` request will generate the following SQL:

```SQL
SELECT child.title, child.slug, child.parent_id, child.id, child.created_at 
FROM child
```

`GET /children?title=ch` request will generate the following SQL:

```SQL
SELECT child.title, child.slug, child.parent_id, child.id, child.created_at 
FROM child 
WHERE lower(child.title) LIKE lower(:title_1)
```

Filtering example using **`sqlalchemy` function** on model attribute:

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

`GET /children?created_at_date=2023-11-19` request will generate the following SQL:

```SQL
SELECT child.title, child.slug, child.parent_id, child.id, child.created_at 
FROM child 
WHERE date(child.created_at) = :date_1
```

Filtering example on related model attribute:

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

`GET /children?parent_title=ch` request will generate the following SQL:

```SQL
SELECT parent.title, parent.slug, parent.id, parent.created_at, 
child.title AS title_1, child.slug AS slug_1, child.parent_id, child.id AS id_1,
child.created_at AS created_at_1 
FROM child LEFT OUTER JOIN parent ON parent.id = child.parent_id 
WHERE lower(parent.title) LIKE lower(:title_1)
```

When filtering by fields of related models using the `filter_expression` parameter,
the necessary `join` for filtering will be automatically performed.
**Important**: It only works for models directly related to the main model and only when
these models are linked by a single foreign key.

### Filtering without additional processing

For filtering without additional processing in the list and `paginated_list` methods,
you can use the `where` parameter. The value of this parameter will be directly
passed to the `.where()` method of the `Select` instance in the SQLAlchemy query expression.

```python
    non_archived_items = await item_manager.list(session, where=(Item.archived_at == None))
```

Using the `where` parameter in the `list` and `paginated_list` methods makes sense when
these methods are used in a list API endpoint and preprocessing of some query parameters
is useful, but you also need to add a filter without preprocessing from `fastapi_sqlalchemy_toolkit`.

In cases where `fastapi_sqlalchemy_toolkit` preprocessing is not needed at all,
you should use the `filter` and `paginated_filter` methods:

```python
    created_at = None

    items = await item_manager.filter(session, created_at=created_at)
```

```SQL
SELECT item.id, item.name, item.created_at
FROM item
WHERE itme.created is null
```

Unlike the `list` method, the `filter` method:

1. Does not ignore simple filters (`kwargs`) with a `None` value

2. Does not have the `filter_expressions` parameter, i.e., it will not perform `join`,
    necessary for filtering by fields of related models.

### Filtering by `null` via API

If in a list API endpoint, you need to be able to filter the field value
by the passed value and also filter it by `null`, it is recommended to use the
`nullable_filter_expressions` parameter of the `list` (`paginated_list`) methods:

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

For the parameter with `null` filtering support, you need to specify the possible type
`fastapi_sqlalchemy_toolkit.NullableQuery`.

Now, when requesting `GET /my-objects?deleted_at=` or `GET /my-objects?deleted_at=null`,
objects of `MyObject` with `deleted_at IS NULL` will be returned.

### Filtering by reverse relationships
Also, there is support for filtering by reverse relationships
(`relationship()` in the one-to-many direction) using the `.any()` method.

```python
# If ParentModel.children is a one-to-many relationship
await parent_manager.list(session, children=[1, 2])
# Returns Parent objects that have a relationship with ChildModel with ids 1 or 2
```
