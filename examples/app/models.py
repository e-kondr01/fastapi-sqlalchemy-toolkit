from uuid import UUID

from fastapi_sqlalchemy_toolkit import Base
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship


class Parent(Base):
    title: Mapped[str]
    slug: Mapped[str] = mapped_column(unique=True)

    children: Mapped[list["Child"]] = relationship(back_populates="parent")


class Child(Base):
    title: Mapped[str]
    slug: Mapped[str] = mapped_column(unique=True)

    parent_id: Mapped[UUID] = mapped_column(ForeignKey("parent.id", ondelete="CASCADE"))
    parent: Mapped[Parent] = relationship(back_populates="children")
