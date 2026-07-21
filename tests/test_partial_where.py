# ruff: noqa: S101
from enum import Enum

from sqlalchemy import Index, and_, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from fastapi_sqlalchemy_toolkit.model_manager import ModelManager


class _Base(DeclarativeBase):
    pass


class _Kind(Enum):
    MAIN = "main"
    EXTRA = "extra"


class _Model(_Base):
    __tablename__ = "partial_where_model"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str]
    group_id: Mapped[int]
    active: Mapped[bool]


def test_none_condition_matches() -> None:
    assert ModelManager._matches_partial_index_where(None, {"kind": "extra"}) is True


def test_text_clause_main_matches() -> None:
    for condition in (
        text("kind = 'main'"),
        text('kind = "main"'),
        text("kind = main"),
    ):
        assert (
            ModelManager._matches_partial_index_where(condition, {"kind": "main"})
            is True
        )
        assert (
            ModelManager._matches_partial_index_where(condition, {"kind": "extra"})
            is False
        )


def test_binary_expression_matches() -> None:
    index = Index(
        "ix",
        _Model.group_id,
        unique=True,
        postgresql_where=(_Model.kind == "main"),
    )
    condition = index.dialect_options["postgresql"]["where"]
    assert (
        ModelManager._matches_partial_index_where(condition, {"kind": "main"}) is True
    )
    assert (
        ModelManager._matches_partial_index_where(condition, {"kind": "extra"}) is False
    )


def test_binary_expression_with_enum_matches() -> None:
    index = Index(
        "ix_enum",
        _Model.group_id,
        unique=True,
        postgresql_where=(_Model.kind == _Kind.MAIN),
    )
    condition = index.dialect_options["postgresql"]["where"]
    assert (
        ModelManager._matches_partial_index_where(condition, {"kind": "main"}) is True
    )
    assert (
        ModelManager._matches_partial_index_where(condition, {"kind": _Kind.MAIN})
        is True
    )
    assert (
        ModelManager._matches_partial_index_where(condition, {"kind": "extra"}) is False
    )


def test_boolean_clause_list_matches() -> None:
    index = Index(
        "ix_and",
        _Model.group_id,
        unique=True,
        postgresql_where=and_(_Model.kind == "main", _Model.active == True),  # noqa: E712
    )
    condition = index.dialect_options["postgresql"]["where"]
    assert (
        ModelManager._matches_partial_index_where(
            condition, {"kind": "main", "active": True}
        )
        is True
    )
    assert (
        ModelManager._matches_partial_index_where(
            condition, {"kind": "main", "active": False}
        )
        is False
    )
    assert (
        ModelManager._matches_partial_index_where(
            condition, {"kind": "extra", "active": True}
        )
        is False
    )


def test_unsupported_text_fail_safe() -> None:
    condition = text("kind IN ('main', 'special')")
    assert (
        ModelManager._matches_partial_index_where(condition, {"kind": "extra"}) is True
    )
