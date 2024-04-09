import json
import sys
from typing import Callable, Union
from mypy.plugin import (
    FunctionContext,
    Plugin,
    ClassDefContext,
    MethodContext,
)
from mypy.nodes import MemberExpr, NameExpr, CallExpr, Decorator, IndexExpr
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
)


def debug(*msg):
    if _DEBUG:
        if isinstance(msg[0], Message):
            print(
                f"DEBUG: {json.dumps(msg, default=lambda o: vars(o))}",
                file=sys.stderr,
            )
        else:
            print("DEBUG", *msg, file=sys.stderr)


def output(location: Location, content: ModelContent | MethodContent):
    if location in _LOCATIONS:
        return
    _LOCATIONS.add(location)

    msg = Message(location, content)

    debug(msg)

    _MESSAGES.append(msg)
    _STATS[type(content)] += 1

    print(f"Found {_STATS[ModelContent]} models and {_STATS[MethodContent]} methods")


def recover_expr_name(expr: MemberExpr | NameExpr):
    if isinstance(expr, NameExpr):
        return expr.name
    if isinstance(expr, MemberExpr):
        if isinstance(expr.expr, NameExpr) or isinstance(expr.expr, MemberExpr):
            return f"{recover_expr_name(expr.expr)}.{expr.name}"
        else:
            raise ValueError(f"Unexpected expression type: {expr.expr}")
    return None


class DjangoAnalyzer(Plugin):
    def get_customize_class_mro_hook(
        self, fullname: str
    ) -> Union[Callable[[ClassDefContext], None], None]:
        """Collects the model definitions."""

        def callback(ctx: ClassDefContext):
            if ctx.cls.base_type_exprs:
                for base_type_expr in ctx.cls.base_type_exprs:
                    if isinstance(base_type_expr, NameExpr) or isinstance(
                        base_type_expr, MemberExpr
                    ):
                        if base_type_expr.fullname == "django.db.models.base.Model":
                            current_file = ctx.api.modules[ctx.api.cur_mod_id]
                            output(
                                Location(
                                    current_file.path,
                                    ctx.cls.line,
                                    ctx.cls.end_line or ctx.cls.line,
                                    ctx.cls.column,
                                    ctx.cls.end_column or ctx.cls.column,
                                ),
                                ModelContent(name=ctx.cls.fullname),
                            )
                    elif isinstance(base_type_expr, IndexExpr):
                        pass
                    else:
                        raise ValueError(
                            f"Unexpected base type expression: {type(base_type_expr)} {base_type_expr}"
                        )

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

            if isinstance(ctx.context.callee, MemberExpr):
                methodType = None
                if ctx.context.callee.name in API_READ:
                    methodType = "read"
                elif ctx.context.callee.name in API_WRITE:
                    methodType = "write"
                elif ctx.context.callee.name in API_OTHER:
                    methodType = "other"

                if methodType:
                    if not isinstance(
                        ctx.context.callee.expr, NameExpr
                    ) and not isinstance(ctx.context.callee.expr, MemberExpr):
                        raise ValueError(
                            f"Unexpected expression type: {ctx.context.callee.expr}"
                        )
                    output(
                        Location(
                            ctx.api.path,
                            ctx.context.line,
                            ctx.context.end_line or ctx.context.line,
                            ctx.context.column,
                            ctx.context.end_column or ctx.context.column,
                        ),
                        MethodContent(
                            name=ctx.context.callee.name,
                            methodType=methodType,
                            object=recover_expr_name(ctx.context.callee.expr),
                            objectType=str(ctx.type),
                            attributes=[],
                        ),
                    )
            else:
                raise ValueError(
                    f"Unexpected callee type: {type(ctx.context.callee)} {ctx.context.callee}"
                )

            return ctx.default_return_type

        return callback

    def get_function_hook(
        self, fullname: str
    ) -> Callable[[FunctionContext], Type] | None:

        def callback(ctx: FunctionContext) -> Type:
            if fullname == "django.db.transaction.atomic":
                name = "<unknown>"
                if isinstance(ctx.context, Decorator):
                    name = ctx.context.func.name
                elif isinstance(ctx.context, CallExpr):
                    name = "with"
                else:
                    raise ValueError(
                        f"Unexpected context type: {type(ctx.context)} {ctx.context}"
                    )

                output(
                    Location(
                        ctx.api.path,
                        ctx.context.line,
                        ctx.context.end_line or ctx.context.line,
                        ctx.context.column,
                        ctx.context.end_column or ctx.context.column,
                    ),
                    MethodContent(
                        name=name,
                        methodType="transaction",
                        object="django.db.transaction.atomic",
                        objectType="django.db.transaction.atomic",
                        attributes=[],
                    ),
                )

            return ctx.default_return_type

        return callback


def plugin(version: str):
    return DjangoAnalyzer
