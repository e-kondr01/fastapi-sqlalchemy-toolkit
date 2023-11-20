from dataclasses import dataclass
from enum import Enum
from typing import Annotated, Sequence, Type
from uuid import uuid4

from fastapi import Depends
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm.attributes import InstrumentedAttribute


@dataclass
class OrderingField:
    """
    Класс для направленный сортировки по полям модели SQLAlchemy
    или полям связанных с ней моделей.
    """

    field: InstrumentedAttribute | str
    desc: bool = False

    def get_directed_field(self, model: Type[DeclarativeBase]):
        if isinstance(self.field, str):
            field = getattr(model, self.field)
        else:
            field = self.field
        if self.desc:
            return field.desc()
        return field


def get_ordering_enum(
    ordering_fields: Sequence[str | InstrumentedAttribute],
) -> Type[Enum]:
    """
    Собирает Enum из возможных значений сортировки для документации OpenAPI
    """
    enum_attrs = {}
    for field in ordering_fields:
        if isinstance(field, str):
            field_name = field
        else:
            # Если передан атрибут модели
            field_name = str(field).lower().replace(".", "_")
        enum_attrs[field_name] = field_name
        enum_attrs[f"desc_{field_name}"] = "-" + field_name
    return Enum(str(uuid4()), enum_attrs)


def ordering_dep(ordering_fields: Sequence[str | InstrumentedAttribute]):
    """
    Создаёт Depends из FastAPI для квери параметра сортировки по переданным полям.
    Поля могут быть строками (поле основной модели) либо атрибутами моделей SQLAlchemy,
    связанных с основной.
    """

    def get_ordering_field(
        order_by: get_ordering_enum(ordering_fields) = None,
    ) -> OrderingField | None:
        if order_by:
            desc = False
            if order_by.value.startswith("-"):
                desc = True
            for field in ordering_fields:
                if str(field).lower().replace(".", "_") == order_by.value.lstrip("-"):
                    return OrderingField(field=field, desc=desc)
        return None

    return Annotated[
        OrderingField | None,
        Depends(get_ordering_field),
    ]
