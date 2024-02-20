from datetime import datetime
from uuid import UUID, uuid4

from fastapi_sqlalchemy_toolkit.model_manager import ModelManager
from pydantic import BaseModel
from sqlalchemy import Column, DateTime, ForeignKey, Table, UniqueConstraint, func
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    declared_attr,
    mapped_column,
    relationship,
)


class Base(DeclarativeBase):
    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
        server_default=func.gen_random_uuid(),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    @declared_attr.directive
    def __tablename__(cls) -> str:
        return cls.__name__.lower()


categories_parents_association = Table(
    "categories_parents_m2m",
    Base.metadata,
    Column("category_id", ForeignKey("category.id"), primary_key=True),
    Column("parent_id", ForeignKey("parent.id"), primary_key=True),
)


class Category(Base):
    title: Mapped[str] = mapped_column(unique=True)

    parents: Mapped[list["Parent"]] = relationship(
        back_populates="categories", secondary=categories_parents_association
    )


class CategorySchema(BaseModel):
    title: str


class Parent(Base):
    __table_args__ = (UniqueConstraint("title", "description"),)

    title: Mapped[str]
    slug: Mapped[str] = mapped_column(unique=True)
    description: Mapped[str | None]

    children: Mapped[list["Child"]] = relationship(back_populates="parent")
    categories: Mapped[list["Category"]] = relationship(
        back_populates="parents", secondary=categories_parents_association
    )


class ParentSchema(BaseModel):
    title: str
    slug: str
    description: str | None = None


class Child(Base):
    title: Mapped[str]
    slug: Mapped[str] = mapped_column(unique=True)

    parent_id: Mapped[UUID] = mapped_column(ForeignKey("parent.id", ondelete="CASCADE"))
    parent: Mapped[Parent] = relationship(back_populates="children")


class ChildSchema(BaseModel):
    title: str
    slug: str
    parent_id: UUID


child_manager = ModelManager[Child, ChildSchema, ChildSchema](
    Child, default_ordering=Child.title
)
parent_manager = ModelManager[Parent, ParentSchema, ParentSchema](Parent)
category_manager = ModelManager[Category, CategorySchema, CategorySchema](Category)
