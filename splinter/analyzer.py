import glob
import os

import mypy.build
import mypy.nodes
import mypy.main
import mypy.types

from .visitor import MypyVisitor

from collections import defaultdict
from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class ModelContent:
    name: str
    type: str = "model"


@dataclass(frozen=True)
class Attribute:
    name: str
    startLine: int
    endLine: int
    startColumn: int
    endColumn: int


@dataclass(frozen=True)
class MethodContent:
    name: str
    methodType: str
    object: str
    objectTypes: List[str]
    attributes: List[Attribute]
    type: str = "method"


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


@dataclass(frozen=True)
class Location:
    path: str
    from_line: int
    to_line: int
    from_column: int
    to_column: int


class Message:
    filePath: str
    fromLine: int
    toLine: int
    fromColumn: int
    toColumn: int
    content: ModelContent | MethodContent

    def __init__(
        self,
        location: Location,
        content: ModelContent | MethodContent,
    ):
        self.filePath = location.path
        self.fromLine = location.from_line
        self.toLine = location.to_line
        self.fromColumn = location.from_column
        self.toColumn = location.to_column
        self.content = content


class Messages:
    messages: list[Message]
    locations: set[Location]
    counts: dict[type, int]

    def __init__(self):
        self.messages = []
        self.locations = set()
        self.counts = defaultdict(int)

    def add(self, loc: Location, content: ModelContent | MethodContent):
        if loc in self.locations:
            return

        self.locations.add(loc)

        msg = Message(loc, content)

        self.messages.append(msg)
        self.counts[type(content)] += 1

        print(
            f"Found {self.counts[ModelContent]} models and {self.counts[MethodContent]} methods"
        )


def analyze(path: str, excludes: List[str]) -> Messages:
    print("Scanning files")
    files, opt = mypy.main.process_options([path])

    # Remove excluded files
    excluded_files: set[str] = set()
    for eg in excludes:
        found = glob.glob(eg, recursive=True, root_dir=path)
        excluded_files.update([os.path.join(path, f) for f in found])
    files = [f for f in files if f.path not in excluded_files]

    # Set options
    opt.preserve_asts = True
    opt.export_types = True
    opt.check_untyped_defs = True
    opt.follow_imports = "silent"
    opt.incremental = False

    print("Parsing files")
    result = mypy.build.build(files, opt)

    print("Traversing ASTs")
    messages = Messages()
    models: dict[str, SplinterVisitor.ModelInfo] = {}
    for _, state in result.graph.items():
        tree = state.tree
        if tree is not None:
            visitor = SplinterVisitor(tree.path, result.types, models, messages)
            visitor.accept(tree)

    def visit_model(
        info: SplinterVisitor.ModelInfo, target_model: str, visited: set[str]
    ) -> ModelContent | MethodContent | None:
        if info.name in visited:
            return None

        visited.add(info.name)

        for parent in info.parents:
            if parent in [
                "django.db.models.Model",
                "django.db.models.base.Model",
                "mptt.models.MPTTModel",
                "polymorphic.models.PolymorphicModel",
                "seal.models.SealableModel",
                "django_extensions.db.models.TimeStampedModel"
            ]:
                return ModelContent(name=target_model)

            if parent in ["django_filters.filterset.FilterSet"]:
                return MethodContent(
                    name=target_model,
                    methodType="read",
                    object="FilterSet",
                    objectTypes=["FilterSet"],
                    attributes=[],
                )

            if parent in models:
                res = visit_model(models[parent], target_model, visited)
                if res is not None:
                    return res

        return None

    for model, info in models.items():
        res = visit_model(info, model, set())
        if res is not None:
            messages.add(info.location, res)

    return messages


