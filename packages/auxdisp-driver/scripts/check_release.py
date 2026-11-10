"""Validate an explicit driver release tag before publishing any artifacts."""

import argparse
import os
import re
from pathlib import Path


TAG = re.compile(
    r"auxdisp-driver-v"
    r"((?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*))"
    r"((?:a|b|rc)(?:0|[1-9][0-9]*))?"
)


def validate_tag(tag, project):
    """Accept matching final, alpha, beta, and release-candidate driver tags."""
    if project.get("name") != "auxdisp-driver":
        raise ValueError("Release workflow may only publish auxdisp-driver")
    match = TAG.fullmatch(tag)
    if not match:
        raise ValueError("Expected auxdisp-driver-vX.Y.Z, optionally followed by aN, bN, or rcN")
    version = match.group(1) + (match.group(2) or "")
    if project.get("version") != version:
        raise ValueError(f"Tag version {version!r} does not match pyproject.toml version {project.get('version')!r}")
    return {"version": version, "prerelease": "true" if match.group(2) else "false"}


def main():
    # The release builder runs Python 3.13. Import lazily so tests on supported
    # runtime versions below 3.11 can still exercise the tag validation logic.
    import tomllib

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
