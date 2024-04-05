from splinter import run_mypy_text


def test_everything():
    messages, _ = run_mypy_text(
        """
from django.db import models

class MyModel(models.Model):
    name: str

my_model = MyModel()

my_model.save()
my_model.objects.all()
my_model.objects.filter(name="test")
"""
    )

    found_model = False
    found_filter = False

    for msg in messages:
        if "MyModel" in msg.content.name:
            found_model = True

        elif msg.content.name == "filter":
            found_filter = True
            assert msg.content.methodType == "read"
            assert msg.content.object == "my_model.objects"
            assert (
                msg.content.objectType
                == "django.db.models.manager.Manager[__main__.MyModel]"
            )

        elif msg.content.name == "save":
            assert msg.content.methodType == "write"
            assert msg.content.object == "my_model"
            assert msg.content.objectType == "__main__.MyModel"

    assert found_model, "Model not found"
    assert found_filter, "objects.filter not found"
