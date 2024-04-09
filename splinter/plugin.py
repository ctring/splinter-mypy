import json
import sys
from typing import Callable, Union
from mypy.plugin import (
    FunctionContext,
    Plugin,
    ClassDefContext,
    MethodContext,
)
from mypy.nodes import (
    CallExpr,
    ComparisonExpr,
    Context,
    ConditionalExpr,
    ClassDef,
    Decorator,
    Expression,
    GeneratorExpr,
    IndexExpr,
    ListComprehension,
    ListExpr,
    MemberExpr,
    NameExpr,
    OpExpr,
    OperatorAssignmentStmt,
    SetExpr,
    StrExpr,
    SuperExpr,
    TempNode,
    TupleExpr,
    UnaryExpr,
)
from mypy.types import Type, Instance

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


def type_error(expr: Context | Expression, name: str, location: Location):
    raise ValueError(f"Unexpected {name} type: {type(expr)} {expr} at {location}")


def output(location: Location, content: ModelContent | MethodContent):
    if location in _LOCATIONS:
        return
    _LOCATIONS.add(location)

    msg = Message(location, content)

    debug(msg)

    _MESSAGES.append(msg)
    _STATS[type(content)] += 1

    print(f"Found {_STATS[ModelContent]} models and {_STATS[MethodContent]} methods")


def recover_expr_name(expr: Expression):
    if isinstance(expr, NameExpr):
        return expr.name
    if isinstance(expr, CallExpr):
        return f"{recover_expr_name(expr.callee)}()"
    if isinstance(expr, MemberExpr):
        return f"{recover_expr_name(expr.expr)}.{expr.name}"

    raise ValueError(f"Unexpected expression type: {expr}")


class DjangoAnalyzer(Plugin):
    def get_customize_class_mro_hook(
        self, fullname: str
    ) -> Union[Callable[[ClassDefContext], None], None]:
        """Collects the model definitions."""

        def callback(ctx: ClassDefContext):
            current_file = ctx.api.modules[ctx.api.cur_mod_id]
            location = Location(
                current_file.path,
                ctx.cls.line,
                ctx.cls.end_line or ctx.cls.line,
                ctx.cls.column,
                ctx.cls.end_column or ctx.cls.column,
            )
            if ctx.cls.base_type_exprs:
                for base_type_expr in ctx.cls.base_type_exprs:
                    if isinstance(base_type_expr, NameExpr) or isinstance(
                        base_type_expr, MemberExpr
                    ):
                        if base_type_expr.fullname == "django.db.models.base.Model":
                            output(
                                location,
                                ModelContent(name=ctx.cls.fullname),
                            )
                    elif isinstance(base_type_expr, IndexExpr):
                        pass
                    else:
                        type_error(base_type_expr, "base type", location)

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
        API_OTHER = ["raw", "execute"]

        def callback(ctx: MethodContext) -> Type:
            location = Location(
                ctx.api.path,
                ctx.context.line,
                ctx.context.end_line or ctx.context.line,
                ctx.context.column,
                ctx.context.end_column or ctx.context.column,
            )
            # Only consider method calls
            if isinstance(ctx.context, CallExpr):
                if isinstance(ctx.context.callee, MemberExpr):
                    object_type = str(ctx.type)
                    if object_type.startswith("builtins"):
                        return ctx.default_return_type

                    method_type = None
                    if ctx.context.callee.name in API_READ:
                        method_type = "read"
                    elif ctx.context.callee.name in API_WRITE:
                        method_type = "write"
                    elif ctx.context.callee.name in API_OTHER:
                        method_type = "other"

                    if method_type:
                        try:
                            object_name = recover_expr_name(ctx.context.callee.expr)
                        except ValueError as e:
                            raise ValueError(f"{e} at {location}")

                        output(
                            location,
                            MethodContent(
                                name=ctx.context.callee.name,
                                methodType=method_type,
                                object=object_name,
                                objectType=str(ctx.type),
                                attributes=[],
                            ),
                        )
                elif isinstance(ctx.context.callee, NameExpr):
                    # e.g. with open("file.txt") as f:
                    #           |--|
                    pass
                elif isinstance(ctx.context.callee, CallExpr):
                    # e.g. functools.wraps(view_func)(wrapped_view)
                    #      |------------------------|
                    pass
                elif isinstance(ctx.context.callee, SuperExpr):
                    # e.g. super().__init__(*args, **kwargs)
                    #      |--------------|
                    pass
                else:
                    type_error(ctx.context.callee, "callee", location)
            elif isinstance(ctx.context, IndexExpr):
                # e.g. Literal["r", "w"]
                pass
            elif isinstance(ctx.context, ComparisonExpr):
                # e.g. sys.version_info >= (3, 10)
                pass
            elif isinstance(ctx.context, UnaryExpr):
                # e.g. -1
                pass
            elif isinstance(ctx.context, OperatorAssignmentStmt):
                # e.g.
                # __all__ += ["Annotated", "BinaryIO", "IO", "Match", "Pattern", "TextIO"]
                pass
            elif isinstance(ctx.context, Decorator):
                # e.g.
                # @deprecated("load_module() is deprecated; use exec_module() instead")
                # def load_module()
                pass
            elif isinstance(ctx.context, OpExpr):
                # e.g. CONFIG_FILE + PYPROJECT_CONFIG_FILES
                pass
            elif isinstance(ctx.context, NameExpr):
                pass
            elif isinstance(ctx.context, ClassDef):
                pass
            elif isinstance(ctx.context, MemberExpr):
                # e.g. new_options.disable_error_code
                pass
            elif isinstance(ctx.context, TupleExpr):
                pass
            elif isinstance(ctx.context, ListExpr):
                pass
            elif isinstance(ctx.context, GeneratorExpr):
                # e.g. (attr for attr in copy_attrs if attr in self.__dict__)
                pass
            elif isinstance(ctx.context, ListComprehension):
                # e.g. [connection for connection in connections.all() if connection.vendor == "sqlite"]
                pass
            elif isinstance(ctx.context, TempNode):
                pass
            elif isinstance(ctx.context, Instance):
                pass
            elif isinstance(ctx.context, StrExpr):
                # e.g. "r"
                pass
            elif isinstance(ctx.context, SetExpr):
                # e.g. {"import_file_name", "input_format"}
                pass
            elif isinstance(ctx.context, ConditionalExpr):
                # e.g. "r" if sys.version_info < (3, 10) else "rb"
                pass
            else:
                type_error(ctx.context, "context", location)

            return ctx.default_return_type

        return callback

    def get_function_hook(
        self, fullname: str
    ) -> Callable[[FunctionContext], Type] | None:

        def callback(ctx: FunctionContext) -> Type:
            location = Location(
                ctx.api.path,
                ctx.context.line,
                ctx.context.end_line or ctx.context.line,
                ctx.context.column,
                ctx.context.end_column or ctx.context.column,
            )
            if fullname == "django.db.transaction.atomic":
                name = "<unknown>"
                if isinstance(ctx.context, Decorator):
                    name = ctx.context.func.name
                elif isinstance(ctx.context, CallExpr):
                    name = "with"
                else:
                    type_error(ctx.context, "context", location)

                output(
                    location,
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
