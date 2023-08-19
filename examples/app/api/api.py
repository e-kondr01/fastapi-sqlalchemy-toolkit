from fastapi import APIRouter

from app.api.endpoints import child

api_router = APIRouter()
api_router.include_router(
    child.router,
    prefix="/children",
    tags=["Demo"],
)
