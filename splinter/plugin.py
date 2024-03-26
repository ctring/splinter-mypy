import json
import sys
from typing import Callable, List, Union
from mypy.plugin import Plugin, ClassDefContext, MethodContext
from mypy.nodes import MemberExpr, NameExpr
from mypy.types import Type


class Location:
    path: str
    line: int
    column: int
    end_line: Union[int, None]
    end_column: Union[int, None]

    def __init__(
        self,
        path: str,
        line: int,
        column: int,
        end_line: Union[int, None],
        end_column: Union[int, None],
    ):
        self.path = path
        self.line = line
        self.column = column
        self.end_line = end_line
        self.end_column = end_column


class Message:
    type: str
    location: Location


class ModelMessage(Message):
    name: str

    def __init__(self, name: str, location: Location):
        self.type = "model"
        self.name = name
        self.location = location


class MethodMessage(Message):
    name: str
    method: str
    callee: List[str]

    def __init__(self, name: str, method: str, callee: List[str], location: Location):
        self.type = "method"
        self.name = name
        self.method = method
        self.callee = callee
        self.location = location


def debug(*msg):
    print(*msg, file=sys.stderr)


def output(msg: Message):
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
                        location = Location(
                            current_file.path,
                            ctx.cls.line,
                            ctx.cls.column,
                            ctx.cls.end_line,
                            ctx.cls.end_column,
                        )
                        output(ModelMessage(fullname, location))

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