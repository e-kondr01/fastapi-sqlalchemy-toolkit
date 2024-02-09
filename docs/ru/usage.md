### Инициализация ModelManager

Для использования `fastapi-sqlaclhemy-toolkit` необходимо создать экземпляр `ModelManager` для своей модели:

```python
from fastapi_sqlalchemy_toolkit import ModelManager

from .models import MyModel
from .schemas import MyModelCreateSchema, MyModelUpdateSchema

my_model_manager = ModelManager[MyModel, MyModelCreateSchema, MyModelUpdateSchema](MyModel)
```

Атрибут `default_ordering` определяет сортировку по умолчанию при получении списка объектов. В него нужно передать поле основной модели.

```python
from fastapi_sqlalchemy_toolkit import ModelManager

from .models import MyModel
from .schemas import MyModelCreateSchema, MyModelUpdateSchema

my_model_manager = ModelManager[MyModel, MyModelCreateSchema, MyModelUpdateSchema](
    MyModel, default_ordering=MyModel.title
)
```

### Методы ModelManager

Ниже перечислены CRUD методы, предоставляемые `ModelManager`.
Документация параметров, принимаемых методами, находится в докстрингах методов.

- `create` - создание объекта; выполняет валидацию значений полей на уровне БД
- `get` - получение объекта
- `get_or_404` - получение объекта или ошибки HTTP 404
- `exists` - проверка существования объекта
- `paginated_list` / `paginated_filter` - получение списка объектов с фильтрами и пагинацией через `fastapi_pagination`
- `list` / `filter` - получение списка объектов с фильтрами
- `count` - получение количества объектов
- `update` - обновление объекта; выполняет валидацию значений полей на уровне БД
- `delete` - удаление объекта
