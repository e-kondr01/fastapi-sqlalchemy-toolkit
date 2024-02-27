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

### Using declarative filters in non-standard list queries
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
