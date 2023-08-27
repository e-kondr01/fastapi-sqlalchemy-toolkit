from fastapi_sqlalchemy_toolkit import ModelManager

from .models import Child
from .schemas import CreateUpdateChildSchema

child_manager = ModelManager[Child, CreateUpdateChildSchema, CreateUpdateChildSchema](
    Child
)
