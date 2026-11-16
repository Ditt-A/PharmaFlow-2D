"""Inspect Apple Numbers containers before attempting dataset parsing."""
from pathlib import Path
import zipfile

directory = Path("data/raw/zenodo_20554446")
for path in sorted(directory.glob("*.numbers")):
    print(path, path.stat().st_size, "bytes")
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            print("ZIP entries:", len(archive.namelist()))
            print("First entries:", archive.namelist()[:10])
    else:
        print("Not a ZIP container; inspect raw format manually")
if not list(directory.glob("*.numbers")):
    print("No files: run scripts/download_reference.py --subset sim")
