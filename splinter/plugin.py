import json
import sys
from typing import Callable, List, Union
from mypy.plugin import Plugin, ClassDefContext, MethodContext
from mypy.nodes import MemberExpr, NameExpr
from mypy.types import Type
from splinter import OUTPUT

API_READ = ["filter"]
API_WRITE = ["save", "delete"]


class JsonMessage:
    type: str

    def __init__(self, type: str):
        self.type = type


class ModelMessage(JsonMessage):
    name: str

    def __init__(self, name: str):
        self.type = "model"
        self.name = name


class Attribute:
    name: str
    start_line: str
    end_line: str
    start_column: str
    end_column: str


class MethodMessage(JsonMessage):
    name: str
    method_type: str
    object: str
    object_types: List[str]
    attributes: List[Attribute]

    def __init__(
        self,
        name: str,
        methodType: str,
        object: str,
        objectTypes: List[str],
        attributes: List[Attribute],
    ):
        self.type = "method"
        self.name = name
        self.method_type = methodType
        self.object = object
        self.object_types = objectTypes
        self.attributes = attributes


class Message:
    file_path: str
    from_line: int
    to_line: int
    from_column: int
    to_column: int
    content: Union[ModelMessage, MethodMessage]

    def __init__(
        self,
        filePath: str,
        fromLine: int,
        toLine: int,
        fromColumn: int,
        toColumn: int,
        content: Union[ModelMessage, MethodMessage],
    ):
        self.file_path = filePath
        self.from_line = fromLine
        self.to_line = toLine
        self.from_column = fromColumn
        self.to_column = toColumn
        self.content = content


def debug(*msg):
    print(*msg, file=sys.stderr)


def output(msg: Message):
    OUTPUT.append(msg)
    print(json.dumps(msg, default=lambda o: vars(o)), file=sys.stderr)


class DjangoAnalyzer(Plugin):
    def get_customize_class_mro_hook(
        self, fullname: str
    ) -> Union[Callable[[ClassDefContext], None], None]:
        """Collects the model definitions."""

        def callback(ctx: ClassDefContext):
            current_file = ctx.api.modules[ctx.api.cur_mod_id]
            if ctx.cls.base_type_exprs:
                for base_type_expr in ctx.cls.base_type_exprs:
                    if (
                        isinstance(base_type_expr, NameExpr)
                        or isinstance(base_type_expr, MemberExpr)
                    ) and base_type_expr.fullname == "django.db.models.base.Model":
                        message = Message(
                            current_file.path,
                            ctx.cls.line,
                            ctx.cls.end_line,
                            ctx.cls.column,
                            ctx.cls.end_column,
                            content=ModelMessage(ctx.cls.name),
                        )
                        output(message)

        return callback

    # def get_method_hook(
    #     self, fullname: str
    # ) -> Union[Callable[[MethodContext], Type], None]:
    #     """Collects the model method calls."""

    #     def callback(ctx: MethodContext) -> Type:
    #         if "filter" in fullname and "django" in fullname:
    #             debug(
    #                 fullname, ":", ctx.type.type, ctx.type.args, ctx.context.callee.name
    #             )
    #         return ctx.default_return_type

    #     return callback


def plugin(version: str):
    return DjangoAnalyzer
