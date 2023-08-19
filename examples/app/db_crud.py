from fastapi_sqlalchemy_toolkit import BaseCRUD

from app.models import Child, Parent
from app.schemas import CreateUpdateChildSchema, ParentBaseSchema

child_db = BaseCRUD[Child, CreateUpdateChildSchema, CreateUpdateChildSchema](Child)
parent_db = BaseCRUD[Parent, ParentBaseSchema, ParentBaseSchema](Parent)
