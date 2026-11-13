"""Check auxdisp-codex-quota package contents and published documentation links."""

from email.parser import BytesParser
from pathlib import Path
import posixpath
import re
from tarfile import open as open_tar
import tomllib
from urllib.parse import unquote, urlsplit
from zipfile import ZipFile


def check(directory=Path("dist")):
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]
    wheels, sources = list(directory.glob("*.whl")), list(directory.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sources) != 1:
        raise ValueError("Expected exactly one auxdisp-codex-quota wheel and source archive")
    with ZipFile(wheels[0]) as archive:
        names = archive.namelist()
        metadata = BytesParser().parsebytes(archive.read(next(n for n in names if n.endswith(".dist-info/METADATA"))))
        if metadata["Name"] != project["name"] or metadata["Version"] != project["version"]:
            raise ValueError("Distribution metadata must match pyproject.toml")
        required = {f"auxdisp_codex_quota/{module}.py" for module in (
            "__init__", "__main__", "cli", "_background", "host", "paths", "scheduler", "service", "win32",
            "collector", "config", "display", "model", "preview", "render", "runtime",
            "task_adapter", "task_spec", "direct_com", "_scheduler_com_worker",
        )} | {"auxdisp_codex_quota/data/demo.json"}
        if not required.issubset(names) or not any(n.endswith("/licenses/LICENSE") for n in names):
            raise ValueError("Wheel is missing required application modules, synthetic data, or license")
        if any(n.startswith(("auxdisp_driver/", "scripts/")) or "/state/" in n or "/logs/" in n for n in names):
            raise ValueError("Wheel contains local driver sources or runtime data")
        if not any(r.startswith("auxdisp-driver") and "@" not in r for r in metadata.get_all("Requires-Dist", [])):
            raise ValueError("auxdisp-driver must remain an ordinary index dependency")
        if not any(r.startswith("pywin32") and 'sys_platform == "win32"' in r
                   for r in metadata.get_all("Requires-Dist", [])):
            raise ValueError("Candidate COM dependency must be restricted to Windows")
        for label in ("Repository", "Documentation", "Issues"):
            if not any(u.startswith(f"{label}, https://") for u in metadata.get_all("Project-URL", [])):
                raise ValueError(f"Missing HTTPS project URL: {label}")
        links = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
        for target in links.findall(metadata.get_payload(decode=True).decode("utf-8")):
            if not target.startswith("#") and urlsplit(target).scheme != "https":
                raise ValueError(f"PyPI README requires absolute HTTPS links: {target}")
    with open_tar(sources[0]) as archive:
        members = {m.name for m in archive.getmembers()}
        for member in archive.getmembers():
            if not member.isfile() or not member.name.endswith(".md"):
                continue
            with archive.extractfile(member) as file:
                document = file.read().decode("utf-8")
            for target in links.findall(document):
                parsed = urlsplit(target)
                if not parsed.scheme and not parsed.netloc and parsed.path:
                    path = posixpath.normpath(posixpath.join(posixpath.dirname(member.name), unquote(parsed.path)))
                    if path not in members:
                        raise ValueError(f"Broken source-distribution link in {member.name}: {target}")
    print("Checked auxdisp-codex-quota modules, license, dependency metadata, and distribution documentation links.")


if __name__ == "__main__":
    check()
