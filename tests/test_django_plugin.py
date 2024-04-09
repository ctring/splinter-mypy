from splinter import run_mypy_text, Location, ModelContent, MethodContent


def test_everything():
    messages, _ = run_mypy_text(
        """
from django.db import models, transaction, connection

class MyModel(models.Model):
    name: str
    my_dict: dict[str, str]

    @transaction.atomic
    def my_transaction_method(self):
        pass
        
class MyModelChild(MyModel):
    pass

my_model = MyModel()

my_model.save()
my_model.objects.all()
my_model.objects.filter(name="test")
my_model.objects.raw("SELECT * FROM my_model")

test_dict = {}
test_dict.get("test")

test_list = []
test_list.count()

my_model.my_dict.get("test")

@transaction.atomic
def my_transaction_function():
    pass
    
with transaction.atomic():
    pass
    
# Mypy does not infer return type even for simple functions
# See: https://github.com/python/mypy/issues/4409
def get_model(x: int) -> MyModel:
    return MyModel()

get_model(1).objects.all()

with connection.cursor() as cursor:
    cursor.execute("SELECT * FROM my_model")

class MyQuerySet(models.QuerySet):
    def active(self):
        return self.filter()

""",
        debug=True,
    )

    items: dict[Location, ModelContent | MethodContent] = {}
    for msg in messages:
        if msg.filePath == "<string>":
            loc = Location(
                msg.filePath, msg.fromLine, msg.toLine, msg.fromColumn, msg.toColumn
            )

            assert loc not in items, f"Duplicate location: {loc} {msg.content}"
            items[loc] = msg.content

    expected = [
        ModelContent(name="__main__.MyModel"),
        ModelContent(name="__main__.MyModelChild"),
        MethodContent(
            name="save",
            methodType="write",
            object="my_model",
            objectTypes=[
                "__main__.MyModel",
                "django.db.models.base.Model",
            ],
            attributes=[],
        ),
        MethodContent(
            name="all",
            methodType="read",
            object="my_model.objects",
            objectTypes=[
                "django.db.models.manager.BaseManager",
                "django.db.models.manager.Manager",
                "django.db.models.manager.Manager[__main__.MyModel]",
            ],
            attributes=[],
        ),
        MethodContent(
            name="filter",
            methodType="read",
            object="my_model.objects",
            objectTypes=[
                "django.db.models.manager.BaseManager",
                "django.db.models.manager.Manager",
                "django.db.models.manager.Manager[__main__.MyModel]",
            ],
            attributes=[],
        ),
        MethodContent(
            name="raw",
            methodType="other",
            object="my_model.objects",
            objectTypes=[
                "django.db.models.manager.BaseManager",
                "django.db.models.manager.Manager",
                "django.db.models.manager.Manager[__main__.MyModel]",
            ],
            attributes=[],
        ),
        MethodContent(
            name="my_transaction_method",
            methodType="transaction",
            object="django.db.transaction.atomic",
            objectTypes=["django.db.transaction.atomic"],
            attributes=[],
        ),
        MethodContent(
            name="my_transaction_function",
            methodType="transaction",
            object="django.db.transaction.atomic",
            objectTypes=["django.db.transaction.atomic"],
            attributes=[],
        ),
        MethodContent(
            name="with",
            methodType="transaction",
            object="django.db.transaction.atomic",
            objectTypes=["django.db.transaction.atomic"],
            attributes=[],
        ),
        MethodContent(
            name="all",
            methodType="read",
            object="get_model().objects",
            objectTypes=[
                "django.db.models.manager.BaseManager",
                "django.db.models.manager.Manager",
                "django.db.models.manager.Manager[__main__.MyModel]",
            ],
            attributes=[],
        ),
        MethodContent(
            name="execute",
            methodType="other",
            object="cursor",
            objectTypes=["django.db.backends.utils.CursorWrapper"],
            attributes=[],
        ),
        MethodContent(
            name="filter",
            methodType="read",
            object="self",
            objectTypes=["__main__.MyQuerySet", "django.db.models.query._QuerySet"],
            attributes=[],
        ),
    ]

    for loc, content in items.items():
        assert content in expected, f"Unexpected item: {content}"
        expected.remove(content)

    assert not expected, f"Missing items: {expected}"
