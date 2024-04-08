import mypy.api
import pathlib

from typing import Tuple

_CONFIG_FILE = pathlib.Path(__file__).parent.resolve() / "mypy.ini"
_MESSAGES = []
_MODELS = set()
_DEBUG = False


def run_mypy(path: str, debug: bool) -> Tuple[list, Tuple[str, str, int]]:
    assert _CONFIG_FILE.exists(), f"Config file mypy.ini does not exist"

    args = [path, "--config-file", str(_CONFIG_FILE)]

    global _DEBUG
    _DEBUG = debug
    if debug:
        args.append("--show-traceback")

    output = mypy.api.run(args)

    messages = _get_and_clear_results()

    return messages, output


def run_mypy_text(text, debug: bool) -> Tuple[list, Tuple[str, str, int]]:
    assert _CONFIG_FILE.exists(), f"Config file mypy.ini does not exist"

    args = ["-c", text, "--config-file", str(_CONFIG_FILE)]

    global _DEBUG
    _DEBUG = debug
    if debug:
        args.append("--show-traceback")

    output = mypy.api.run(args)

    messages = _get_and_clear_results()

    return messages, output


def _get_and_clear_results():
    global _MESSAGES
    messages = _MESSAGES
    _MESSAGES = []
    _MODELS.clear()
    return messages
