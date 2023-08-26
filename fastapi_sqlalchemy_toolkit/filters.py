from typing import Any, Callable, Literal, Type, get_args

from dateutil import parser

from .base_model import Base

# NullableQuery определяет значения квери параметра,
# который должны интерпретироваться как сравнение с null.
# None интерпретируется как отсутствие квери параметра
# и исключает поле из фильтрации (вместо фильтра со сравнением с null).
NullableQuery = Literal[""]
null_query_values = get_args(NullableQuery)


class FieldFilter:
    """
    Класс для универсальной фильтрации по значениям полей моделей SQLAlchemy.
    """

    def __init__(
        self,
        value: Any,
        operator: str = "__eq__",
        func: Callable | None = None,
        model: Type[Base] | None = None,
        alias: str | None = None,
    ) -> None:
        """
        :param value: Значение поля
        :param operator: Атрибут/метод модели, с помощью которого нужно фильтровать
        :param func: Функция SQLAlchemy, которую нужно применить к полю
        :param model: Модель SQLAlchemy, к которой применяется фильтр
        По умолчанию, модель из DB CRUD, в котором вызывается метод.
        :param alias: Название поля модели
        (по умолчанию название параметра, по которому фильтр передаётся в db_crud)
        """
        self.value = value
        self.operator = operator
        self.func = func
        self.model = model
        self.alias = alias

        # Приводим значение поля к формату, который ожидает SQLAlchemy.
        if self.value is not None:
            if self.value in null_query_values:
                self.value = None

            elif self.operator == "ilike":
                self.value = f"%{self.value}%"

            elif self.func and str(self.func()) == "date()":
                self.value = parser.parse(self.value).date()

    def __bool__(self):
        return self.value is not None
