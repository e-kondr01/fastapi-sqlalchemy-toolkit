### Инициализация ModelManager

Для взаимодействия с моделью `SQLAlchemy`, `fastapi-sqlalchemy-toolkit` предоставляет
класс `ModelManager`. Его методы используются для взаимодействия с БД.

Создать экземпляр `ModelManager` для конкретной модели можно следующим образом:

```python
from fastapi_sqlalchemy_toolkit import ModelManager

from .models import MyModel
from .schemas import MyModelCreateSchema, MyModelUpdateSchema

my_model_manager = ModelManager[MyModel, MyModelCreateSchema, MyModelUpdateSchema](
    MyModel
)
```

В качестве аргумента передаётся модель `SQLAlchemy`. Кроме того, используется параметризация типов 
класса `ModelManager`. В параметры типа передаётся модель `SQLAlchemy`, `Pydantic` модель для
создания объекта и `Pydantic` модель для обновления объекта.

Атрибут `default_ordering` определяет сортировку по умолчанию при получении списка объектов.
В него можно передать поле модели:

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

Использование методов `paginated_list` и `paginated_filter`, согласно документации 
`fastapi_pagination`, требует применения `fastapi_pagination.add_pagination`
к приложению `FastAPI`, и использование `fastapi_pagination.Page` в типизации ответа
эндпоинта FastAPI.

Также доступны следующие методы для выполнения действий "пачкой":

- `bulk_create` - создание объектов (частично выполняет валидацию на уровне БД)
- `bulk_update` - обновление объектов (не выполняет валидацию на уровне БД)
- `bulk_delete` - удаление объектов
