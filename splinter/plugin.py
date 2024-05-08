import json
import sys
from typing import Callable, Union, List
from mypy.plugin import (
    FunctionContext,
    Plugin,
    ClassDefContext,
    MethodContext,
)
from mypy.nodes import (
    AwaitExpr,
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
    SymbolNode,
    TempNode,
    TupleExpr,
    TypeInfo,
    UnaryExpr,
    IntExpr,
    SliceExpr,
    DictExpr,
    BytesExpr,
)
from mypy.types import (
    Type,
    Instance,
    CallableType,
    Overloaded,
    TypedDictType,
    ParamSpecType,
    TypeType,
    TypeVarType,
)

from splinter import (
    _MESSAGES,
    _LOCATIONS,
    _STATS,
    _DEBUG,
    Attribute,
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


def type_error(expr: Context | Expression | SymbolNode, name: str, location: Location):
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
    if isinstance(expr, IndexExpr):
        return f"{recover_expr_name(expr.base)}[{recover_expr_name(expr.index)}]"
    if isinstance(expr, SliceExpr):
        return f"_:_"
    if isinstance(expr, StrExpr):
        return f'"{expr.value}"'
    if isinstance(expr, IntExpr):
        return f"{expr.value}"
    if isinstance(expr, SuperExpr):
        return "super()"
    if isinstance(expr, OpExpr):
        return (
            f"{recover_expr_name(expr.left)} {expr.op} {recover_expr_name(expr.right)}"
        )

    raise ValueError(f"Unexpected expression type: {expr}")


def collect_base_types(type_info: TypeInfo) -> List[str]:
    if type_info.fullname.startswith("builtins") or type_info.fullname.startswith(
        "typing"
    ):
        return []
    types = [type_info.fullname]
    for base in type_info.bases:
        if isinstance(base, Instance):
            types.extend(collect_base_types(base.type))
    return types


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
                        if isinstance(base_type_expr.node, TypeInfo):
                            base_types = collect_base_types(base_type_expr.node)
                        else:
                            continue

                        if "django.db.models.base.Model" in base_types:
                            output(
                                location,
                                ModelContent(name=ctx.cls.fullname),
                            )

                        if "django_filters.filterset.FilterSet" in base_types:
                            output(
                                location,
                                MethodContent(
                                    name=ctx.cls.fullname,
                                    methodType="read",
                                    object="FilterSet",
                                    objectTypes=["FilterSet"],
                                    attributes=[],
                                ),
                            )
                    elif isinstance(base_type_expr, IndexExpr):
                        pass
                    elif isinstance(base_type_expr, CallExpr):
                        # e.g.
                        #   class Url(
                        #     typing.NamedTuple(
                        #         "Url",
                        #         [
                        #             ("scheme", typing.Optional[str]),
                        #             ("auth", typing.Optional[str]),
                        #             ("host", typing.Optional[str]),
                        #             ("port", typing.Optional[int]),
                        #             ("path", typing.Optional[str]),
                        #             ("query", typing.Optional[str]),
                        #             ("fragment", typing.Optional[str]),
                        #         ],
                        #     )
                        # ):
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
            "exclude",
            "distinct",
            "values",
            "values_list",
            "latest",
            "earliest",
            "first",
            "last",
            "dates",
            "datetimes",
            "exists",
            "extra",
        ]
        API_WRITE = [
            "save",
            "delete",
            "create",
            "update",
            "update_or_create",
            "get_or_create",
            "bulk_create",
            "bulk_update",
        ]
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

                    # Ignore all obvious irrelevant types
                    if (
                        object_type.startswith("builtins")
                        or object_type.startswith("collections")
                        or object_type.startswith("os")
                        or object_type.startswith("hashlib")
                    ):
                        return ctx.default_return_type

                    method_name = ctx.context.callee.name
                    method_type = None
                    if method_name in API_READ:
                        method_type = "read"
                    elif method_name in API_WRITE:
                        method_type = "write"
                    elif method_name in API_OTHER:
                        method_type = "other"

                    if method_type:
                        try:
                            object_name = recover_expr_name(ctx.context.callee.expr)
                        except ValueError as e:
                            raise ValueError(f"{e} at {location}")

                        object_types = [str(ctx.type)]
                        if isinstance(ctx.type, Instance):
                            object_types.extend(collect_base_types(ctx.type.type))
                        elif isinstance(ctx.type, CallableType):
                            pass
                        elif isinstance(ctx.type, Overloaded):
                            # i.e dict.update(self, iterable)
                            #     |--|
                            pass
                        elif isinstance(ctx.type, TypedDictType):
                            # i.e
                            # class LegacyEditHistoryEvent(TypedDict, total=False):
                            #   user_id: int
                            #   timestamp: int
                            #
                            # event: LegacyEditHistoryEvent = ...
                            # event.get("user_id")
                            # |---|
                            pass
                        elif isinstance(ctx.type, ParamSpecType):
                            pass
                        elif isinstance(ctx.type, TypeType):
                            pass
                        elif isinstance(ctx.type, TypeVarType):
                            pass
                        else:
                            type_error(ctx.type, "object type", location)

                        # Deduplicate while preserving order
                        object_types = list(dict.fromkeys(object_types).keys())

                        attributes = []
                        if method_name in ["get", "filter"]:
                            for arg_name, arg in zip(
                                ctx.context.arg_names, ctx.context.args
                            ):
                                if arg_name:
                                    attributes.append(Attribute(
                                        name=arg_name,
                                        startLine=arg.line,
                                        endLine=arg.end_line or arg.line,
                                        startColumn=arg.column - len(arg_name) - 1,
                                        endColumn=arg.end_column or arg.column,
                                    ))

                        output(
                            location,
                            MethodContent(
                                name=method_name,
                                methodType=method_type,
                                object=object_name,
                                objectTypes=object_types,
                                attributes=attributes,
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
                elif isinstance(ctx.context.callee, IndexExpr):
                    # e.g. self.manager_type_mapper[execution.manager_type](execution)
                    #      |----------------------------------------------|
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
            elif isinstance(ctx.context, IntExpr):
                # e.g. 0
                pass
            elif isinstance(ctx.context, SuperExpr):
                # e.g super().content
                pass
            elif isinstance(ctx.context, AwaitExpr):
                # e.g await asyncio.sleep(1)
                pass
            elif isinstance(ctx.context, DictExpr):
                # e.g {"import_file_name": "input_format"}
                pass
            elif isinstance(ctx.context, SliceExpr):
                # e.g. _[:]
                pass
            elif isinstance(ctx.context, BytesExpr):
                # e.g. b"Hello"
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
                        objectTypes=["django.db.transaction.atomic"],
                        attributes=[],
                    ),
                )

            return ctx.default_return_type

        return callback


def plugin(version: str):
    return DjangoAnalyzer
