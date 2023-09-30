from typing import Annotated
from uuid import UUID

from app.deps import get_async_session
from app.managers import child_manager
from app.models import Child, Parent
from app.schemas import (
    ChildDetailSchema,
    ChildListSchema,
    CreateChildSchema,
    HTTPErrorSchema,
    PatchChildSchema,
)
from fastapi import APIRouter, Depends, Response, status
from fastapi_pagination import Page, Params
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from fastapi_sqlalchemy_toolkit import FieldFilter, ordering_dep

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
) -> Page[ChildListSchema]:
    return await child_manager.paginated_list(
        # Обязательные параметры
        session=session,
        pagination_params=params,
        # Фильтры
        title=FieldFilter(title, operator="ilike"),
        slug=slug,
        parent_title=FieldFilter(
            parent_title, operator="ilike", model=Parent, alias="title"
        ),
        parent_slug=FieldFilter(parent_slug, model=Parent, alias="slug"),
        # Сортировка
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
) -> ChildDetailSchema:
    return await child_manager.get_or_404(
        session=session,
        id=child_id,
        options=joinedload(Child.parent),
    )


@router.post("")
async def create_child(
    child_in: CreateChildSchema, session: CurrentSession
) -> ChildListSchema:
    return await child_manager.create(session=session, in_obj=child_in)


@router.patch(
    "/{child_id}",
    responses={
        status.HTTP_404_NOT_FOUND: {"model": HTTPErrorSchema},
    },
)
async def update_child(
    child_id: UUID, child_in: PatchChildSchema, session: CurrentSession
) -> ChildListSchema:
    child_to_update = await child_manager.get_or_404(session=session, id=child_id)
    return await child_manager.update(
        session=session, db_obj=child_to_update, in_obj=child_in
    )


@router.delete(
    "/{child_id}",
    responses={
        status.HTTP_404_NOT_FOUND: {"model": HTTPErrorSchema},
    },
)
async def delete_child(child_id: UUID, session: CurrentSession) -> Response:
    child_to_delete = await child_manager.get_or_404(session=session, id=child_id)
    await child_manager.delete(session=session, db_obj=child_to_delete)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
