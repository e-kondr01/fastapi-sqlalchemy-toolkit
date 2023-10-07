from fastapi_sqlalchemy_toolkit import ModelManager

from .models import Child
from .schemas import CreateChildSchema, PatchChildSchema

child_manager = ModelManager[Child, CreateChildSchema, PatchChildSchema](
    Child, default_ordering=Child.title
)
