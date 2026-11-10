"""Assert that the driver wheel contains only the extracted driver package."""

from pathlib import Path
from zipfile import ZipFile


wheel = next(Path("dist").glob("*.whl"))
with ZipFile(wheel) as archive:
    names = archive.namelist()

forbidden = ("/res/", "/sensors/", "/themes/", "/library/display.py", "/library/config.py")
unexpected = [name for name in names if any(part in name for part in forbidden)]
if unexpected:
    raise SystemExit(f"Unexpected application/resource files in wheel: {unexpected}")

if not any(name.endswith("/licenses/LICENSE") for name in names):
    raise SystemExit("The wheel is missing LICENSE")
if not any(name.endswith("/licenses/NOTICE.md") for name in names):
    raise SystemExit("The wheel is missing NOTICE.md")

print(f"Checked {len(names)} wheel files; no application or resource files found.")
