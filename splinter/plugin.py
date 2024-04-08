import json
import sys
from typing import Callable, List, Union
from mypy.plugin import (
    FunctionContext,
    Plugin,
    ClassDefContext,
    MethodContext,
)
from mypy.nodes import MemberExpr, NameExpr, CallExpr, Decorator
from mypy.types import Type

from splinter import (
    _MESSAGES,
    _LOCATIONS,
    _STATS,
    _DEBUG,
    Message,
    ModelContent,
    MethodContent,
    Location,
    Content,
)


def debug(msg):
    if _DEBUG:
        if isinstance(msg, Message):
            print(
                f"DEBUG: {json.dumps(msg, default=lambda o: vars(o))}",
                file=sys.stderr,
            )
        else:
            print("DEBUG", *msg, file=sys.stderr)


def output(location: Location, content: Content):
    if location in _LOCATIONS:
        return
    _LOCATIONS.add(location)

    msg = Message(location, content)

    debug(msg)

    _MESSAGES.append(msg)
    _STATS[type(Content)] += 1

    print(f"Found {_STATS[ModelContent]} models and {_STATS[MethodContent]} methods")


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
        API_OTHER = ["raw"]

        def callback(ctx: MethodContext) -> Type:
            # Only consider method calls
            if not isinstance(ctx.context, CallExpr):
                return ctx.default_return_type

            # Skip method call on another call (e.g. functools.wraps(view_func)(wrapped_view))
            if isinstance(ctx.context.callee, CallExpr):
                return ctx.default_return_type

            methodType = None
            if ctx.context.callee.name in API_READ:
                methodType = "read"
            elif ctx.context.callee.name in API_WRITE:
                methodType = "write"
            elif ctx.context.callee.name in API_OTHER:
                methodType = "other"

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

    def get_function_hook(
        self, fullname: str
    ) -> Callable[[FunctionContext], Type] | None:

        def callback(ctx: FunctionContext) -> Type:
            if fullname == "django.db.transaction.atomic":
                name = "<unknown>"
                objectType = "<unknown>"
                if isinstance(ctx.context, Decorator):
                    name = ctx.context.func.name
                elif isinstance(ctx.context, CallExpr):
                    name = "transaction.atomic"

                message = Message(
                    ctx.api.path,
                    ctx.context.line,
                    ctx.context.end_line,
                    ctx.context.column,
                    ctx.context.end_column,
                    content=MethodContent(
                        name=name,
                        methodType="transaction",
                        object="django.db.transaction.atomic",
                        objectType="django.db.transaction.atomic",
                        attributes=[],
                    ),
                )
                output(message)

            return ctx.default_return_type

        return callback


def plugin(version: str):
    return DjangoAnalyzer
