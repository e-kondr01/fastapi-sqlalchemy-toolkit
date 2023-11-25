from typing import Any, Callable, Generic, Iterable, List, Type, TypeVar

from fastapi import HTTPException, status
from fastapi_pagination.bases import AbstractPage, AbstractParams
from fastapi_pagination.ext.sqlalchemy import paginate
from pydantic import BaseModel
from sqlalchemy import Row, UniqueConstraint, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase, contains_eager, load_only
from sqlalchemy.orm.attributes import InstrumentedAttribute
from sqlalchemy.orm.relationships import Relationship
from sqlalchemy.sql import Select
from sqlalchemy.sql.elements import UnaryExpression
from sqlalchemy.sql.functions import Function
from sqlalchemy.sql.selectable import Exists

from .filters import null_query_values
from .ordering import OrderingField

ModelType = TypeVar("ModelType", bound=DeclarativeBase)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)
ModelDict = dict[str, Any]


def sqlalchemy_model_to_dict(model: ModelType) -> dict:
    db_obj_dict = model.__dict__.copy()
    del db_obj_dict["_sa_instance_state"]
    return db_obj_dict


class ModelManager(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    def __init__(
        self,
        model: Type[ModelType],
        default_ordering: InstrumentedAttribute | UnaryExpression | None = None,
    ) -> None:
        """
        Создание экземпляра ModelManager под конкретную модель.

        :param model: модель SQLAlchemy

        :param default_ordering: поле модели, по которому должна выполняться
        сортировка по умолчанию
        """
        self.model = model
        self.default_ordering = default_ordering

        # str() of FK attr to related model
        # "parent_id": <class app.models.parent.Parent>
        # Используется для валидации существования FK при создании/обновлении объекта
        self.fk_name_to_model: dict[str, Type[ModelType]] = {}

        self.unique_constraints: List[List[str]] = []
        if hasattr(self.model, "__table_args__"):
            for table_arg in self.model.__table_args__:
                if isinstance(table_arg, UniqueConstraint):
                    if table_arg.columns.keys():
                        self.unique_constraints.append(table_arg.columns.keys())
                    else:
                        self.unique_constraints.append(table_arg._pending_colargs)

        self.reverse_relationships: dict[str, Type[ModelType]] = {}
        self.m2m_relationships: dict[str, Type[ModelType]] = {}
        # Model to related attr
        # Parent : Child.parent
        # Используется при составлении join'ов для фильтрации и сортировки
        self.models_to_relationship_attrs: dict[
            Type[ModelType], InstrumentedAttribute
        ] = {}

        attr: InstrumentedAttribute
        for attr_name, attr in self.model.__dict__.items():
            # Перебираем только атрибуты модели
            if not attr_name.startswith("_"):
                # Обрабатываем связи
                if hasattr(attr, "prop") and isinstance(attr.prop, Relationship):
                    self.models_to_relationship_attrs[attr.prop.mapper.class_] = attr
                    if attr.prop.collection_class == list:
                        # Выбираем обратные связи (ManyToOne, ManyToMany)
                        self.reverse_relationships[attr_name] = attr.prop.mapper.class_
                    else:
                        # Выбираем OneToMany связи
                        self.fk_name_to_model[
                            str(attr.expression.right).split(".")[1]
                        ] = attr.prop.mapper.class_
                    # Выбираем  ManyToMany связи
                    if getattr(attr.prop, "secondary") is not None:
                        self.m2m_relationships[attr_name] = attr.prop.mapper.class_

    ##################################################################################
    # Public API
    ##################################################################################

    async def create(
        self,
        session: AsyncSession,
        in_obj: CreateSchemaType | None = None,
        refresh_attribute_names: Iterable[str] | None = None,
        commit: bool = True,
        **attrs: Any,
    ) -> ModelType:
        """
        Создание экземпляра модели и сохранение в БД.
        Также выполняет валидацию на уровне БД.

        :param session: сессия SQLAlchemy

        :param in_obj: модель Pydantic для создания объекта

        :param refresh_attribute_names: названия полей, которые нужно обновить
        (может использоваться для подгрузки связанных полей)

        :param commit: нужно ли вызывать `session.commit()`

        :param attrs: дополнительные значения полей создаваемого экземпляра
        (какие-то поля можно установить напрямую,
        например, пользователя запроса)

        :returns: созданный экземпляр модели
        """
        if in_obj:
            create_data = in_obj.model_dump()
        else:
            create_data = {}

        create_data.update(attrs)
        await self.run_db_validation(session, in_obj=create_data)
        db_obj = self.model(**create_data)
        session.add(db_obj)
        if commit:
            await session.commit()
            await session.refresh(db_obj, attribute_names=refresh_attribute_names)
        return db_obj

    async def get(
        self,
        session: AsyncSession,
        options: List[Any] | Any | None = None,
        order_by: OrderingField | None = None,
        where: Any | None = None,
        select_: Select | None = None,
        **simple_filters: Any,
    ) -> ModelType | Row | None:
        """
        Получение одного экземпляра модели при существовании

        :param session: сессия SQLAlchemy

        :param options: параметры для метода .options() загрузчика SQLAlchemy

        :param order_by: поле для сортировки (экземпляр OrderingField)

        :param where: выражение, которое будет передано в метод .where() SQLAlchemy

        :param select_: объект Select для SQL запроса. Если передан, то метод вернёт
        экземпляр Row, а не ModelType.
        Примечание: фильтрация и сортировка по связанным моделям скорее всего
        не будут работать вместе с этим параметром.

        :param simple_filters: параметры для фильтрации по точному соответствию,
        аналогично методу .filter_by() SQLAlchemy

        :returns: экземпляр модели, Row или None, если подходящего нет в БД
        """
        stmt = self.assemble_stmt(select_, order_by, options, where, **simple_filters)

        result = await session.execute(stmt)
        if select_ is None:
            return result.scalars().first()
        return result.first()

    async def get_or_404(
        self,
        session: AsyncSession,
        options: List[Any] | Any | None = None,
        order_by: OrderingField | None = None,
        where: Any | None = None,
        select_: Select | None = None,
        **simple_filters: Any,
    ) -> ModelType | Row:
        """
        Получение одного экземпляра модели или возвращение HTTP ответа 404.

        :param session: сессия SQLAlchemy

        :param options: параметры для метода .options() загрузчика SQLAlchemy

        :param order_by: поле для сортировки (экземпляр OrderingField)

        :param where: выражение, которое будет передано в метод .where() SQLAlchemy

        :param select_: объект Select для SQL запроса. Если передан, то метод вернёт
        экземпляр Row, а не ModelType.

        :param simple_filters: параметры для фильтрации по точному соответствию,
        аналогично методу .filter_by() SQLAlchemy

        :returns: экземпляр модели или Row

        :raises: fastapi.HTTPException 404
        """

        db_obj = await self.get(
            session,
            options=options,
            order_by=order_by,
            where=where,
            select_=select_,
            **simple_filters,
        )
        attrs_str = ", ".join(
            [f"{key}={value}" for key, value in simple_filters.items()]
        )
        if not db_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{self.model.__tablename__} with {attrs_str} not found",
            )
        return db_obj

    async def exists(
        self,
        session: AsyncSession,
        options: List[Any] | Any | None = None,
        order_by: OrderingField | None = None,
        where: Any | None = None,
        **simple_filters: Any,
    ) -> bool:
        """
        Проверка существования экземпляра модели.

        :param session: сессия SQLAlchemy

        :param options: параметры для метода .options() загрузчика SQLAlchemy

        :param order_by: поле для сортировки (экземпляр OrderingField)

        :param where: выражение, которое будет передано в метод .where() SQLAlchemy

        :param simple_filters: параметры для фильтрации по точному соответствию,
        аналогично методу .filter_by() SQLAlchemy

        :returns: True если объект существует, иначе False
        """
        stmt = self.assemble_stmt(
            select(self.model.id), order_by, options, where, **simple_filters
        )

        result = await session.execute(stmt)
        return result.first() is not None

    async def paginated_filter(
        self,
        session: AsyncSession,
        pagination_params: AbstractParams,
        order_by: OrderingField | None = None,
        options: List[Any] | Any | None = None,
        where: Any | None = None,
        select_: Select | None = None,
        **simple_filters: Any,
    ) -> AbstractPage[ModelType | Row]:
        """
        Получение списка объектов с фильтрами и пагинацией.

        :param session: сессия SQLAlchemy

        :pagination_params: параметры пагинации из fastapi_pagination

        :param order_by: поле для сортировки (экземпляр OrderingField)

        :param options: параметры для метода .options() загрузчика SQLAlchemy

        :param where: выражение, которое будет передано в метод .where() SQLAlchemy

        :param select_: объект Select для SQL запроса. Если передан, то метод вернёт
        страницу Row, а не ModelType.

        :param simple_filters: параметры для фильтрации по точному соответствию,
        аналогично методу .filter_by() SQLAlchemy

        :returns: пагинированный список объектов или Row
        """
        stmt = self.assemble_stmt(select_, order_by, options, where, **simple_filters)
        return await paginate(session, stmt, pagination_params)

    async def paginated_list(
        self,
        session: AsyncSession,
        pagination_params: AbstractParams,
        order_by: OrderingField | None = None,
        filter_expressions: dict[InstrumentedAttribute | Callable, Any] | None = None,
        nullable_filter_expressions: dict[InstrumentedAttribute | Callable, Any]
        | None = None,
        options: List[Any] | Any | None = None,
        where: Any | None = None,
        select_: Select | None = None,
        **simple_filters: Any,
    ) -> AbstractPage[ModelType | Row]:
        """
        Получение списка объектов с фильтрами и пагинацией.
        Пропускает фильтры, значения которых None.

        :param session: сессия SQLAlchemy

        :pagination_params: параметры пагинации из fastapi_pagination

        :param order_by: поле для сортировки (экземпляр OrderingField)

        :param filter_expressions: словарь, отображающий поля для фильтрации
        на их значения. Фильтрация по None не применяется. См. раздел "фильтрация"
        в документации.

        :param nullable_filter_expressions: словарь, отображающий поля для фильтрации
        на их значения. Фильтрация по None применятеся, если значение
        в fastapi_sqlalchemy_toolkit.NullableQuery. См. раздел "фильтрация"
        в документации.

        :param options: параметры для метода .options() загрузчика SQLAlchemy

        :param where: выражение, которое будет передано в метод .where() SQLAlchemy

        :param select_: объект Select для SQL запроса. Если передан, то метод вернёт
        страницу Row, а не ModelType.
        Примечание: фильтрация и сортировка по связанным моделям скорее всего
        не будет работать вместе с этим параметром.

        :param simple_filters: параметры для фильтрации по точному соответствию,
        аналогично методу .filter_by() SQLAlchemy

        :returns: пагинированный список объектов или Row
        """
        if filter_expressions is None:
            filter_expressions = {}
        if nullable_filter_expressions is None:
            nullable_filter_expressions = {}
        self.remove_optional_filter_bys(simple_filters)
        self.handle_filter_expressions(filter_expressions)
        self.handle_nullable_filter_expressions(nullable_filter_expressions)
        filter_expressions = filter_expressions | nullable_filter_expressions

        stmt = self.assemble_stmt(select_, order_by, options, where, **simple_filters)
        stmt = self.get_joins(
            stmt,
            options=options,
            order_by=order_by,
            filter_expressions=filter_expressions,
        )

        for filter_expression, value in filter_expressions.items():
            if isinstance(filter_expression, InstrumentedAttribute) or isinstance(
                filter_expression, Function
            ):
                stmt = stmt.filter(filter_expression == value)
            else:
                stmt = stmt.filter(filter_expression(value))

        return await paginate(session, stmt, pagination_params)

    async def filter(
        self,
        session: AsyncSession,
        order_by: OrderingField | None = None,
        options: List[Any] | Any | None = None,
        where: Any | None = None,
        unique: bool = False,
        select_: Select | None = None,
        **simple_filters: Any,
    ) -> List[ModelType] | List[Row]:
        """
        Получение списка объектов с фильтрами

        :param session: сессия SQLAlchemy

        :param order_by: поле для сортировки (экземпляр OrderingField)

        :param options: параметры для метода .options() загрузчика SQLAlchemy

        :param where: выражение, которое будет передано в метод .where() SQLAlchemy

        :param unique: определяет необходимость вызова метода .unique()
        у результата SQLAlchemy

        :param select_: объект Select для SQL запроса. Если передан, то метод вернёт
        список Row, а не ModelType.

        :param simple_filters: параметры для фильтрации по точному соответствию,
        аналогично методу .filter_by() SQLAlchemy

        :returns: список объектов или Row
        """
        stmt = self.assemble_stmt(select_, order_by, options, where, **simple_filters)
        result = await session.execute(stmt)

        if select_ is None:
            if unique:
                return result.scalars().unique().all()
            return result.scalars().all()
        return result.all()

    async def list(
        self,
        session: AsyncSession,
        order_by: OrderingField | None = None,
        filter_expressions: dict[InstrumentedAttribute | Callable, Any] | None = None,
        nullable_filter_expressions: dict[InstrumentedAttribute | Callable, Any]
        | None = None,
        options: List[Any] | Any | None = None,
        where: Any | None = None,
        unique: bool = False,
        select_: Select | None = None,
        **simple_filters: Any,
    ) -> List[ModelType] | List[Row]:
        """
        Получение списка объектов с фильтрами.
        Пропускает фильтры, значения которых None.

        :param session: сессия SQLAlchemy

        :param order_by: поле для сортировки (экземпляр OrderingField)

        :param filter_expressions: словарь, отображающий поля для фильтрации
        на их значения. Фильтрация по None не применяется. См. раздел "фильтрация"
        в документации.

        :param nullable_filter_expressions: словарь, отображающий поля для фильтрации
        на их значения. Фильтрация по None применятеся, если значение
        в fastapi_sqlalchemy_toolkit.NullableQuery. См. раздел "фильтрация"
        в документации.

        :param options: параметры для метода .options() загрузчика SQLAlchemy

        :param where: выражение, которое будет передано в метод .where() SQLAlchemy

        :param unique: определяет необходимость вызова метода .unique()
        у результата SQLAlchemy

        :param select_: объект Select для SQL запроса. Если передан, то метод вернёт
        список Row, а не ModelType.
        Примечание: фильтрация и сортировка по связанным моделям скорее всего
        не будут работать вместе с этим параметром.

        :param simple_filters: параметры для фильтрации по точному соответствию,
        аналогично методу .filter_by() SQLAlchemy

        :returns: список объектов или Row
        """
        if filter_expressions is None:
            filter_expressions = {}
        if nullable_filter_expressions is None:
            nullable_filter_expressions = {}
        self.remove_optional_filter_bys(simple_filters)
        self.handle_filter_expressions(filter_expressions)
        self.handle_nullable_filter_expressions(nullable_filter_expressions)
        filter_expressions = filter_expressions | nullable_filter_expressions

        stmt = self.assemble_stmt(select_, order_by, options, where, **simple_filters)
        stmt = self.get_joins(
            stmt,
            options=options,
            order_by=order_by,
            filter_expressions=filter_expressions,
        )

        for filter_expression, value in filter_expressions.items():
            if isinstance(filter_expression, InstrumentedAttribute):
                stmt = stmt.filter(filter_expression == value)
            else:
                stmt = stmt.filter(filter_expression(value))

        result = await session.execute(stmt)

        if select_ is None:
            if unique:
                return result.scalars().unique().all()
            return result.scalars().all()
        return result.all()

    async def count(
        self,
        session: AsyncSession,
        options: List[Any] | Any | None = None,
        order_by: OrderingField | None = None,
        where: Any | None = None,
        **simple_filters: Any,
    ) -> int:
        """
        Возвращает количество экземпляров модели по данным фильтрам.

        :param session: сессия SQLAlchemy

        :param options: параметры для метода .options() загрузчика SQLAlchemy

        :param order_by: поле для сортировки (экземпляр OrderingField)

        :param where: выражение, которое будет передано в метод .where() SQLAlchemy

        :param simple_filters: параметры для фильтрации по точному соответствию,
        аналогично методу .filter_by() SQLAlchemy

        :returns: количество объектов по переданным фильтрам
        """
        stmt = self.assemble_stmt(
            select(func.count(self.model.id)),
            order_by,
            options,
            where,
            **simple_filters,
        )
        result = await session.execute(stmt)
        return result.scalars().first() or 0

    async def update(
        self,
        session: AsyncSession,
        db_obj: ModelType,
        in_obj: UpdateSchemaType | None = None,
        refresh_attribute_names: Iterable[str] | None = None,
        commit: bool = True,
        exclude_unset: bool = True,
        **attrs: Any,
    ) -> ModelType:
        """
        Обновление экземпляра модели в БД.
        Также выполняет валидацию на уровне БД.

        :param session: сессия SQLAlchemy

        :param db_obj: обновляемый объект

        :param in_obj: модель Pydantic для обновления значений полей объекта

        :param attrs: дополнительные значения обновляемых полей
        (какие-то поля можно установить напрямую,
        например, пользователя запроса)

        :param refresh_attribute_names: названия полей, которые нужно обновить
        (может использоваться для подгрузки связанных полей)

        :param commit: нужно ли вызывать `session.commit()`

        :param exclude_unset: передаётся в метод `.model_dump()` Pydantic модели.
        При использовании метода в PATCH-запросах имеет смысл оставлять его True
        для изменения только переданных полей; при PUT-запросах имеет смысл
        передавать False, чтобы установить дефолтные значения полей, заданные
        в модели Pydantic.

        :returns: обновлённый экземпляр модели
        """
        if in_obj:
            update_data = in_obj.model_dump(exclude_unset=exclude_unset)
        else:
            update_data = {}

        update_data.update(attrs)
        await self.run_db_validation(session, db_obj=db_obj, in_obj=update_data)
        for field in update_data:
            setattr(db_obj, field, update_data[field])
        session.add(db_obj)
        if commit:
            await session.commit()
            await session.refresh(db_obj, attribute_names=refresh_attribute_names)
        return db_obj

    async def delete(
        self, session: AsyncSession, db_obj: ModelType, commit: bool = True
    ) -> ModelType | None:
        """
        Удаление экземпляра модели из БД.

        :param session: сессия SQLAlchemy

        :param db_obj: удаляемый объект

        :param commit: нужно ли вызывать `session.commit()`
        """
        await session.delete(db_obj)
        if commit:
            await session.commit()
        return db_obj

    async def bulk_create(
        self,
        session: AsyncSession,
        in_objs: List[CreateSchemaType | dict],
        commit: bool = True,
        **attrs: Any,
    ) -> List[ModelType]:
        """
        Создание экземпляров модели и сохранение в БД пачкой.
        Также выполняет валидацию на уровне БД.

        :param session: сессия SQLAlchemy

        :param in_objs: список значений полей создаваемых экземпляров модели

        :param commit: нужно ли вызывать `session.commit()`

        :param attrs: дополнительные значения полей создаваемого экземпляра
        (чтобы какие-то поля можно было установить напрямую из кода,
        например, пользователя запроса)

        :returns: список созданных экземпляров модели
        """
        objs = []
        for in_obj in in_objs:
            if not isinstance(in_obj, dict):
                in_obj = in_obj.model_dump()
            in_obj.update(**attrs)
            await self.run_db_validation(session, in_obj=in_obj)
            db_obj = self.model(**in_obj)
            objs.append(db_obj)
        session.add_all(objs)
        if commit:
            await session.commit()
            for db_obj in objs:
                await session.refresh(db_obj)
        return objs

    async def bulk_update(
        self,
        session: AsyncSession,
        in_objs: dict[ModelType, UpdateSchemaType],
        commit: bool = True,
        exclude_unset: bool = True,
        **attrs: Any,
    ) -> List[ModelType]:
        """
        Обновление экземпляров модели в БД пачкой.
        Также выполняет валидацию на уровне БД.

        :param session: сессия SQLAlchemy

        :param db_obj: обновляемый объект

        :param in_objs: словарь обновляемых объектов, где ключ -- существующий объект,
        значение -- схема Pydantic для обновления значений его полей.

        :param commit: нужно ли вызывать `session.commit()`

        :param exclude_unset: передаётся в метод `.model_dump()` Pydantic модели.
        При использовании метода в PATCH-запросах имеет смысл оставлять его True
        для изменения только переданных полей; при PUT-запросах имеет смысл
        передавать False, чтобы установить дефолтные значения полей, заданные
        в модели Pydantic.

        :param attrs: дополнительные значения обновляемых полей
        (чтобы какие-то поля можно было установить напрямую из кода,
        например, пользователя запроса)

        :returns: список обновлённых экземпляров модели
        """
        for obj, in_obj in in_objs.items():
            if isinstance(in_obj, dict):
                update_data = in_obj
            else:
                update_data = in_obj.model_dump(exclude_unset=exclude_unset)
            update_data.update(attrs)
            await self.run_db_validation(session, db_obj=obj, in_obj=update_data)
            for field in update_data:
                setattr(obj, field, update_data[field])
            session.add(obj)
        if commit:
            await session.commit()
            updated_objs = list(in_objs.keys())
            for updated_obj in updated_objs:
                await session.refresh(updated_obj)
        return updated_objs

    ##################################################################################
    # Internal methods
    ##################################################################################

    async def run_db_validation(
        self,
        session: AsyncSession,
        in_obj: ModelDict,
        db_obj: ModelType | None = None,
    ) -> ModelDict:
        """
        Выполнить валидацию на соответствие ограничениям БД.
        """
        if db_obj:
            db_obj_dict = sqlalchemy_model_to_dict(db_obj)
            db_obj_dict.update(in_obj)
            in_obj = db_obj_dict
        if self.fk_name_to_model:
            await self.validate_fk_exists(session, in_obj)
        if self.m2m_relationships:
            await self.handle_m2m_fields(session, in_obj)
        await self.validate_unique_fields(session, in_obj, db_obj=db_obj)
        await self.validate_unique_constraints(session, in_obj)
        return in_obj

    def get_select(self, select_: Select | None = None, **kwargs) -> Select:
        if select_ is not None:
            return select_
        return select(self.model)

    def get_joins(
        self,
        base_query: Select,
        filter_expressions: dict[InstrumentedAttribute | Callable, Any],
        options: List[Any] | None = None,
        order_by: OrderingField | None = None,
    ) -> Select:
        """
        Делает необходимые join'ы при фильтрации и сортировке по полям
        связанных моделей.
        Поддерживает только глубину связи 1.
        """
        joined_query = base_query
        models_to_join = set()
        if (
            order_by
            and not isinstance(order_by.field, str)
            and order_by.field.parent.class_ != self.model
        ):
            models_to_join.add(order_by.field.parent.class_)

        for filter_expression in filter_expressions.keys():
            if isinstance(filter_expression, InstrumentedAttribute):
                model = filter_expression.parent._identity_class
            elif isinstance(filter_expression, Function):
                model = filter_expression.entity_namespace
            else:
                model = filter_expression.__self__.parent._identity_class
            if model != self.model:
                models_to_join.add(model)
        for model in models_to_join:
            if model in self.models_to_relationship_attrs:
                joined_query = joined_query.outerjoin(
                    self.models_to_relationship_attrs[model]
                ).options(contains_eager(self.models_to_relationship_attrs[model]))

        if options:
            # Если в .options передана стратегия загрузки модели,
            # которая должна быть подгружена для фильтрации или сортировки,
            # нужно убрать её из options для избежания конфликтов.
            options[:] = [
                option
                for option in options
                if option.path.entity.class_ not in models_to_join
            ]
        return joined_query

    def get_order_by_expression(self, order_by: OrderingField | None):
        if order_by is not None:
            if self.default_ordering is not None:
                return order_by.get_directed_field(self.model), self.default_ordering
            return order_by.get_directed_field(self.model)
        return self.default_ordering

    @staticmethod
    def remove_optional_filter_bys(
        filters: dict[str, Any],
    ) -> None:
        for filter_by_name, filter_by_value in filters.copy().items():
            if filter_by_value is None:
                del filters[filter_by_name]

    @staticmethod
    def handle_filter_expressions(
        filter_expressions: dict[InstrumentedAttribute | Callable, Any]
    ) -> None:
        for filter_expression, value in filter_expressions.copy().items():
            if value is None:
                del filter_expressions[filter_expression]
            elif "ilike" in str(filter_expression):
                filter_expressions[
                    filter_expression
                ] = f"%{filter_expressions[filter_expression]}%"

    @staticmethod
    def handle_nullable_filter_expressions(
        nullable_filter_expressions: dict[InstrumentedAttribute | Callable, Any]
    ) -> None:
        for filter_expression, value in nullable_filter_expressions.copy().items():
            if value in null_query_values:
                nullable_filter_expressions[filter_expression] = None
            elif value is None:
                del nullable_filter_expressions[filter_expression]
            elif "ilike" in str(filter_expression):
                nullable_filter_expressions[
                    filter_expression
                ] = f"%{nullable_filter_expressions[filter_expression]}%"

    def get_reverse_relation_filter_stmt(
        self,
        field_name: str,
        value: Any,
    ) -> Exists:
        relationship: InstrumentedAttribute = getattr(self.model, field_name)
        return relationship.any(self.reverse_relationships[field_name].id.in_(value))

    def assemble_stmt(
        self,
        select_: Select | None = None,
        order_by: OrderingField | None = None,
        options: List[Any] | Any | None = None,
        where: Any | None = None,
        **simple_filters: Any,
    ) -> Select:
        if select_ is not None:
            stmt = select_
        else:
            stmt = self.get_select(select_=select_, order_by=order_by, **simple_filters)

        for field_name, value in simple_filters.copy().items():
            if field_name in self.reverse_relationships:
                stmt = stmt.filter(
                    self.get_reverse_relation_filter_stmt(field_name, value)
                )
                del simple_filters[field_name]

        if simple_filters:
            stmt = stmt.filter_by(**simple_filters)

        order_by_expression = self.get_order_by_expression(order_by)
        if order_by_expression is not None:
            stmt = (
                stmt.order_by(*order_by_expression)
                if isinstance(order_by_expression, tuple)
                else stmt.order_by(order_by_expression)
            )

        if options is not None:
            if not isinstance(options, list):
                options = [options]
        else:
            options = []
        for option in options:
            stmt = stmt.options(option)

        if where is not None:
            stmt = stmt.where(where)

        return stmt

    async def validate_fk_exists(
        self, session: AsyncSession, in_obj: ModelDict
    ) -> None:
        """
        Проверить, существуют ли связанные объекты с переданными для записи id.
        """

        for key in in_obj:
            if key in self.fk_name_to_model and in_obj[key] is not None:
                related_object_exists = await session.get(
                    self.fk_name_to_model[key],
                    in_obj[key],
                    options=[load_only(self.fk_name_to_model[key].id)],
                )
                if not related_object_exists:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=(
                            f"{self.fk_name_to_model[key].__tablename__} с id "
                            f"{in_obj[key]} не существует."
                        ),
                    )

    async def validate_unique_constraints(
        self, session: AsyncSession, in_obj: ModelDict
    ) -> None:
        """
        Проверить, не нарушаются ли UniqueConstraint модели.
        """
        for unique_constraint in self.unique_constraints:
            query = {}
            for field in unique_constraint:
                if in_obj[field] is not None:
                    query[field] = in_obj[field]
            object_exists = await self.exists(
                session, **query, where=(self.model.id != in_obj.get("id"))
            )
            if object_exists:
                conflicting_fields = ", ".join(unique_constraint)
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        f"{self.model.__tablename__} с такими "
                        + conflicting_fields
                        + " уже существует."
                    ),
                )

    async def validate_unique_fields(
        self,
        session: AsyncSession,
        in_obj: ModelDict,
        db_obj: ModelType | None = None,
    ) -> None:
        """
        Проверить соблюдение уникальности полей.
        """
        for column in self.model.__table__.columns._all_columns:
            if (
                column.unique
                and column.name in in_obj
                and in_obj[column.name] is not None
            ):
                if db_obj and getattr(db_obj, column.name) == in_obj[column.name]:
                    continue
                attrs_to_check = {column.name: in_obj[column.name]}
                object_exists = await self.exists(
                    session=session,
                    **attrs_to_check,
                    where=(self.model.id != in_obj.get("id")),
                )
                if object_exists:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=(
                            f"{self.model.__tablename__} c {column.name} "
                            f"{in_obj[column.name]} уже существует"
                        ),
                    )

    async def handle_m2m_fields(self, session: AsyncSession, in_obj: ModelDict):
        for field in in_obj:
            if field in self.m2m_relationships:
                related_model = self.m2m_relationships[field]
                related_objects = []
                for related_object_id in in_obj[field]:
                    related_object = await session.get(related_model, related_object_id)
                    if not related_object:
                        raise HTTPException(
                            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=(
                                f"{related_model.__tablename__} с id "
                                f"{related_object_id} не существует."
                            ),
                        )
                    related_objects.append(related_object)
                in_obj[field] = related_objects
