from typing import Any, Callable, Type

from dateutil import parser

from .base_model import Base


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
        filter_by_null: bool = False,
    ) -> None:
        """
        :param value: Значение поля

        :param operator: Атрибут/метод модели, с помощью которого нужно фильтровать

        :param func: Функция SQLAlchemy, которую нужно применить к полю

        :param model: Модель SQLAlchemy, к которой применяется фильтр
        По умолчанию, модель из ModelManager, в котором вызывается метод.

        :param alias: Название поля модели
        (по умолчанию название параметра, по которому фильтр
        передаётся в методы ModelManager)

        :param filter_by_null: если установить как True, то фильтрация этого поля
        по null будет применяться, даже если filter_by_null методов
        ModelManager будет установлена на False.
        Используется для поддержки возможности фильтрации по null
        конкретных (но не всех) полей фильтрации
        """
        self.value = value
        self.operator = operator
        self.func = func
        self.model = model
        self.alias = alias
        self.filter_by_null = filter_by_null

        # Приводим значение поля к формату, который ожидает SQLAlchemy
        if value:
            if self.operator == "ilike":
                self.value = f"%{self.value}%"
            elif self.func and str(self.func()) == "date()":
                self.value = parser.parse(self.value).date()

    def __bool__(self):
        return self.value is not None

    def __eq__(self, __value: object) -> bool:
        return self.value == __value
