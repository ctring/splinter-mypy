import json
import sys
from typing import Callable, List, Union
from mypy.plugin import Plugin, ClassDefContext, MethodContext
from mypy.nodes import MemberExpr, NameExpr, CallExpr
from mypy.types import Type

from splinter import _MESSAGES, _MODELS


class Content:
    type: str

    def __init__(self, type: str):
        self.type = type


class ModelContent(Content):
    name: str

    def __init__(self, name: str):
        self.type = "model"
        self.name = name


class Attribute:
    name: str
    startLine: str
    endLine: str
    startColumn: str
    endColumn: str


class MethodContent(Content):
    name: str
    methodType: str
    object: str
    objectType: str
    attributes: List[Attribute]

    def __init__(
        self,
        name: str,
        methodType: str,
        object: str,
        objectType: str,
        attributes: List[Attribute],
    ):
        self.type = "method"
        self.name = name
        self.methodType = methodType
        self.object = object
        self.objectType = objectType
        self.attributes = attributes


class Message:
    filePath: str
    fromLine: int
    toLine: int
    fromColumn: int
    toColumn: int
    content: Content

    def __init__(
        self,
        filePath: str,
        fromLine: int,
        toLine: int,
        fromColumn: int,
        toColumn: int,
        content: Content,
    ):
        self.filePath = filePath
        self.fromLine = fromLine
        self.toLine = toLine
        self.fromColumn = fromColumn
        self.toColumn = toColumn
        self.content = content


def debug(*msg):
    print("DEBUG", *msg, file=sys.stderr)


def output(msg: Message):
    if isinstance(msg.content, ModelContent):
        if msg.content.name in _MODELS:
            return
        _MODELS.add(msg.content.name)

    _MESSAGES.append(msg)
    print(json.dumps(msg, default=lambda o: vars(o)), file=sys.stderr)


def recover_expr_name(expr):
    if isinstance(expr, NameExpr):
        return expr.name
    if isinstance(expr, MemberExpr):
        return f"{recover_expr_name(expr.expr)}.{expr.name}"
    return None


class DjangoAnalyzer(Plugin):
    def get_customize_class_mro_hook(
        self, fullname: str
    ) -> Union[Callable[[ClassDefContext], None], None]:
        """Collects the model definitions."""

        def callback(ctx: ClassDefContext):
            if ctx.cls.base_type_exprs:
                for base_type_expr in ctx.cls.base_type_exprs:
                    if (
                        isinstance(base_type_expr, NameExpr)
                        or isinstance(base_type_expr, MemberExpr)
                    ) and base_type_expr.fullname == "django.db.models.base.Model":
                        current_file = ctx.api.modules[ctx.api.cur_mod_id]
                        message = Message(
                            current_file.path,
                            ctx.cls.line,
                            ctx.cls.end_line,
                            ctx.cls.column,
                            ctx.cls.end_column,
                            content=ModelContent(ctx.cls.fullname),
                        )
                        output(message)

        return callback

    def get_method_hook(
        self, fullname: str
    ) -> Union[Callable[[MethodContext], Type], None]:
        """Collects the model method calls."""

        API_READ = [
            "filter",
            "all",
            "get",
            "exclude",
            "remove",
            "add",
            "aggregate",
            "first",
            "last",
            "count",
        ]
        API_WRITE = ["save", "delete", "create", "update"]

        def callback(ctx: MethodContext) -> Type:
            if isinstance(ctx.context, CallExpr):
                methodType = None
                if ctx.context.callee.name in API_READ:
                    methodType = "read"
                elif ctx.context.callee.name in API_WRITE:
                    methodType = "write"

                if methodType:
                    message = Message(
                        ctx.api.path,
                        ctx.context.line,
                        ctx.context.end_line,
                        ctx.context.column,
                        ctx.context.end_column,
                        content=MethodContent(
                            name=ctx.context.callee.name,
                            methodType=methodType,
                            object=recover_expr_name(ctx.context.callee.expr),
                            objectType=str(ctx.type),
                            attributes=[],
                        ),
                    )
                    output(message)

            return ctx.default_return_type

        return callback


def plugin(version: str):
    return DjangoAnalyzer
