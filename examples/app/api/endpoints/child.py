from typing import Annotated
from uuid import UUID

from app.deps import get_async_session
from app.managers import child_manager
from app.models import Parent
from app.schemas import (
    CreateChildSchema,
    HTTPErrorSchema,
    PatchChildSchema,
    RetrieveChildSchema,
)
from fastapi import APIRouter, Depends, Response, status
from fastapi_pagination import Page, Params
from fastapi_sqlalchemy_toolkit import FieldFilter, ordering_dep
from sqlalchemy.ext.asyncio import AsyncSession


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
    return await child_manager.paginated_filter(
        session=session,
        pagination_params=params,
        title=FieldFilter(value=title, operator="ilike"),
        slug=slug,
        parent_title=FieldFilter(value=parent_title, operator="ilike", model=Parent),
        parent_slug=FieldFilter(value=parent_slug, model=Parent),
        order_by=order_by,
    )


@router.get(
    "/{child_id}",
    responses={
        status.HTTP_404_NOT_FOUND: {"model": HTTPErrorSchema},
    },
)
async def get_child(
    child_id: UUID,
    session: CurrentSession,
) -> RetrieveChildSchema:
    return await child_manager.get_or_404(
        session=session,
        id=child_id,
    )


@router.post("")
async def create_child(
    child_in: CreateChildSchema, session: CurrentSession
) -> CreateChildSchema:
    return await child_manager.create(session=session, in_obj=child_in)


@router.get(
    "/{child_id}",
    responses={
        status.HTTP_404_NOT_FOUND: {"model": HTTPErrorSchema},
    },
)
@router.patch("/{child_id}")
async def update_child(
    child_id: UUID, child_in: PatchChildSchema, session: CurrentSession
) -> PatchChildSchema:
    child_to_update = await child_manager.get_or_404(session=session, id=child_id)
    return await child_manager.update(
        session=session, db_obj=child_to_update, in_obj=child_in
    )


@router.get(
    "/{child_id}",
    responses={
        status.HTTP_404_NOT_FOUND: {"model": HTTPErrorSchema},
    },
)
@router.delete("/{child_id}")
async def delete_child(child_id: UUID, session: CurrentSession) -> Response:
    child_to_delete = await child_manager.get_or_404(session=session, id=child_id)
    await child_manager.delete(session=session, db_obj=child_to_delete)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
