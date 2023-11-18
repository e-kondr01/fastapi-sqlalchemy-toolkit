from typing import Any, Callable, Literal, Type

from dateutil import parser

from .base_model import Base

NullableQuery = Literal["", "null"]
null_query_values = ("", "null")
