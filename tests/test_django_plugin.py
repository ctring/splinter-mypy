from splinter import run_mypy_text, Location, ModelContent, MethodContent


def test_everything():
    messages, _ = run_mypy_text(
        """
from django.db import models, transaction

class MyModel(models.Model):
    name: str

    @transaction.atomic
    def my_transaction_method(self):
        pass

my_model = MyModel()

my_model.save()
my_model.objects.all()
my_model.objects.filter(name="test")

@transaction.atomic
def my_transaction_function():
    pass
    
with transaction.atomic():
    pass
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
        MethodContent(
            name="save",
            methodType="write",
            object="my_model",
            objectType="__main__.MyModel",
            attributes=[],
        ),
        MethodContent(
            name="all",
            methodType="read",
            object="my_model.objects",
            objectType="django.db.models.manager.Manager[__main__.MyModel]",
            attributes=[],
        ),
        MethodContent(
            name="filter",
            methodType="read",
            object="my_model.objects",
            objectType="django.db.models.manager.Manager[__main__.MyModel]",
            attributes=[],
        ),
        MethodContent(
            name="my_transaction_method",
            methodType="transaction",
            object="django.db.transaction.atomic",
            objectType="django.db.transaction.atomic",
            attributes=[],
        ),
        MethodContent(
            name="my_transaction_function",
            methodType="transaction",
            object="django.db.transaction.atomic",
            objectType="django.db.transaction.atomic",
            attributes=[],
        ),
        MethodContent(
            name="with",
            methodType="transaction",
            object="django.db.transaction.atomic",
            objectType="django.db.transaction.atomic",
            attributes=[],
        ),
    ]

    for loc, content in items.items():
        assert content in expected, f"Unexpected item: {content}"
        expected.remove(content)

    assert not expected, f"Missing items: {expected}"
