# ruff: noqa: UP006
from collections.abc import Callable, Iterable
from typing import Any, Generic, List, TypeVar  # noqa: UP035

from fastapi import HTTPException, status
from fastapi_pagination.bases import BasePage
from fastapi_pagination.ext.sqlalchemy import paginate
from pydantic import BaseModel
from sqlalchemy import (
    Integer,
    Row,
    String,
    UniqueConstraint,
    delete,
    func,
    insert,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import BOOLEAN
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase, contains_eager, load_only
from sqlalchemy.orm.attributes import InstrumentedAttribute
from sqlalchemy.orm.relationships import Relationship
from sqlalchemy.sql import Select
from sqlalchemy.sql.elements import UnaryExpression
from sqlalchemy.sql.functions import Function
from sqlalchemy.sql.schema import ScalarElementColumnDefault
from sqlalchemy.sql.selectable import Exists

from .filters import null_query_values

ModelT = TypeVar("ModelT", bound=DeclarativeBase)
CreateSchemaT = TypeVar("CreateSchemaT", bound=BaseModel)
UpdateSchemaT = TypeVar("UpdateSchemaT", bound=BaseModel)
ModelDict = dict[str, Any]


def sqlalchemy_model_to_dict(model: DeclarativeBase) -> dict:
    db_obj_dict = model.__dict__.copy()
    db_obj_dict.pop("_sa_instance_state", None)
    return db_obj_dict


class ModelManager(Generic[ModelT, CreateSchemaT, UpdateSchemaT]):
    def __init__(
        self,
        model: type[ModelT],
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
        self.fk_name_to_model: dict[str, type[ModelT]] = {}

        self.unique_constraints: List[List[str]] = []
        self.nullable_unique_constraints: List[List[str]] = []

        if hasattr(self.model, "__table_args__"):
            for table_arg in self.model.__table_args__:
                if isinstance(table_arg, UniqueConstraint):
                    # Проверяем наличие атрибута postgresql_nulls_not_distinct
                    # и его значение
                    if table_arg.dialect_kwargs.get("postgresql_nulls_not_distinct"):
                        if table_arg.columns.keys():
                            self.nullable_unique_constraints.append(
                                table_arg.columns.keys()
                            )
                        else:
                            self.nullable_unique_constraints.append(
                                table_arg._pending_colargs
                            )
                    else:
                        if table_arg.columns.keys():
                            self.unique_constraints.append(table_arg.columns.keys())
                        else:
                            self.unique_constraints.append(table_arg._pending_colargs)

        self.reverse_relationships: dict[str, type[ModelT]] = {}
        self.m2m_relationships: dict[str, type[ModelT]] = {}
        # Model to related attr
        # Parent : Child.parent
        # Используется при составлении join'ов для фильтрации и сортировки
        self.models_to_relationship_attrs: dict[
            type[ModelT], InstrumentedAttribute
        ] = {}
        # Значения по умолчанию для полей (используется для валидации)
        self.defaults: dict[str, Any] = {}

        attr: InstrumentedAttribute
        model_attrs = self.model.__dict__.copy()
        for attr_name, attr in model_attrs.items():
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
                    if attr.prop.secondary is not None:
                        self.m2m_relationships[attr_name] = attr.prop.mapper.class_
                if hasattr(attr, "nullable") and attr.nullable:
                    self.defaults[attr_name] = None
            if hasattr(attr, "default") and attr.default is not None:
                if isinstance(attr.default, ScalarElementColumnDefault):
                    self.defaults[attr_name] = attr.default.arg
            elif (
                hasattr(attr, "server_default")
                and attr.server_default is not None
                and hasattr(attr.server_default, "arg")
            ):
                if isinstance(attr.type, BOOLEAN):
                    self.defaults[attr_name] = attr.server_default.arg != "False"
                elif isinstance(attr.type, Integer):
                    self.defaults[attr_name] = int(attr.server_default.arg)
                elif isinstance(attr.type, String):
                    self.defaults[attr_name] = attr.server_default.arg

    ##################################################################################
    # Public API
    ##################################################################################

    async def create(
        self,
        session: AsyncSession,
        in_obj: CreateSchemaT | None = None,
        refresh_attribute_names: Iterable[str] | None = None,
        *,
        commit: bool = True,
        **attrs: Any,
    ) -> ModelT:
        """
        Создание экземпляра модели и сохранение в БД.
        Также выполняет валидацию на уровне БД.

        :param session: сессия SQLAlchemy

        :param in_obj: модель Pydantic для создания объекта

        :param refresh_attribute_names: названия полей, которые нужно обновить
        (может использоваться для подгрузки связанных полей)

        :param commit: нужно ли вызывать `session.commit()`, если используется
        подход commit as you go

        :param attrs: дополнительные значения полей создаваемого экземпляра
        (какие-то поля можно установить напрямую,
        например, пользователя запроса)

        :returns: созданный экземпляр модели
        """
        create_data = in_obj.model_dump() if in_obj else {}
        create_data.update(attrs)
        # Добавляем дефолтные значения полей для валидации уникальности
        for field, default in self.defaults.items():
            if field not in create_data:
                create_data[field] = default

        await self.run_db_validation(session, in_obj=create_data)
        db_obj = self.model(**create_data)
        session.add(db_obj)
        await self.save(session, commit=commit)
        await session.refresh(db_obj, attribute_names=refresh_attribute_names)
        return db_obj

    async def bulk_create(
        self,
        session: AsyncSession,
        in_objs: list[CreateSchemaT],
        *,
        commit: bool = True,
        returning: bool = True,
        **attrs: Any,
    ) -> list[ModelT] | None:
        """
        Создание экземпляров модели пачкой и сохранение в БД.

        Валидация на уровне БД выполняется для каждого объекта
        (могут быть ошибки, если несколько создаваемых объектов
        имеют одинаковое значение для уникального поля).

        :param session: сессия SQLAlchemy

        :param in_objs: модели Pydantic для создания объектов

        :param commit: нужно ли вызывать `session.commit()`, если используется
        подход commit as you go

        :param returning: нужно ли возвращать созданные объекты

        :param attrs: дополнительные значения полей создаваемых экземпляров

        :returns: созданные экземпляры модели или None
        """
        create_data = [in_obj.model_dump() | attrs for in_obj in in_objs]
        for in_obj in create_data:
            await self.run_db_validation(session, in_obj)

        stmt = insert(self.model).values(create_data)
        if returning:
            stmt = stmt.returning(self.model)
        result = await session.execute(stmt)
        await self.save(session, commit=commit)
        if returning:
            return result.scalars().all()
        return None

    async def get(
        self,
        session: AsyncSession,
        options: List[Any] | Any | None = None,
        order_by: InstrumentedAttribute | UnaryExpression | None = None,
        where: Any | None = None,
        base_stmt: Select | None = None,
        *,
        unique: bool = False,
        **simple_filters: Any,
    ) -> ModelT | Row | None:
        """
        Получение одного экземпляра модели при существовании

        :param session: сессия SQLAlchemy

        :param options: параметры для метода .options() загрузчика SQLAlchemy

        :param order_by: поле для сортировки

        :param where: выражение, которое будет передано в метод .where() SQLAlchemy

        :param base_stmt: объект Select для SQL запроса. Если передан, то метод вернёт
        экземпляр Row, а не ModelT.
        Примечание: фильтрация и сортировка по связанным моделям скорее всего
        не будут работать вместе с этим параметром.

        :param unique: определяет необходимость вызова метода .unique()
        у результата SQLAlchemy

        :param simple_filters: параметры для фильтрации по точному соответствию,
        аналогично методу .filter_by() SQLAlchemy

        :returns: экземпляр модели, Row или None, если подходящего нет в БД
        """
        stmt = self.assemble_stmt(base_stmt, order_by, options, where, **simple_filters)

        result = await session.execute(stmt)
        if unique:
            result = result.unique()
        if base_stmt is None:
            if order_by is not None:
                return result.scalars().first()
            return result.scalar_one_or_none()
        return result.first()

    async def get_or_404(
        self,
        session: AsyncSession,
        options: List[Any] | Any | None = None,
        order_by: InstrumentedAttribute | UnaryExpression | None = None,
        where: Any | None = None,
        base_stmt: Select | None = None,
        *,
        unique: bool = False,
        **simple_filters: Any,
    ) -> ModelT | Row:
        """
        Получение одного экземпляра модели или вызов HTTP исключения 404.

        :param session: сессия SQLAlchemy

        :param options: параметры для метода .options() загрузчика SQLAlchemy

        :param order_by: поле для сортировки

        :param where: выражение, которое будет передано в метод .where() SQLAlchemy

        :param base_stmt: объект Select для SQL запроса. Если передан, то метод вернёт
        экземпляр Row, а не ModelT.

        :param unique: определяет необходимость вызова метода .unique()
        у результата SQLAlchemy

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
            base_stmt=base_stmt,
            unique=unique,
            **simple_filters,
        )
        if not db_obj:
            attrs_str = ", ".join(
                [f"{key}={value}" for key, value in simple_filters.items()]
            )
            if where is not None:
                attrs_str += f", {where}"
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{self.model.__tablename__} with {attrs_str} not found",
            )
        return db_obj

    async def exists(
        self,
        session: AsyncSession,
        options: List[Any] | Any | None = None,
        where: Any | None = None,
        **simple_filters: Any,
    ) -> bool:
        """
        Проверка существования экземпляра модели.

        :param session: сессия SQLAlchemy

        :param options: параметры для метода .options() загрузчика SQLAlchemy

        :param where: выражение, которое будет передано в метод .where() SQLAlchemy

        :param simple_filters: параметры для фильтрации по точному соответствию,
        аналогично методу .filter_by() SQLAlchemy

        :returns: True если объект существует, иначе False
        """
        stmt = self.assemble_stmt(
            select(self.model.id), None, options, where, **simple_filters
        )
        result = await session.execute(stmt)
        return result.first() is not None

    async def exists_or_404(
        self,
        session: AsyncSession,
        options: List[Any] | Any | None = None,
        where: Any | None = None,
        **simple_filters: Any,
    ) -> bool:
        """
        Проверка существования экземпляра модели.
        Если объект не существует, вызывает HTTP исключение 404.

        :param session: сессия SQLAlchemy

        :param options: параметры для метода .options() загрузчика SQLAlchemy

        :param where: выражение, которое будет передано в метод .where() SQLAlchemy

        :param simple_filters: параметры для фильтрации по точному соответствию,
        аналогично методу .filter_by() SQLAlchemy

        :returns: True, если объект существует

        :raises: fastapi.HTTPException 404
        """

        exists = await self.exists(
            session,
            options=options,
            where=where,
            **simple_filters,
        )
        if not exists:
            attrs_str = ", ".join(
                [f"{key}={value}" for key, value in simple_filters.items()]
            )
            if where is not None:
                attrs_str += f", {where}"
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{self.model.__tablename__} with {attrs_str} does not exist",
            )
        return True

    async def paginated_filter(
        self,
        session: AsyncSession,
        order_by: InstrumentedAttribute | UnaryExpression | None = None,
        options: List[Any] | Any | None = None,
        where: Any | None = None,
        base_stmt: Select | None = None,
        transformer: Callable | None = None,
        **simple_filters: Any,
    ) -> BasePage[ModelT | Row]:
        """
        Получение списка объектов с фильтрами и пагинацией.

        :param session: сессия SQLAlchemy

        :param order_by: поле для сортировки

        :param options: параметры для метода .options() загрузчика SQLAlchemy

        :param where: выражение, которое будет передано в метод .where() SQLAlchemy

        :param base_stmt: объект Select для SQL запроса. Если передан, то метод вернёт
        страницу Row, а не ModelT.

        :param transformer: функция для преобразования атрибутов Row к
        модели Pydantic в пагинированном результате. См:
        https://uriyyo-fastapi-pagination.netlify.app/integrations/sqlalchemy/#scalar-column

        :param simple_filters: параметры для фильтрации по точному соответствию,
        аналогично методу .filter_by() SQLAlchemy

        :returns: пагинированный список объектов или Row
        """
        stmt = self.assemble_stmt(base_stmt, order_by, options, where, **simple_filters)
        return await paginate(session, stmt, transformer=transformer)

    async def paginated_list(
        self,
        session: AsyncSession,
        order_by: InstrumentedAttribute | UnaryExpression | None = None,
        filter_expressions: dict[InstrumentedAttribute | Callable, Any] | None = None,
        nullable_filter_expressions: (
            dict[InstrumentedAttribute | Callable, Any] | None
        ) = None,
        options: List[Any] | Any | None = None,
        where: Any | None = None,
        base_stmt: Select | None = None,
        transformer: Callable | None = None,
        **simple_filters: Any,
    ) -> BasePage[ModelT | Row]:
        """
        Получение списка объектов с фильтрами и пагинацией.
        Пропускает фильтры, значения которых None.

        :param session: сессия SQLAlchemy

        :param order_by: поле для сортировки

        :param filter_expressions: словарь, отображающий поля для фильтрации
        на их значения. Фильтрация по None не применяется. См. раздел "фильтрация"
        в документации.

        :param nullable_filter_expressions: словарь, отображающий поля для фильтрации
        на их значения. Фильтрация по None применятеся, если значение
        в fastapi_sqlalchemy_toolkit.NullableQuery. См. раздел "фильтрация"
        в документации.

        :param options: параметры для метода .options() загрузчика SQLAlchemy

        :param where: выражение, которое будет передано в метод .where() SQLAlchemy

        :param base_stmt: объект Select для SQL запроса. Если передан, то метод вернёт
        страницу Row, а не ModelT.
        Примечание: фильтрация и сортировка по связанным моделям скорее всего
        не будет работать вместе с этим параметром.

        :param transformer: функция для преобразования атрибутов Row к
        модели Pydantic в пагинированном результате. См:
        https://uriyyo-fastapi-pagination.netlify.app/integrations/sqlalchemy/#scalar-column

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

        stmt = self.assemble_stmt(base_stmt, order_by, options, where, **simple_filters)
        stmt = self.get_joins(
            stmt,
            options=options,
            order_by=order_by,
            filter_expressions=filter_expressions,
        )

        for filter_expression, value in filter_expressions.items():
            if isinstance(filter_expression, InstrumentedAttribute | Function):
                stmt = stmt.filter(filter_expression == value)
            else:
                stmt = stmt.filter(filter_expression(value))

        return await paginate(session, stmt, transformer=transformer)

    async def filter(
        self,
        session: AsyncSession,
        order_by: InstrumentedAttribute | UnaryExpression | None = None,
        options: List[Any] | Any | None = None,
        where: Any | None = None,
        base_stmt: Select | None = None,
        limit: int | None = None,
        offset: int | None = None,
        *,
        unique: bool = False,
        **simple_filters: Any,
    ) -> List[ModelT] | List[Row]:
        """
        Получение списка объектов с фильтрами

        :param session: сессия SQLAlchemy

        :param order_by: поле для сортировки

        :param options: параметры для метода .options() загрузчика SQLAlchemy

        :param where: выражение, которое будет передано в метод .where() SQLAlchemy

        :param unique: определяет необходимость вызова метода .unique()
        у результата SQLAlchemy

        :param base_stmt: объект Select для SQL запроса. Если передан, то метод вернёт
        список Row, а не ModelT.

        :param limit: ограничение, передаётся в параметр limit запроса SQLAlchemy

        :param offset: смещение, передаётся в параметр offset запроса SQLAlchemy

        :param simple_filters: параметры для фильтрации по точному соответствию,
        аналогично методу .filter_by() SQLAlchemy

        :returns: список объектов или Row
        """
        stmt = self.assemble_stmt(
            base_stmt,
            order_by,
            options,
            where,
            limit=limit,
            offset=offset,
            **simple_filters,
        )
        result = await session.execute(stmt)

        if base_stmt is None:
            if unique:
                return result.scalars().unique().all()
            return result.scalars().all()
        return result.all()

    async def list(
        self,
        session: AsyncSession,
        order_by: InstrumentedAttribute | UnaryExpression | None = None,
        filter_expressions: dict[InstrumentedAttribute | Callable, Any] | None = None,
        nullable_filter_expressions: (
            dict[InstrumentedAttribute | Callable, Any] | None
        ) = None,
        options: List[Any] | Any | None = None,
        where: Any | None = None,
        base_stmt: Select | None = None,
        limit: int | None = None,
        offset: int | None = None,
        *,
        unique: bool = False,
        **simple_filters: Any,
    ) -> List[ModelT] | List[Row]:
        """
        Получение списка объектов с фильтрами.
        Пропускает фильтры, значения которых None.

        :param session: сессия SQLAlchemy

        :param order_by: поле для сортировки

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

        :param base_stmt: объект Select для SQL запроса. Если передан, то метод вернёт
        список Row, а не ModelT.
        Примечание: фильтрация и сортировка по связанным моделям скорее всего
        не будут работать вместе с этим параметром.

        :param limit: ограничение, передаётся в параметр limit запроса SQLAlchemy

        :param offset: смещение, передаётся в параметр offset запроса SQLAlchemy

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

        stmt = self.assemble_stmt(
            base_stmt,
            order_by,
            options,
            where,
            limit=limit,
            offset=offset,
            **simple_filters,
        )
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

        if base_stmt is None:
            if unique:
                return result.scalars().unique().all()
            return result.scalars().all()
        return result.all()

    async def count(
        self,
        session: AsyncSession,
        where: Any | None = None,
        **simple_filters: Any,
    ) -> int:
        """
        Возвращает количество экземпляров модели по данным фильтрам.

        :param session: сессия SQLAlchemy

        :param where: выражение, которое будет передано в метод .where() SQLAlchemy

        :param simple_filters: параметры для фильтрации по точному соответствию,
        аналогично методу .filter_by() SQLAlchemy

        :returns: количество объектов по переданным фильтрам
        """
        # TODO: reference primary key instead of hardcode model.id
        stmt = select(func.count(self.model.id))
        if where is not None:
            stmt = stmt.where(where)
        if simple_filters:
            stmt = stmt.filter_by(**simple_filters)
        result = await session.execute(stmt)
        return result.scalar_one_or_none() or 0

    async def update(
        self,
        session: AsyncSession,
        db_obj: ModelT,
        in_obj: UpdateSchemaT | None = None,
        refresh_attribute_names: Iterable[str] | None = None,
        *,
        commit: bool = True,
        exclude_unset: bool = True,
        **attrs: Any,
    ) -> ModelT:
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

        :param commit: нужно ли вызывать `session.commit()`, если используется
        подход commit as you go

        :param exclude_unset: передаётся в метод `.model_dump()` Pydantic модели.
        При использовании метода в PATCH-запросах имеет смысл оставлять его True
        для изменения только переданных полей; при PUT-запросах имеет смысл
        передавать False, чтобы установить дефолтные значения полей, заданные
        в модели Pydantic.

        :returns: обновлённый экземпляр модели
        """
        update_data = in_obj.model_dump(exclude_unset=exclude_unset) if in_obj else {}
        update_data.update(attrs)
        update_data = await self.run_db_validation(
            session, db_obj=db_obj, in_obj=update_data
        )
        for field in update_data:
            setattr(db_obj, field, update_data[field])
        await self.save(session, commit=commit)
        await session.refresh(db_obj, attribute_names=refresh_attribute_names)
        return db_obj

    async def bulk_update(
        self,
        session: AsyncSession,
        in_obj: UpdateSchemaT | None = None,
        ids: Iterable | None = None,
        where: Any | None = None,
        *,
        commit: bool = True,
        returning: bool = True,
        **attrs: Any,
    ) -> List[ModelT] | None:
        """
        Обновление экземпляров модели пачкой и сохранение в БД.
        Не выполняет валидацию на уровне БД.

        :param session: сессия SQLAlchemy

        :param in_obj: модель Pydantic для обновления объектов

        :param ids: ID обновляемых объектов (в списке, кортеже и т.д.)

        :param where: фильтр для обновления объектов,
        передаётся в метод .where() SQLAlchemy.
        Используется, если не передан параметр :ids:

        :param commit: нужно ли вызывать `session.commit()`, если используется
        подход commit as you go

        :param returning: нужно ли возвращать обновлённые объекты

        :param attrs: дополнительные значения полей обновляемых экземпляров

        :returns: обновлённые экземпляры модели или None
        """
        update_data = in_obj.model_dump() if in_obj else {}
        update_data.update(attrs)

        stmt = update(self.model).values(update_data)
        if ids:
            stmt = stmt.where(self.model.id.in_(ids))
        elif where is not None:
            stmt = stmt.where(where)
        if returning:
            stmt = stmt.returning(self.model)
        result = await session.execute(stmt)
        await self.save(session, commit=commit)
        if returning:
            return result.scalars().all()
        return None

    async def delete(
        self, session: AsyncSession, db_obj: ModelT, *, commit: bool = True
    ) -> ModelT:
        """
        Удаление экземпляра модели из БД.

        :param session: сессия SQLAlchemy

        :param db_obj: удаляемый объект

        :param commit: нужно ли вызывать `session.commit()`, если используется
        подход commit as you go

        :returns: переданный в функцию экземпляр модели
        """
        await session.delete(db_obj)
        await self.save(session, commit=commit)
        return db_obj

    async def bulk_delete(
        self,
        session: AsyncSession,
        ids: Iterable | None = None,
        where: Any | None = None,
        *,
        commit: bool = True,
    ) -> None:
        """
        Удаление экземпляров модели пачкой из БД.

        :param session: сессия SQLAlchemy

        :param ids: ID удаляемых объектов (в списке, кортеже и т.д.)

        :param where: фильтр для удаления объектов,
        передаётся в метод .where() SQLAlchemy.
        Используется, если не передан параметр :ids:

        :param commit: нужно ли вызывать `session.commit()`, если используется
        подход commit as you go

        :returns: None
        """
        stmt = delete(self.model)
        if ids:
            stmt = stmt.where(self.model.id.in_(ids))
        elif where is not None:
            stmt = stmt.where(where)
        await session.execute(stmt)
        await self.save(session, commit=commit)

    ##################################################################################
    # Internal methods
    ##################################################################################

    @staticmethod
    async def save(session: AsyncSession, *, commit: bool = True) -> None:
        """
        Сохраняет изменения в БД, обрабатывая разное использовании сессии:
        "commit as you go" или "begin once".

        Если используется подход "commit as you go", и параметр :commit: передан
        True, то выполняется `commit()`; иначе `flush()`.

        Если используется подход "begin once" (`async with session.begin():`),
        то не выполняется `flush()`, чтобы не закрывать транзакцию в контекстном
        менеджере.
        """

        if session.sync_session._trans_context_manager:
            await session.flush()
        elif commit:
            await session.commit()
        else:
            await session.flush()

    async def run_db_validation(
        self,
        session: AsyncSession,
        in_obj: ModelDict,
        db_obj: ModelT | None = None,
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
        await self.validate_nullable_unique_constraints(session, in_obj)
        return in_obj

    def get_select(self, base_stmt: Select | None = None, **_kwargs: Any) -> Select:
        if base_stmt is not None:
            return base_stmt
        return select(self.model)

    def get_joins(
        self,
        base_query: Select,
        filter_expressions: dict[InstrumentedAttribute | Callable, Any],
        options: List[Any] | None = None,
        order_by: InstrumentedAttribute | UnaryExpression | None = None,
    ) -> Select:
        """
        Делает необходимые join'ы при фильтрации и сортировке по полям
        связанных моделей.
        Поддерживает только глубину связи 1.
        """
        if options is not None:
            if not isinstance(options, list):
                options = [options]
        else:
            options = []

        joined_query = base_query
        models_to_join = set()

        if order_by is not None:
            if isinstance(order_by, InstrumentedAttribute):
                ordering_model = order_by.parent.class_
            else:
                ordering_model = order_by._propagate_attrs[
                    "plugin_subject"
                ]._identity_class
            if ordering_model != self.model:
                models_to_join.add(ordering_model)

        for filter_expression in filter_expressions:
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
                )

        if options:
            # Если в .options передана стратегия загрузки модели,
            # которая должна быть подгружена для фильтрации или сортировки,
            # то не добавляем contains_eager для этой модели
            models_for_additional_options = models_to_join.copy()
            for option in options:
                if option.path.entity.class_ in models_for_additional_options:
                    models_for_additional_options.remove(option.path.entity.class_)
            for model in models_for_additional_options:
                options.append(contains_eager(self.models_to_relationship_attrs[model]))
        return joined_query

    def get_order_by_expression(
        self, order_by: InstrumentedAttribute | UnaryExpression | None
    ) -> (
        InstrumentedAttribute
        | UnaryExpression
        | None
        | tuple[
            InstrumentedAttribute | UnaryExpression,
            InstrumentedAttribute | UnaryExpression,
        ]
    ):
        if order_by is not None:
            if self.default_ordering is not None:
                return order_by, self.default_ordering
            return order_by
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
        filter_expressions: dict[InstrumentedAttribute | Callable, Any],
    ) -> None:
        for filter_expression, value in filter_expressions.copy().items():
            if value is None:
                del filter_expressions[filter_expression]
            elif "ilike" in str(filter_expression):
                filter_expressions[filter_expression] = (
                    f"%{filter_expressions[filter_expression]}%"
                )

    @staticmethod
    def handle_nullable_filter_expressions(
        nullable_filter_expressions: dict[InstrumentedAttribute | Callable, Any],
    ) -> None:
        for filter_expression, value in nullable_filter_expressions.copy().items():
            if value in null_query_values:
                nullable_filter_expressions[filter_expression] = None
            elif value is None:
                del nullable_filter_expressions[filter_expression]
            elif "ilike" in str(filter_expression):
                nullable_filter_expressions[filter_expression] = (
                    f"%{nullable_filter_expressions[filter_expression]}%"
                )

    def get_reverse_relation_filter_stmt(
        self,
        field_name: str,
        value: Any,
    ) -> Exists:
        relationship: InstrumentedAttribute = getattr(self.model, field_name)
        return relationship.any(self.reverse_relationships[field_name].id.in_(value))

    def assemble_stmt(
        self,
        base_stmt: Select | None = None,
        order_by: InstrumentedAttribute | UnaryExpression | None = None,
        options: List[Any] | Any | None = None,
        where: Any | None = None,
        limit: int | None = None,
        offset: int | None = None,
        **simple_filters: Any,
    ) -> Select:
        if base_stmt is not None:
            stmt = base_stmt
        else:
            stmt = self.get_select(
                base_stmt=base_stmt, order_by=order_by, **simple_filters
            )

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
            if isinstance(where, tuple):
                stmt = stmt.where(*where)
            else:
                stmt = stmt.where(where)

        if limit is not None:
            stmt = stmt.limit(limit)
        if offset is not None:
            stmt = stmt.offset(offset)

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

    async def validate_nullable_unique_constraints(
        self, session: AsyncSession, in_obj: ModelDict
    ) -> None:
        """
        Проверяет, не нарушаются ли nullable UniqueConstraint модели.
        Поля со значением NULL игнорируются при проверке и не считаются дублированием.
        """
        for unique_constraint in self.nullable_unique_constraints:
            query = {}
            if any(in_obj[field] is None for field in unique_constraint):
                continue

            for field in unique_constraint:
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
        db_obj: ModelT | None = None,
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

    async def handle_m2m_fields(self, session: AsyncSession, in_obj: ModelDict) -> None:
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
