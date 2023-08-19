from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from fastapi_pagination import Page, Params
from fastapi_sqlalchemy_toolkit import FieldFilter, ordering_dep
from sqlalchemy.ext.asyncio import AsyncSession

from app.db_crud import child_db
from app.deps import get_async_session
from app.models import Parent
from app.schemas import CreateUpdateChildSchema, RetrieveChildSchema

router = APIRouter()

CurrentSession = Annotated[AsyncSession, Depends(get_async_session)]
PaginationParams = Annotated[Params, Depends()]

children_ordering_fields = (Parent.created_at, Parent.title, "created_at", "title")


@router.get("")
async def get_children(
    session: CurrentSession,
    order_by: ordering_dep(children_ordering_fields),
    params: PaginationParams,
    title: str | None = None,
    slug: str | None = None,
    parent_title: str | None = None,
    parent_slug: str | None = None,
) -> Page[RetrieveChildSchema]:
    return await child_db.paginated_filter(
        session=session,
        pagination_params=params,
        title=FieldFilter(value=title, operator="ilike"),
        slug=slug,
        parent_title=FieldFilter(value=parent_title, operator="ilike", model=Parent),
        parent_slug=FieldFilter(value=parent_slug, model=Parent),
        order_by=order_by,
    )


@router.get("/{child_id}")
async def get_child(
    child_id: UUID,
    session: CurrentSession,
) -> RetrieveChildSchema:
    return await child_db.get_or_404(
        session=session,
        id=child_id,
    )


@router.post("")
async def create_child(
    child_in: CreateUpdateChildSchema, session: CurrentSession
) -> CreateUpdateChildSchema:
    return await child_db.create(session=session, in_obj=child_in)


@router.patch("/{child_id}")
async def update_child(
    child_id: UUID, child_in: CreateUpdateChildSchema, session: CurrentSession
) -> CreateUpdateChildSchema:
    child_to_update = await child_db.get_or_404(session=session, id=child_id)
    return await child_db.update(
        session=session, db_obj=child_to_update, in_obj=child_in
    )


@router.delete("/{child_id}")
async def delete_child(child_id: UUID, session: CurrentSession) -> Response:
    child_to_delete = await child_db.get_or_404(session=session, id=child_id)
    await child_db.delete(session=session, db_obj=child_to_delete)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
