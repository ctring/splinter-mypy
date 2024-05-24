import argparse
import json
import fnmatch

from splinter.analyzer import analyze

if __name__ == "__main__":
    parser = argparse.ArgumentParser("splinter")
    parser.add_argument("path", help="Path to the project to analyze")
    parser.add_argument(
        "--output", default="messages.json", help="Path to the output file"
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=["**/venv/**"],
        help="Glob pattern for matching paths to exclude from analysis",
    )
    args = parser.parse_args()

    result = analyze(args.path, args.exclude)

    output_json = {"messages": result.messages}
    with open(args.output, "w") as f:
        json.dump(output_json, f, default=lambda o: vars(o), indent=2)
