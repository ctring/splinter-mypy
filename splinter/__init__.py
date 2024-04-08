import mypy.api
import pathlib

from typing import Tuple, List, Set
from collections import defaultdict, namedtuple

Location = namedtuple(
    "Location", ["path", "from_line", "to_line", "from_column", "to_column"]
)


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
        location: Location,
        content: Content,
    ):
        self.filePath = location.path
        self.fromLine = location.from_line
        self.toLine = location.to_line
        self.fromColumn = location.from_column
        self.toColumn = location.to_column
        self.content = content


_CONFIG_FILE = pathlib.Path(__file__).parent.resolve() / "mypy.ini"
_MESSAGES: List[Message] = []
_LOCATIONS: Set[Location] = set()
_STATS = defaultdict(int)
_DEBUG = False


def run_mypy(
    path: str, excludes: List[str], debug: bool
) -> Tuple[list, Tuple[str, str, int]]:
    assert _CONFIG_FILE.exists(), f"Config file mypy.ini does not exist"

    args = [path] + _build_args(excludes, debug)

    output = mypy.api.run(args)

    messages = _get_and_clear_results()

    return messages, output


def run_mypy_text(
    text, excludes: List[str] = [], debug: bool = False
) -> Tuple[list, Tuple[str, str, int]]:
    assert _CONFIG_FILE.exists(), f"Config file mypy.ini does not exist"

    args = ["-c", text] + _build_args(excludes, debug)

    output = mypy.api.run(args)

    messages = _get_and_clear_results()

    return messages, output


def _build_args(excludes: List[str], debug: bool) -> List[str]:
    args = ["--config-file", str(_CONFIG_FILE)]

    for exclude in excludes:
        args.append("--exclude")
        args.append(exclude)

    global _DEBUG
    _DEBUG = debug
    if debug:
        args.append("--show-traceback")

    return args


def _get_and_clear_results():
    global _MESSAGES
    messages = _MESSAGES
    _MESSAGES = []
    _LOCATIONS.clear()
    _STATS.clear()
    return messages
