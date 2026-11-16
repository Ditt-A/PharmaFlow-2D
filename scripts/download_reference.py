"""Retrieve published Zenodo DEM/experimental reference files; verify checksums."""
import argparse
from pathlib import Path
import requests
from pharmaflow.dataio import md5_file

RECORD_ID = "20554446"
EXPECTED = {
    "quasi2D-sim.numbers": "00e53f48ae587beca990c5d1f709b24d",
    "quasi2D-expt.numbers": "c701fb415580d6ffa6d9fc9945bce0fe",
    "3D.sim.numbers": "00fff3dd1a07b3cb7966edfb744cae29",
}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--subset", choices=("sim", "expt", "all"), default="sim")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()
    if args.list:
        print("https://zenodo.org/records/" + RECORD_ID)
        for key, md5 in EXPECTED.items():
            print(key, md5)
        return

    response = requests.get("https://zenodo.org/api/records/" + RECORD_ID, timeout=40)
    response.raise_for_status()
    files = {item["key"]: item for item in response.json()["files"]}
    selected = list(EXPECTED) if args.subset == "all" else [
        "quasi2D-sim.numbers" if args.subset == "sim" else "quasi2D-expt.numbers"
    ]
    folder = Path("data/raw/zenodo_" + RECORD_ID)
    folder.mkdir(parents=True, exist_ok=True)
    for filename in selected:
        metadata = files[filename]
        published = metadata.get("checksum")
        expected = EXPECTED[filename]
        if published and published != "md5:" + expected:
            raise ValueError("Published checksum unexpected: " + filename)
        path = folder / filename
        if path.exists() and md5_file(path) == expected:
            print("Already verified:", path)
            continue
        url = metadata["links"].get("self") or metadata["links"].get("content")
        tmp = path.with_name(filename + ".part")
        try:
            with requests.get(url, timeout=(30, 180), stream=True) as result:
                result.raise_for_status()
                with tmp.open("wb") as stream:
                    for chunk in result.iter_content(1024 * 1024):
                        if chunk:
                            stream.write(chunk)
            if md5_file(tmp) != expected:
                raise ValueError("MD5 mismatch on " + filename)
            tmp.replace(path)
            print("Downloaded and verified:", path)
        finally:
            tmp.unlink(missing_ok=True)

if __name__ == "__main__":
    main()
