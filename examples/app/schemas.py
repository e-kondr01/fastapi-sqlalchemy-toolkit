from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from fastapi_sqlalchemy_toolkit.utils import make_partial_model


class ChildBaseSchema(BaseModel):
    title: str
    slug: str


class CreateChildSchema(ChildBaseSchema):
    parent_id: UUID


PatchChildSchema = make_partial_model(CreateChildSchema)


class ParentBaseSchema(BaseModel):
    title: str
    slug: str


class ChildListSchema(ChildBaseSchema):
    id: UUID
    created_at: datetime


class ChildDetailSchema(ChildListSchema):
    parent: ParentBaseSchema


class HTTPErrorSchema(BaseModel):
    detail: str
