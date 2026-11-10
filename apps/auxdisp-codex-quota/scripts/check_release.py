"""Validate an explicit auxdisp-codex-quota release tag before publishing."""

import argparse
import os
from pathlib import Path
import re
import tomllib


PROJECT = "auxdisp-codex-quota"
TAG = re.compile(r"auxdisp-codex-quota-v"
                 r"((?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*))"
                 r"((?:a|b|rc)(?:0|[1-9][0-9]*))?")


def validate_tag(tag, project):
    if project.get("name") != PROJECT:
        raise ValueError(f"Release workflow may only publish {PROJECT}")
    match = TAG.fullmatch(tag)
    if not match:
        raise ValueError(f"Expected {PROJECT}-vX.Y.Z, optionally followed by aN, bN, or rcN")
    version = match.group(1) + (match.group(2) or "")
    if version != project.get("version"):
        raise ValueError("Release tag must match the pyproject.toml version exactly")
    return {"version": version, "prerelease": "true" if match.group(2) else "false"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tag")
    args = parser.parse_args()
    project_file = Path(__file__).resolve().parents[1] / "pyproject.toml"
    project = tomllib.loads(project_file.read_text(encoding="utf-8"))["project"]
    try:
        values = validate_tag(args.tag, project)
    except ValueError as exc:
        parser.error(str(exc))
    output = "".join(f"{key}={value}\n" for key, value in values.items())
    if os.environ.get("GITHUB_OUTPUT"):
        with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as file:
            file.write(output)
    print(output, end="")


if __name__ == "__main__":
    main()
