"""Read actual Numbers tables and report schema without inventing variable units."""
import argparse
import json
from pathlib import Path
import zipfile
from pharmaflow.dataio import md5_file
from download_reference import EXPECTED, RECORD_ID


def inspect(path):
    checksum = md5_file(path)
    if checksum != EXPECTED[path.name]:
        raise ValueError("MD5 mismatch: " + str(path))
    if not zipfile.is_zipfile(path):
        raise ValueError("Not a Numbers ZIP: " + str(path))
    with zipfile.ZipFile(path) as archive:
        corrupt = archive.testzip()
        if corrupt:
            raise ValueError("Corrupt Numbers archive entry: " + corrupt)
        entries = len(archive.namelist())
    from numbers_parser import Document
    document = Document(str(path))
    tables = []
    for sheet in document.sheets:
        for table in sheet.tables:
            rows = table.rows(values_only=True)
            previews = []
            nonempty = 0
            types = {}
            for row_index, row in enumerate(rows):
                cells = []
                for column, value in enumerate(row):
                    if value is not None and value != "":
                        nonempty += 1
                        kind = type(value).__name__
                        types[kind] = types.get(kind, 0) + 1
                        if len(cells) < 18:
                            cells.append({"column_zero_based": column, "value": str(value)[:140]})
                if cells and len(previews) < 7:
                    previews.append({"row_zero_based": row_index, "cells": cells})
            tables.append({"sheet": sheet.name, "table": table.name, "rows": table.num_rows,
                           "columns": table.num_cols, "nonempty_cells": nonempty,
                           "cell_types": types, "first_nonempty_rows": previews})
    return {"file": str(path), "bytes": path.stat().st_size, "md5": checksum, "checksum_verified": True,
            "zip_entries": entries, "tables": tables,
            "interpretation": "Schema previews only. Units, axes and semantics need explicit verification. Not assigned as particle trajectories."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path("data/raw/zenodo_" + RECORD_ID))
    parser.add_argument("--report", type=Path, default=Path("outputs/metrics/reference_schema.json"))
    args = parser.parse_args()
    paths = sorted(args.directory.glob("*.numbers"))
    if not paths:
        raise SystemExit("No files: run scripts/download_reference.py --subset sim")
    try:
        reports = [inspect(path) for path in paths]
    except ImportError as error:
        raise SystemExit('Install parser: python -m pip install -e ".[reference]"; ' + str(error)) from error
    args.report.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps({"record": RECORD_ID, "files": reports}, indent=2)
    args.report.write_text(text + "\n", encoding="utf-8")
    print(text)
    print("Saved:", args.report)


if __name__ == "__main__":
    main()
