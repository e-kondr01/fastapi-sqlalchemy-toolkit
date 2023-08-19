from uuid import UUID

from pydantic import BaseModel


class ChildBaseSchema(BaseModel):
    title: str
    slug: str


class CreateUpdateChildSchema(ChildBaseSchema):
    parent_id: UUID


class ParentBaseSchema(BaseModel):
    title: str
    slug: str


class RetrieveChildSchema(ChildBaseSchema):
    parent: ParentBaseSchema


class RetrieveParentSchema(ParentBaseSchema):
    children: list[ChildBaseSchema | None]
