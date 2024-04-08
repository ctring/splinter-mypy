import argparse
import json

from splinter import run_mypy


if __name__ == "__main__":
    parser = argparse.ArgumentParser("splinter")
    parser.add_argument("path", help="Path to the project to analyze")
    parser.add_argument(
        "--output", default="messages.json", help="Path to the output file"
    )
    parser.add_argument("--debug", action="store_true", help="Print debug messages")
    parser.add_argument(
        "--exclude",
        nargs="*",
        help="Regular expression for matching paths to exclude from analysis",
    )
    args = parser.parse_args()

    output_json = {
        "messages": run_mypy(args.path, args.exclude, args.debug)[0],
    }
    with open(args.output, "w") as f:
        json.dump(output_json, f, default=lambda o: vars(o), indent=2)
