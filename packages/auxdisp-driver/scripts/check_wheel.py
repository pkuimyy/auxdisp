"""Check wheel contents, release metadata, and source-distribution doc links."""

import posixpath
import re
from email.parser import BytesParser
from pathlib import Path
from tarfile import open as open_tar
from urllib.parse import urlsplit
from zipfile import ZipFile


wheel = next(Path("dist").glob("*.whl"))
with ZipFile(wheel) as archive:
    names = archive.namelist()
    metadata_name = next(name for name in names if name.endswith(".dist-info/METADATA"))
    metadata = BytesParser().parsebytes(archive.read(metadata_name))

forbidden = ("/res/", "/sensors/", "/themes/", "/library/display.py", "/library/config.py")
unexpected = [name for name in names if any(part in name for part in forbidden)]
if unexpected:
    raise SystemExit(f"Unexpected application/resource files in wheel: {unexpected}")

if not any(name.endswith("/licenses/LICENSE") for name in names):
    raise SystemExit("The wheel is missing LICENSE")
if not any(name.endswith("/licenses/NOTICE.md") for name in names):
    raise SystemExit("The wheel is missing NOTICE.md")

print(f"Checked {len(names)} wheel files; no application or resource files found.")

project_urls = metadata.get_all("Project-URL", [])
for label in ("Repository", "Documentation", "Issues"):
    if not any(value.startswith(f"{label}, https://") for value in project_urls):
        raise SystemExit(f"Missing HTTPS project URL: {label}")

readme = metadata.get_payload(decode=True).decode("utf-8")
link_pattern = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
for target in link_pattern.findall(readme):
    if not target.startswith("#") and urlsplit(target).scheme != "https":
        raise SystemExit(f"README link cannot resolve on PyPI: {target}")

sdist = wheel.parent / f"{wheel.name.split('-')[0]}-{metadata['Version']}.tar.gz"
with open_tar(sdist) as archive:
    members = {member.name for member in archive.getmembers()}
    for member in archive.getmembers():
        if not member.isfile() or not member.name.endswith(".md"):
            continue
        with archive.extractfile(member) as file:
            document = file.read().decode("utf-8")
        for target in link_pattern.findall(document):
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            resolved = posixpath.normpath(posixpath.join(posixpath.dirname(member.name), parsed.path))
            if resolved not in members:
                raise SystemExit(f"Broken source-distribution link in {member.name}: {target}")

print("Checked project URLs, PyPI README links, and source-distribution documentation links.")
