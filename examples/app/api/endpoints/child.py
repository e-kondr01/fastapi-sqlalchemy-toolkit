from datetime import date
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
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from fastapi_sqlalchemy_toolkit import ordering_dep

router = APIRouter()

Session = Annotated[AsyncSession, Depends(get_async_session)]
PaginationParams = Annotated[Params, Depends()]

children_ordering_fields = (Parent.created_at, Parent.title, "created_at", "title")


@router.get("")
async def get_list(
    session: Session,
    order_by: ordering_dep(children_ordering_fields),
    pagination_params: PaginationParams,
    title: str | None = None,
    slug: str | None = None,
    parent_title: str | None = None,
    parent_slug: str | None = None,
    created_at_date: date | None = None,
) -> Page[ChildListSchema]:
    return await child_manager.paginated_list(
        # Обязательные параметры
        session,
        pagination_params,
        # Фильтры
        slug=slug,
        filter_expressions={
            Child.title.ilike: title,
            Parent.slug: parent_slug,
            Parent.title.ilike: parent_title,
            func.date(Child.created_at): created_at_date,
        },
        # Сортировка
        order_by=order_by,
    )


@router.get(
    "/{object_id}",
    responses={
        status.HTTP_404_NOT_FOUND: {"model": HTTPErrorSchema},
    },
)
async def retrieve(
    object_id: UUID,
    session: Session,
) -> ChildDetailSchema:
    return await child_manager.get_or_404(
        session,
        id=object_id,
        options=joinedload(Child.parent),
    )


@router.post("")
async def create(in_obj: CreateChildSchema, session: Session) -> ChildListSchema:
    return await child_manager.create(session, in_obj=in_obj)


@router.patch(
    "/{object_id}",
    responses={
        status.HTTP_404_NOT_FOUND: {"model": HTTPErrorSchema},
    },
)
async def update_child(
    object_id: UUID, in_obj: PatchChildSchema, session: Session
) -> ChildListSchema:
    db_obj = await child_manager.get_or_404(session, id=object_id)
    return await child_manager.update(session, db_obj=db_obj, in_obj=in_obj)


@router.delete(
    "/{object_id}",
    responses={
        status.HTTP_404_NOT_FOUND: {"model": HTTPErrorSchema},
    },
)
async def delete(object_id: UUID, session: Session) -> Response:
    db_obj = await child_manager.get_or_404(session=session, id=object_id)
    await child_manager.delete(session, db_obj=db_obj)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
