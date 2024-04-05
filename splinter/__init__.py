import mypy.api
import pathlib

from typing import Tuple

CONFIG_FILE = pathlib.Path(__file__).parent.resolve() / "mypy.ini"
_MESSAGES = []


def run_mypy(path: str) -> Tuple[list, Tuple[str, str, int]]:
    assert CONFIG_FILE.exists(), f"Config file mypy.ini does not exist"

    output = mypy.api.run([path, "--config-file", str(CONFIG_FILE)])

    global _MESSAGES
    messages = _MESSAGES
    _MESSAGES = []

    return messages, output


def run_mypy_text(text) -> Tuple[list, Tuple[str, str, int]]:
    assert CONFIG_FILE.exists(), f"Config file mypy.ini does not exist"

    output = mypy.api.run(["-c", text, "--config-file", str(CONFIG_FILE)])

    global _MESSAGES
    messages = _MESSAGES
    _MESSAGES = []

    return messages, output
