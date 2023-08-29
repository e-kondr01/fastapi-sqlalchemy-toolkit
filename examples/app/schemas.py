from uuid import UUID

from fastapi_sqlalchemy_toolkit.utils import make_partial_model
from pydantic import BaseModel


class ChildBaseSchema(BaseModel):
    title: str
    slug: str


class CreateChildSchema(ChildBaseSchema):
    parent_id: UUID


PatchChildSchema = make_partial_model(CreateChildSchema)


class ParentBaseSchema(BaseModel):
    title: str
    slug: str


class RetrieveChildSchema(ChildBaseSchema):
    parent: ParentBaseSchema


class RetrieveParentSchema(ParentBaseSchema):
    children: list[ChildBaseSchema] | None


class HTTPErrorSchema(BaseModel):
    detail: str
