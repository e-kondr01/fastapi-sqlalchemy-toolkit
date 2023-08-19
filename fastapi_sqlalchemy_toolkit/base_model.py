from datetime import datetime
from uuid import UUID as _py_uuid
from uuid import uuid4

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column


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

    def to_dict(self):
        db_obj_dict = self.__dict__.copy()
        del db_obj_dict["_sa_instance_state"]
        return db_obj_dict
