# FastAPI SQLAlchemy Toolkit

- [Версия на русском](./README_ru.md)

**FastAPI SQLAlchemy Toolkit** — a library for the `FastAPI` + Async `SQLAlchemy` stack that helps solve the following tasks:

- reducing the amount of templated, copy-pasted code that arises when developing REST APIs and interacting with databases through `SQLAlchemy`;

- automatic validation of values at the database level when creating and modifying objects through the API.

To achieve this, `FastAPI SQLAlachemy Toolkit` provides the `fastapi_sqlalchemy_toolkit.ModelManager` manager class for interacting with the `SQLAlchemy`.

## Features

- Methods for CRUD operations with objects in the database

- Filtering with optional query parameters handling (see the [Filtering](#filtering) section)

Declarative sorting using `ordering_dep` (see the [Sorting](#sorting) section)

- Validation of foreign key existence

- Validation of unique constraints

- Simplification of CRUD actions with M2M relationships

## Installation

```bash
pip install fastapi-sqlalchemy-toolkit
```

## Quick Start

Example of `fastapi-sqlalchemy-toolkit` usage is available in the `examples/app` directory

## ModelManager initialization

To use `fastapi-sqlaclhemy-toolkit`, you need to create an instance of `ModelManager` for your model:

```python
from fastapi_sqlalchemy_toolkit import ModelManager

from .models import MyModel
from .schemas import MyModelCreateSchema, MyModelUpdateSchema

my_model_manager = ModelManager[MyModel, MyModelCreateSchema, MyModelUpdateSchema](MyModel)
```

The `default_ordering` attribute defines the default sorting when retrieving a list of objects. You should pass the primary model field to it.

```python
from fastapi_sqlalchemy_toolkit import ModelManager

from .models import MyModel
from .schemas import MyModelCreateSchema, MyModelUpdateSchema

my_model_manager = ModelManager[MyModel, MyModelCreateSchema, MyModelUpdateSchema](
    MyModel, default_ordering=MyModel.title
)
```

## `ModelManager` methods

Below are the CRUD methods provided by `ModelManager`. Documentation for the parameters accepted by these methods can be found in the method docstrings.

- `create` - creates an object; performs validation of field values at the database level
- `get` - retrieves an object
- `get_or_404` - retrieves an object or returns HTTP 404 error
- `exists` - checks the existence of an object
- `paginated_list` / `paginated_filter` - retrieves a list of objects with filters and pagination through `fastapi_pagination`
- `list` / `filter` - retrieves a list of objects with filters
- `count` - retrieves the count of objects
- `update` - updates an object; performs validation of field values at the database level
- `delete` - deletes an object

## Filtering

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

### Prerequisites
An optional section demonstrating the reduction of boilerplate code when using `fastapi_sqlalchemy_toolkit`.

If you need to add filters based on field values in a `FastAPI` endpoint, the code would look something like this:

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
As you can see, implementing filtering requires duplicating template code.

With `fastapi-sqlalchemy-toolkit`, this endpoint looks like this:

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

## Sorting

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


## Extension
The `ModelManager` methods can be easily extended with additional logic.


Firstly, you need to define your own `ModelManager` class:

```python
from fastapi_sqlalchemy_toolkit import ModelManager


class MyModelManager[MyModel, MyModelCreateSchema, MyModelUpdateSchema](ModelManager):
    ...
```

### Additional Validation
You can add additional validation by overriding the `validate` method:

```python
class MyModelManager[MyModel, MyModelCreateSchema, MyModelUpdateSchema](ModelManager):
    async def validate_parent_type(self, session: AsyncSession, validated_data: ModelDict) -> None:
        """
        Checks the type of the selected Parent object
        """
        # The Parent object with this ID definitely exists since this is checked earlier in super().validate
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

### Additional business logic for CRUD operations
If additional business logic needs to be executed during CRUD operations with the model,
this can be done by overriding the corresponding `ModelManager` methods:

```python
class MyModelManager[MyModel, MyModelCreateSchema, MyModelUpdateSchema](ModelManager):
    async def create(
        self, *args, background_tasks: BackgroundTasks | None = None, **kwargs
    ) -> MyModel:
    created = await super().create(*args, **kwargs)
    background_tasks.add_task(send_email, created.id)
    return created
```

This approach aligns with the "*Fat Models, Skinny Views*" principle from Django.

### Using declarative dilters in non-standard list queries
If you need to retrieve not just a list of objects but also other fields (e.g., the number of child objects)
or aggregations, and you also need declarative filtering, you can create a new manager method,
calling the `super().get_filter_expression` method within it:
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

        # Calling the method to get SQLAlchemy filters from method arguments
        # list и paginated_list
        query = query.filter(self.get_filter_expression(**kwargs))

        result = await session.execute(query)
        result = result.unique().all()
        for i, row in enumerate(result):
            row.Parent.children_count = row.children_count
            result[i] = row.Parent
        return result
```

## Other useful features
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
