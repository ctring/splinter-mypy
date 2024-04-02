import argparse
import mypy.api
import pathlib
import json

from splinter import OUTPUT

CONFIG_FILE = pathlib.Path(__file__).parent.resolve() / "mypy.ini"

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("path", help="Path to the project to analyze")
    parser.add_argument(
        "--output", default="messages.json", help="Path to the output file"
    )
    args = parser.parse_args()

    mypy.api.run([args.path, "--config-file", str(CONFIG_FILE), "--show-traceback"])

    with open(args.output, "w") as f:
        json.dump(OUTPUT, f, default=lambda o: vars(o), indent=2)
