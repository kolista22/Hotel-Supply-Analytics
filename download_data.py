"""Download only the attributed CSV; never copy someone else's application."""
from pathlib import Path
import hashlib
import json
import urllib.request
ROOT = Path(__file__).resolve().parent
URL = "https://raw.githubusercontent.com/rfordatascience/tidytuesday/main/data/2020/2020-02-11/hotels.csv"
if __name__ == "__main__":
    path = ROOT / "data/hotels.csv"
    if path.exists():
        print("CSV already exists; not overwritten.")
    else:
        with urllib.request.urlopen(URL, timeout=45) as response:
            data = response.read()
        path.parent.mkdir(exist_ok=True)
        with path.open("xb") as target: target.write(data)
        meta = {"source_url": URL, "sha256": hashlib.sha256(data).hexdigest(), "authors": "Nuno Antonio, Ana de Almeida, Luis Nunes", "publication_doi": "10.1016/j.dib.2018.11.126", "license": "CC BY 4.0", "license_url": "https://creativecommons.org/licenses/by/4.0/", "mirror": "TidyTuesday 2020-02-11"}
        (ROOT/"data/source.json").write_text(json.dumps(meta,indent=2)+"\n")
        print("Downloaded hotels.csv; source hash recorded.")
