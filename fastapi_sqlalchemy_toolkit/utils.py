from copy import deepcopy
from typing import Annotated, Any, Optional, TypeVar

import pydantic
import pydantic_core
from fastapi import Query

BaseModelT = TypeVar("BaseModelT", bound=pydantic.BaseModel)


def _make_field_optional(
    field: pydantic.fields.FieldInfo,
) -> tuple[Any, pydantic.fields.FieldInfo]:
    new = deepcopy(field)
    new.default = (
        None if field.default == pydantic_core.PydanticUndefined else field.default
    )
    new.annotation = Optional[field.annotation]  # type: ignore  # noqa: UP007
    return (new.annotation, new)


def make_partial_model(model: type[BaseModelT]) -> type[BaseModelT]:
    """
    Функция, создающая Pydantic модель из переданной,
    делая все поля модели необязательными.
    Полезно для схем PATCH запросов.
    """
    return pydantic.create_model(  # type: ignore
        f"Partial{model.__name__}",
        __base__=model,
        __module__=model.__module__,
        **{
            field_name: _make_field_optional(field_info)
            for field_name, field_info in model.model_fields.items()
        },
    )


# Утилиты для передачи нескольких значений для фильтрации в одном
# квери параметре через запятую
CommaSepQuery = Annotated[
    str | None, Query(description="Несколько значений можно передать через запятую")
]


def comma_sep_q_to_list(query: str | None, type_: type) -> list | None:
    """
    :param query: Значение квери параметра
    (строка со значениями, перечисленными через запятую)
    :param type_: Тип значений в списке для конвертирования
    """
    if query:
        return [type_(query_value) for query_value in query.split(",")]
    return None
