from datetime import datetime
from uuid import UUID
from uuid import UUID as _py_uuid
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    declared_attr,
    mapped_column,
    relationship,
)


class Base(DeclarativeBase):
    id: Mapped[_py_uuid] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    @declared_attr.directive
    def __tablename__(cls) -> str:
        return cls.__name__.lower()


class Parent(Base):
    title: Mapped[str]
    slug: Mapped[str] = mapped_column(unique=True)

    children: Mapped[list["Child"]] = relationship(back_populates="parent")


class Child(Base):
    title: Mapped[str]
    slug: Mapped[str] = mapped_column(unique=True)

    parent_id: Mapped[UUID] = mapped_column(ForeignKey("parent.id", ondelete="CASCADE"))
    parent: Mapped[Parent] = relationship(back_populates="children")
