from typing import Any, Generic, Type, TypeVar

from fastapi import HTTPException, status
from fastapi_pagination.bases import AbstractPage, AbstractParams
from fastapi_pagination.ext.async_sqlalchemy import paginate
from pydantic import BaseModel
from sqlalchemy import UniqueConstraint, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager, load_only
from sqlalchemy.orm.attributes import InstrumentedAttribute
from sqlalchemy.orm.relationships import Relationship
from sqlalchemy.sql import Select
from sqlalchemy.sql.elements import BinaryExpression, BooleanClauseList

from .base_model import Base
from .filters import FieldFilter
from .ordering import OrderingField

ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)
ModelDict = dict[str, Any]


class BaseCRUD(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    def __init__(
        self,
        model: Type[ModelType],
        fk_mapping: dict[str, Type[Base]] | None = None,
        default_ordering: InstrumentedAttribute | None = None,
    ) -> None:
        """
        Создание экземпляра DB CRUD под конкретную модель.

        :param model: модель SQLAlchemy

        :param fk_mapping: словарь, который соотносит названия полей модели,
        которые являются внешними ключами, и модели SQLAlchemy,
        на которые ключи ссылаются.
        Этот параметр нужно определить для валидации внешних ключей.
        Например, если DB CRUD создаётся для модели Child, которая имеет
        внешний ключ parent_id на модель Parent, то нужно передать
        fk_mapping={"parent_id": Parent}

        :param default_ordering: поле модели, по которому должна выполняться
        сортировка по умолчанию
        """
        self.model = model
        self.fk_mapping = fk_mapping
        self.default_ordering = default_ordering

        self.unique_constraints: list[list[str]] = []
        if hasattr(self.model, "__table_args__"):
            for table_arg in self.model.__table_args__:
                if isinstance(table_arg, UniqueConstraint):
                    self.unique_constraints.append(table_arg.columns.keys())

        self.reverse_relationships: dict[str, Type[Base]] = {}
        self.m2m_relationships: dict[str, Type[Base]] = {}
        self.related_models: dict[str, InstrumentedAttribute] = {}
        for attr_name, attr in self.model.__dict__.items():
            # Перебираем только атрибуты модели
            if not attr_name.startswith("_"):
                # Выбираем связи
                if hasattr(attr, "prop") and isinstance(attr.prop, Relationship):
                    self.related_models[str(attr.prop.mapper.class_)] = attr
                    # Выбираем обратные связи (ManyToOne, ManyToMany)
                    if attr.prop.collection_class == list:
                        self.reverse_relationships[attr_name] = attr.prop.mapper.class_
                    # Выбираем  ManyToMany связи
                    if getattr(attr.prop, "secondary") is not None:
                        self.m2m_relationships[attr_name] = attr.prop.mapper.class_

    ##################################################################################
    # Public API
    ##################################################################################

    async def create(
        self,
        session: AsyncSession,
        in_obj: CreateSchemaType | ModelDict,
        refresh_attribute_names: list[str] | None = None,
        **attrs: Any,
    ) -> ModelType:
        """
        Создание экземпляра модели и сохранение в БД.
        Также выполняет валидацию на уровне БД.

        :param session: сессия SQLAlchemy

        :param in_obj: значения полей создаваемого экземпляра модели в словаре

        :param refresh_attribute_names: список полей, которые нужно обновить
        (может использоваться для подгрузки связанных полей)

        :param attrs: дополнительные значения полей создаваемого экземпляра
        (чтобы какие-то поля можно было установить напрямую из кода,
        например, пользователя запроса)

        :returns: созданный экземпляр модели
        """
        if isinstance(in_obj, dict):
            create_data = in_obj
        else:
            create_data = in_obj.model_dump()
        validated_data = await self.run_db_validation(
            session=session, in_obj=create_data | attrs
        )
        db_obj = self.model(**validated_data)
        session.add(db_obj)
        await session.commit()
        await session.refresh(db_obj, attribute_names=refresh_attribute_names)
        return db_obj

    async def get(
        self,
        session: AsyncSession,
        options: list[Any] | Any | None = None,
        order_by: OrderingField | None = None,
        **attrs,
    ) -> ModelType | None:
        """
        Получение одного экземпляра модели при существовании

        :param session: сессия SQLAlchemy

        :param options: параметры для метода .options() загрузчика SQLAlchemy

        :param order_by: поле для сортировки (экземпляр OrderingField)

        :param attrs: параметры для выборки объекта. Название параметра используется как
        название поля модели. Значение параметра может быть примитивным типом для
        точного сравнения либо экземпляром FieldFilter.

        :returns: экземпляр модели или None, если подходящего нет в БД
        """
        filter_expression = self.get_filter_expression(**attrs)
        statement = self.get_base_query().filter(filter_expression)
        if options is not None:
            if isinstance(options, list):
                for option in options:
                    statement = statement.options(option)
            else:
                statement = statement.options(options)
        order_by_expression = self.get_order_by_expression(order_by)
        if order_by_expression is not None:
            statement = statement.order_by(order_by_expression)
        result = await session.execute(statement=statement)
        return result.scalars().first()

    async def get_or_404(self, session: AsyncSession, **attrs) -> ModelType:
        """
        Получение одного экземпляра модели или возвращение HTTP ответа 404.

        :param session: сессия SQLAlchemy

        :param attrs: все параметры, которые можно передать в метод get

        :returns: экземпляр модели

        :raises: fastapi.HTTPException 404
        """

        db_obj = await self.get(session=session, **attrs)
        if not db_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{self.model.__tablename__.capitalize()} not found",
            )
        return db_obj

    async def exists(self, session: AsyncSession, **attrs) -> bool:
        """
        Проверка существования экземпляра модели.

        :param session: сессия SQLAlchemy

        :param attrs: параметры для выборки объекта. Название параметра используется как
        название поля модели. Значение параметра может быть примитивным типом для
        точного сравнения либо экземпляром FieldFilter.

        :returns: True если объект существует, иначе False
        """
        filter_expression = self.get_filter_expression(**attrs)
        statement = select(self.model.id).filter(filter_expression)
        result = await session.execute(statement=statement)
        return result.first() is not None

    async def paginated_filter(
        self,
        session: AsyncSession,
        pagination_params: AbstractParams | None = None,
        order_by: OrderingField | None = None,
        options: list[Any] | Any | None = None,
        where: Any | None = None,
        **attrs,
    ) -> AbstractPage[ModelType]:
        """
        Получение выборки экземпляров модели с фильтрами и пагинацией.

        :param session: сессия SQLAlchemy

        :pagination_params: параметры пагинации из fastapi_pagination

        :param order_by: поле для сортировки (экземпляр OrderingField)

        :param options: параметры для метода .options() загрузчика SQLAlchemy

        :param where: параметры для метода .where() селекта SQLAlchemy.
        Может приняться для передачи параметров фильтрации,
        которые нельзя передать в attrs.
        Например, для фильтрации с использованием метода .any() у поля-связи модели.

        :param attrs: параметры для выборки объекта. Название параметра используется как
        название поля модели. Значение параметра может быть примитивным типом для
        точного сравнения либо экземпляром FieldFilter.

        :returns: пагинированная выборка объектов
        """
        base_query = self.get_base_query(**attrs, order_by=order_by)
        joined_query = self.get_joins(base_query, order_by=order_by, **attrs)
        query = self.get_list_query(
            joined_query, order_by=order_by, options=options, where=where, **attrs
        )
        return await paginate(session, query, pagination_params)

    async def filter(
        self,
        session: AsyncSession,
        order_by: OrderingField | None = None,
        filter_by: dict | None = None,
        options: list[Any] | Any | None = None,
        where: Any | None = None,
        unique: bool = False,
        **attrs,
    ) -> Any:
        """
        Получение выборки экземпляров модели с фильтрами.

        :param session: сессия SQLAlchemy

        :param order_by: поле для сортировки (экземпляр OrderingField)

        :param filter_by: параметры для метода .filter_by() селекта SQLAlchemy
        в виде словаря

        :param options: параметры для метода .options() загрузчика SQLAlchemy

        :param where: параметры для метода .where() селекта SQLAlchemy.
        Может приняться для передачи параметров фильтрации,
        которые нельзя передать в attrs.
        Например, для фильтрации с использованием метода .any() у поля-связи модели.

        :param unique: определяет необходимость вызова метода .unique()
        у результата SQLAlchemy

        :param attrs: параметры для выборки объекта. Название параметра используется как
        название поля модели. Значение параметра может быть примитивным типом для
        точного сравнения либо экземпляром FieldFilter.

        :returns: выборка объектов
        """
        base_query = self.get_base_query(**attrs, order_by=order_by)
        joined_query = self.get_joins(base_query, order_by=order_by, **attrs)
        query = self.get_list_query(
            joined_query, order_by, filter_by, options, where=where, **attrs
        )
        list_objects = await session.execute(query)
        if unique:
            return list_objects.scalars().unique().all()
        return list_objects.scalars().all()

    async def count(self, session: AsyncSession, **attrs) -> int:
        """
        Возвращает количество экземпляров модели по данным фильтрам.

        :param session: сессия SQLAlchemy

        :param attrs: параметры для выборки объекта. Название параметра используется как
        название поля модели. Значение параметра может быть примитивным типом для
        точного сравнения либо экземпляром FieldFilter.

        :returns: количество объектов по переданным фильтрам
        """
        query = select(func.count(self.model.id))
        filter_expression = self.get_filter_expression(**attrs)
        if filter_expression is not None:
            query = query.filter(filter_expression)
        amount = await session.execute(query)
        return amount.scalars().first() or 0

    async def update(
        self,
        session: AsyncSession,
        db_obj: ModelType,
        in_obj: UpdateSchemaType | ModelDict,
        refresh_attribute_names: list[str] | None = None,
        **attrs,
    ) -> ModelType:
        """
        Обновление экземпляра модели в БД.
        Также выполняет валидацию на уровне БД.

        :param session: сессия SQLAlchemy

        :param db_obj: обновляемый объект

        :param in_obj: значения обновляемых полей в словаре

        :param attrs: дополнительные значения обновляемых полей
        (чтобы какие-то поля можно было установить напрямую из кода,
        например, пользователя запроса)

        :param refresh_attribute_names: список полей, которые нужно обновить
        (может использоваться для подгрузки связанных полей)

        :returns: обновлённый экземпляр модели
        """
        if isinstance(in_obj, dict):
            update_data = in_obj
        else:
            update_data = in_obj.model_dump()

        update_data.update(attrs)
        validated_data = await self.run_db_validation(
            session=session, db_obj=db_obj, in_obj=update_data
        )
        for field in validated_data:
            setattr(db_obj, field, validated_data[field])
        session.add(db_obj)
        await session.commit()
        await session.refresh(db_obj, attribute_names=refresh_attribute_names)
        return db_obj

    async def delete(
        self, session: AsyncSession, db_obj: ModelType
    ) -> ModelType | None:
        """
        Удаление экземпляра модели из БД.

        :param session: сессия SQLAlchemy

        :param db_obj: удаляемый объект
        """
        await session.delete(db_obj)
        await session.commit()
        return db_obj

    ##################################################################################
    # Internal methods
    ##################################################################################

    async def run_db_validation(
        self,
        session: AsyncSession,
        db_obj: ModelType | None = None,
        in_obj: ModelDict | None = None,
    ) -> ModelDict:
        """
        Выполнить валидацию на соответствие ограничениям БД.
        """
        if db_obj:
            db_obj_dict = db_obj.to_dict()
            db_obj_dict.update(in_obj)
            in_obj = db_obj_dict
        if self.fk_mapping:
            await self.validate_fk_exists(session, in_obj)
        if self.m2m_relationships:
            await self.handle_m2m_fields(session, in_obj)
        await self.validate_unique_fields(session, in_obj, db_obj=db_obj)
        await self.validate_unique_constraints(session, in_obj)
        return in_obj

    def get_base_query(self, **kwargs) -> Select:
        return select(self.model)

    def get_joins(
        self, base_query: Select, order_by: OrderingField | None = None, **kwargs
    ):
        """
        Делает необходимые join'ы при фильтрации и сортировке по полям
        связанных моделей.
        Поддерживает только глубину связи 1.
        """
        joined_query = base_query
        models_to_join = set()
        if order_by and not isinstance(order_by.field, str):
            models_to_join.add(str(order_by.field.parent.class_))
        if self.default_ordering and self.default_ordering.parent.class_ != self.model:
            models_to_join.add(str(self.default_ordering.parent.class_))
        for filter in kwargs.values():
            if isinstance(filter, FieldFilter) and filter and filter.model:
                models_to_join.add(str(filter.model))
        for model in models_to_join:
            if model in self.related_models:
                joined_query = joined_query.outerjoin(
                    self.related_models[model]
                ).options(contains_eager(self.related_models[model]))
        return joined_query

    def get_order_by_expression(self, order_by: OrderingField | None):
        if order_by is not None:
            if self.default_ordering:
                return order_by.get_directed_field(self.model), self.default_ordering
            return order_by.get_directed_field(self.model)
        return self.default_ordering

    def add_reverse_relation_filter_expression(
        self, field_name: str, filter_options, filters: list
    ):
        relationship = getattr(self.model, field_name)
        filter_expression = relationship.any(
            self.reverse_relationships[field_name].id.in_(filter_options)
        )
        filters.append(filter_expression)

    def get_filter_expression(
        self, **kwargs: FieldFilter | Any
    ) -> BooleanClauseList | None:
        filters: list[BinaryExpression] = []
        for field_name, filter_options in kwargs.items():
            if (
                filter_options is None
                or isinstance(filter_options, FieldFilter)
                and filter_options.value is None
            ):
                continue

            if field_name in self.reverse_relationships:
                self.add_reverse_relation_filter_expression(
                    field_name, filter_options, filters
                )
                continue

            if not isinstance(filter_options, FieldFilter):
                filter_options = FieldFilter(value=filter_options)

            model = filter_options.model or self.model
            field = (
                getattr(model, filter_options.alias)
                if filter_options.alias
                else getattr(model, field_name)
            )
            expression = field
            if filter_options.func:
                expression = filter_options.func(expression)
            operators = filter_options.operator.split(".")
            for operator in operators:
                expression = getattr(expression, operator)
            filters.append(expression(filter_options.value))

        if filters:
            expression = filters[0]
            for filter_expression in filters[1:]:
                expression &= filter_expression
        else:
            expression = None
        return expression

    def get_list_query(
        self,
        base_query: Select,
        order_by: OrderingField | None,
        filter_by: dict | None = None,
        options: Any | None = None,
        where: Any | None = None,
        **attrs,
    ):
        query = base_query
        order_by_expression = self.get_order_by_expression(order_by)
        filter_expression = self.get_filter_expression(**attrs)
        if filter_expression is not None:
            query = query.filter(filter_expression)
        if filter_by is not None:
            query = query.filter_by(**filter_by)
        if order_by_expression is not None:
            query = (
                query.order_by(*order_by_expression)
                if isinstance(order_by_expression, tuple)
                else query.order_by(order_by_expression)
            )
        if options is not None:
            if isinstance(options, list):
                for option in options:
                    query = query.options(option)
            else:
                query = query.options(options)
        if where is not None:
            query = query.where(where)
        elif hasattr(self.model, "created_at"):
            query = query.order_by(self.model.created_at.desc())
        return query

    async def validate_fk_exists(
        self, session: AsyncSession, in_obj: ModelDict
    ) -> None:
        """
        Проверить, существуют ли связанные объекты с переданными для записи id.
        """

        for key in in_obj:
            if key in self.fk_mapping and in_obj[key] is not None:
                related_object_exists = await session.get(
                    self.fk_mapping[key],
                    in_obj[key],
                    options=[load_only(self.fk_mapping[key].id)],
                )
                if not related_object_exists:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=(
                            f"{self.fk_mapping[key].__tablename__} с ID "
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
                query[field] = in_obj[field]
            object_exists = await self.exists(session, **query)
            if object_exists:
                conflicting_fields = ", ".join(unique_constraint)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
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
            if column.unique and column.name in in_obj:
                if db_obj and getattr(db_obj, column.name) == in_obj[column.name]:
                    continue
                attrs_to_check = {column.name: in_obj[column.name]}
                check_unique = await self.exists(session=session, **attrs_to_check)
                if check_unique:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
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
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=(
                                f"{related_model.__tablename__} с ID "
                                f"{related_object_id} не существует."
                            ),
                        )
                    related_objects.append(related_object)
                in_obj[field] = related_objects
