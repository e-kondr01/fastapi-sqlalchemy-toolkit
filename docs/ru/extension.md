# Расширение
Методы `ModelManager` легко расширить дополнительной логикой.


В первую очередь необходимо определить свой класс ModelManager:

```python
from fastapi_sqlalchemy_toolkit import ModelManager


class MyModelManager[MyModel, MyModelCreateSchema, MyModelUpdateSchema](ModelManager):
    ...
```
## Дополнительная валидация
Дополнительную валидацию можно добавить, переопределив метод `run_db_valiation`:

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

## Дополнительная бизнес логика при CRUD операциях
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

## Использование декларативных фильтров в нестандартных списочных запросах
Если необходимо получить не просто список объектов, но и какие-то другие поля (допустим, кол-во дочерних объектов)
или агрегации, но также необходима декларативная фильтрация, то можно определить метод менеджера,
вызвав в нём метод `assemble_stmt`:
```python
class MyModelManager[MyModel, MyModelCreateSchema, MyModelUpdateSchema](MyModel):
    async def get_parents_with_children_count(
        self, session: AsyncSession, **kwargs
    ) -> list[RetrieveParentWithChildrenCountSchema]:
        children_count_stmt = (
            select(func.count(Child.id))
            .filter(Child.parent_id == Parent.id)
            .scalar_subquery()
        )
        stmt = (
            select(Parent, children_count_query.label("children_count"))
        )

        # Вызываем метод для получения фильтров SQLAlchemy из аргументов методов
        # list и paginated_list
        stmt = self.assemble_stmt(stmt, **kwargs)

        result = await session.execute(query)
        result = result.unique().all()
        for i, row in enumerate(result):
            row.Parent.children_count = row.children_count
            result[i] = row.Parent
        return result
```
