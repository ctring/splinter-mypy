import mypy.api
import pathlib

from typing import Tuple, List

_CONFIG_FILE = pathlib.Path(__file__).parent.resolve() / "mypy.ini"
_MESSAGES = []
_MODELS = set()
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
    _MODELS.clear()
    return messages
