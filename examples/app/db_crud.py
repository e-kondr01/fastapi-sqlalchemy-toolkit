from fastapi_sqlalchemy_toolkit import BaseCRUD

from .models import Child, Parent
from .schemas import CreateUpdateChildSchema, ParentBaseSchema

child_db = BaseCRUD[Child, CreateUpdateChildSchema, CreateUpdateChildSchema](Child)
parent_db = BaseCRUD[Parent, ParentBaseSchema, ParentBaseSchema](Parent)
