### ModelManager initialization

To use `fastapi-sqlaclhemy-toolkit`, you need to create an instance of `ModelManager` for your model:

```python
from fastapi_sqlalchemy_toolkit import ModelManager

from .models import MyModel
from .schemas import MyModelCreateSchema, MyModelUpdateSchema

my_model_manager = ModelManager[MyModel, MyModelCreateSchema, MyModelUpdateSchema](MyModel)
```

The `default_ordering` attribute defines the default sorting when retrieving a list of objects. You should pass the primary model field to it.

```python
from fastapi_sqlalchemy_toolkit import ModelManager

from .models import MyModel
from .schemas import MyModelCreateSchema, MyModelUpdateSchema

my_model_manager = ModelManager[MyModel, MyModelCreateSchema, MyModelUpdateSchema](
    MyModel, default_ordering=MyModel.title
)
```

### ModelManager methods

Below are the CRUD methods provided by `ModelManager`. Documentation for the parameters accepted by these methods can be found in the method docstrings.

- `create` - creates an object; performs validation of field values at the database level
- `get` - retrieves an object
- `get_or_404` - retrieves an object or returns HTTP 404 error
- `exists` - checks the existence of an object
- `paginated_list` / `paginated_filter` - retrieves a list of objects with filters and pagination through `fastapi_pagination`
- `list` / `filter` - retrieves a list of objects with filters
- `count` - retrieves the count of objects
- `update` - updates an object; performs validation of field values at the database level
- `delete` - deletes an object
