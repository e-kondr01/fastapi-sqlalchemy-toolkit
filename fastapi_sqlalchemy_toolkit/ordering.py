from collections.abc import Sequence
from enum import Enum
from typing import Annotated
from uuid import uuid4

from fastapi import Depends
from sqlalchemy.orm.attributes import InstrumentedAttribute
from sqlalchemy.sql.elements import UnaryExpression


def get_ordering_enum(
    ordering_fields_mapping: dict[str, InstrumentedAttribute],
) -> Enum:
    """
    Собирает Enum из возможных значений сортировки для документации OpenAPI
    """
    enum_attrs = {}
    for field_name in ordering_fields_mapping:
        enum_attrs[field_name] = field_name
        enum_attrs[f"desc_{field_name}"] = "-" + field_name
    return Enum(str(uuid4()), enum_attrs)


def ordering_depends(
    ordering_fields: Sequence[InstrumentedAttribute] | dict[str, InstrumentedAttribute],
) -> object:
    """
    Создаёт fastapi.Depends для квери параметра сортировки по переданным полям модели.

    :ordering_fields: поля для сортировки.
    Может быть последовательностью полей основной модели:
    ordering_fields=(MyModel.title, MyModel.created_at)
    В таком случае будут доступны параметры сортировки "title", "-title",
    "created_at", "-created_at".
    Дефис первым символом означает сортировку по убыванию.
    Либо может быть маппингом строковых полей для сортировки
    на соответствующие поля моделей:
    ordering_fields={
        "title": MyModel.title,
        "parent_title": ParentModel.title
    }
    В таком случае будут доступны параметры сортировки "title", "-title",
    "parent_title", "-parent_title".
    Если order_by передаётся в методы list или paginated_list,
    и поле для сортировки относится к модели, напрямую связанную с основной,
    то будет выполнен необходимый join для применения сортировки.
    """

    if isinstance(ordering_fields, dict):
        ordering_fields_mapping = ordering_fields

    else:
        ordering_fields_mapping = {field.name: field for field in ordering_fields}

    def get_ordering_field(
        order_by: get_ordering_enum(ordering_fields_mapping) = None,
    ) -> InstrumentedAttribute | UnaryExpression | None:
        if order_by:
            desc = order_by.value.startswith("-")
            field = ordering_fields_mapping[order_by.value.lstrip("-")]
            if desc:
                return field.desc()
            return field
        return None

    return Annotated[
        InstrumentedAttribute | UnaryExpression | None,
        Depends(get_ordering_field),
    ]