class SplinterVisitor(MypyVisitor):

    @dataclass()
    class ModelInfo:
        name: str
        parents: set[str]
        location: Location

    path: str
    models: dict[str, ModelInfo]
    imports: dict[str, str]

    def __init__(
        self,
        path: str,
        types: dict[mypy.nodes.Expression, mypy.types.Type],
        models: dict[str, ModelInfo],
        messages: Messages,
    ):
        self.path = path
        self.types = types
        self.models = models
        self.imports = {}
        self.messages = messages

    def visit_import(self, o: mypy.nodes.Import):
        super().visit_import(o)
        for mod, alias in o.ids:
            if alias is not None:
                self.imports[alias] = mod
            else:
                suffix = mod.split(".")[-1]
                self.imports[suffix] = mod

    def visit_import_from(self, o: mypy.nodes.ImportFrom):
        super().visit_import_from(o)
        for name, alias in o.names:
            if alias is not None:
                self.imports[alias] = f"{o.id}.{name}"
            else:
                self.imports[name] = f"{o.id}.{name}"

    def visit_class_def(self, o: mypy.nodes.ClassDef):
        super().visit_class_def(o)
        location = Location(
            self.path,
            o.line,
            o.end_line or o.line,
            o.column,
            o.end_column or o.column,
        )
        parents = set()
        for base_type_expr in o.base_type_exprs:
            if isinstance(base_type_expr, mypy.nodes.NameExpr) or isinstance(
                base_type_expr, mypy.nodes.MemberExpr
            ):
                expr = recover_expr_str(base_type_expr)
                prefix = expr.split(".")[0]
                if prefix in self.imports:
                    parents.add(expr.replace(prefix, self.imports[prefix]))
                else:
                    parents.add(base_type_expr.fullname)

                if isinstance(base_type_expr.node, mypy.nodes.TypeInfo):
                    parents.update(collect_base_types(base_type_expr.node))

        self.models[o.fullname] = self.ModelInfo(
            name=o.fullname,
            parents=parents,
            location=location,
        )

    def visit_decorator(self, o: mypy.nodes.Decorator):
        super().visit_decorator(o)
        for dec in o.original_decorators:
            if (
                isinstance(dec, mypy.nodes.MemberExpr)
                or isinstance(dec, mypy.nodes.NameExpr)
            ) and dec.fullname == "django.db.transaction.atomic":
                self.messages.add(
                    Location(
                        self.path,
                        o.line,
                        o.end_line or o.line,
                        o.column,
                        o.end_column or o.column,
                    ),
                    MethodContent(
                        name=o.func.fullname,
                        methodType="transaction",
                        object="django.db.transaction.atomic",
                        objectTypes=["django.db.transaction.atomic"],
                        attributes=[],
                    ),
                )

    def visit_call_expr(self, o: mypy.nodes.CallExpr):
        super().visit_call_expr(o)
        location = Location(
            self.path,
            o.line,
            o.end_line or o.line,
            o.column,
            o.end_column or o.column,
        )

        if isinstance(o.callee, mypy.nodes.MemberExpr):
            method_name = o.callee.name
            expr = o.callee.expr
            obj_type = self.types.get(expr)

            # Ignore all obvious irrelevant types
            if (
                str(obj_type).startswith("builtins")
                or str(obj_type).startswith("collections")
                or str(obj_type).startswith("os")
                or str(obj_type).startswith("hashlib")
            ):
                return

            method_type = None
            if method_name in API_READ:
                method_type = "read"
            elif method_name in API_WRITE:
                method_type = "write"
            elif method_name in API_OTHER:
                method_type = "other"

            if method_type:
                try:
                    object_name = recover_expr_str(expr)
                except ValueError as e:
                    raise ValueError(f"{e} at {location}")

                obj_types = [str(obj_type)]
                if isinstance(obj_type, mypy.types.Instance):
                    obj_types.extend(collect_base_types(obj_type.type))

                # Deduplicate while preserving order
                obj_types = list(dict.fromkeys(obj_types).keys())

                attributes = []
                if method_name in ["get", "filter", "exclude"]:
                    for arg_name, arg in zip(o.arg_names, o.args):
                        if arg_name:
                            attributes.append(
                                Attribute(
                                    name=arg_name,
                                    startLine=arg.line,
                                    endLine=arg.end_line or arg.line,
                                    startColumn=arg.column - len(arg_name) - 1,
                                    endColumn=arg.end_column or arg.column,
                                )
                            )
                self.messages.add(
                    location,
                    MethodContent(
                        name=method_name,
                        methodType=method_type,
                        object=object_name,
                        objectTypes=obj_types,
                        attributes=attributes,
                    ),
                )

        if isinstance(o.callee, mypy.nodes.MemberExpr) or isinstance(
            o.callee, mypy.nodes.NameExpr
        ):
            if o.callee.fullname == "django.db.transaction.atomic":
                self.messages.add(
                    location,
                    MethodContent(
                        name="with",
                        methodType="transaction",
                        object="django.db.transaction.atomic",
                        objectTypes=["django.db.transaction.atomic"],
                        attributes=[],
                    ),
                )


def collect_base_types(type_info: mypy.nodes.TypeInfo) -> List[str]:
    if type_info.fullname.startswith("builtins") or type_info.fullname.startswith(
        "typing"
    ):
        return []
    types = [type_info.fullname]
    for base in type_info.bases:
        if isinstance(base, mypy.types.Instance):
            types.extend(collect_base_types(base.type))
    return types


def recover_expr_str(cur_expr: mypy.nodes.Expression):
    match cur_expr:
        case mypy.nodes.NameExpr(name=name):
            return cur_expr.name
        case mypy.nodes.CallExpr(callee=callee):
            return f"{recover_expr_str(callee)}()"
        case mypy.nodes.MemberExpr(expr=expr, name=name):
            return f"{recover_expr_str(expr)}.{name}"
        case mypy.nodes.IndexExpr(base=base, index=index):
            return f"{recover_expr_str(base)}[{recover_expr_str(index)}]"
        case mypy.nodes.SliceExpr():
            return f"_:_"
        case mypy.nodes.StrExpr(value=value):
            return f'"{value}"'
        case mypy.nodes.IntExpr(value=value):
            return f"{value}"
        case mypy.nodes.SuperExpr():
            return "super()"
        case mypy.nodes.OpExpr(left=left, op=op, right=right):
            return f"{recover_expr_str(left)} {op} {recover_expr_str(right)}"
        case mypy.nodes.UnaryExpr(op=op, expr=expr):
            return f"{op}{recover_expr_str(expr)}"
        case mypy.nodes.DictExpr():
            return f"{{}}"
        case mypy.nodes.ListExpr():
            return f"[]"
        case mypy.nodes.TupleExpr():
            return f"()"
        case mypy.nodes.ConditionalExpr(cond=cond, if_expr=if_expr, else_expr=else_expr):
            return f"{recover_expr_str(if_expr)} if {recover_expr_str(cond)} else {recover_expr_str(else_expr)}"
        case _:
            raise ValueError(f"Unexpected expression type: {cur_expr}")
