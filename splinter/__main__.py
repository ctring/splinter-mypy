import argparse
import json
import fnmatch

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
    parser.add_argument(
        "--exclude-glob",
        nargs="*",
        help="Glob pattern for matching paths to exclude from analysis",
    )
    args = parser.parse_args()

    excludes = []
    if args.exclude:
        excludes.extend(args.exclude)
    if args.exclude_glob:
        excludes.extend([fnmatch.translate(pat) for pat in args.exclude_glob])

    output_json = {
        "messages": run_mypy(args.path, excludes, args.debug)[0],
    }
    with open(args.output, "w") as f:
        json.dump(output_json, f, default=lambda o: vars(o), indent=2)
