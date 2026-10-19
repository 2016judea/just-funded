#!/usr/bin/env python3
"""Pull the SBA 7(a) + 504 FOIA release and cut it to the seven-county Twin Cities market.

    python3 pipeline/pull.py            # reuse the bricks cache if it carries the same as-of date
    python3 pipeline/pull.py --fresh    # download the two CSVs from data.sba.gov (~130 MB)

Source page: https://data.sba.gov/dataset/7a-504-foia (public domain, U.S. Government Works).
The release is quarterly; the page names its as-of date ("as of June 30, 2026"). This script
reads that date off the page, and only downloads when it is newer than data/_meta.json.
Writes data/7a_market.json, data/504_market.json and data/_meta.json.
"""
import csv, io, json, re, sys, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
BRICKS_CACHE = Path.home() / "Desktop/bricks/data/cache/sba"
PAGE = "https://data.sba.gov/dataset/7a-504-foia"
COUNTIES = {"HENNEPIN", "RAMSEY", "DAKOTA", "ANOKA", "WASHINGTON", "SCOTT", "CARVER"}
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126.0 Safari/537.36"}


def page_release():
    """(as_of 'YYMMDD', {'7a': url, '504': url}) from the dataset page."""
    html = urllib.request.urlopen(urllib.request.Request(PAGE, headers=UA), timeout=60).read().decode()
    urls = {}
    for m in re.finditer(r'href="(https://data\.sba\.gov/[^"]*FOIA_(7a|504)_FY20(?:20|10)_Present_asof_(\d{6})\.csv)"', html):
        urls[m.group(2).lower()] = m.group(1)
    dates = set(re.findall(r"asof_(\d{6})\.csv", html))
    if len(urls) != 2 or not dates:
        sys.exit(f"could not read the two Present CSVs off {PAGE}: {urls}")
    return max(dates), urls


def cut(csv_bytes):
    rows = []
    for r in csv.DictReader(io.StringIO(csv_bytes.decode("utf-8-sig", errors="replace"))):
        if (r.get("ProjectState") or "").strip() == "MN" and (r.get("ProjectCounty") or "").strip().upper() in COUNTIES:
            rows.append(r)
    return rows


def main():
    fresh = "--fresh" in sys.argv
    DATA.mkdir(exist_ok=True)
    meta_path = DATA / "_meta.json"
    have = json.loads(meta_path.read_text())["as_of"] if meta_path.exists() else ""
    as_of, urls = page_release()
    if not fresh and have == as_of and all((DATA / f"{p}_market.json").exists() for p in ("7a", "504")):
        print(f"data/ already holds the {as_of} release")
        return
    bricks_meta = json.loads((BRICKS_CACHE / "_meta.json").read_text()) if (BRICKS_CACHE / "_meta.json").exists() else {}
    bricks_as_of = re.search(r"asof_(\d{6})", json.dumps(bricks_meta.get("urls", {})))
    files = {}
    if not fresh and bricks_as_of and bricks_as_of.group(1) == as_of:
        for p in ("7a", "504"):
            rows = json.loads((BRICKS_CACHE / f"{p}_market.json").read_text())["rows"]
            rows = [r for r in rows if (r.get("ProjectCounty") or "").strip().upper() in COUNTIES]
            files[p] = rows
            print(f"{p}: {len(rows)} market rows from the bricks cache ({as_of})")
    else:
        for p, url in urls.items():
            print(f"downloading {url}")
            body = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=600).read()
            files[p] = cut(body)
            n_lines = body.count(b"\n")
            print(f"{p}: {len(files[p])} market rows of {n_lines:,} in the file")
    for p, rows in files.items():
        (DATA / f"{p}_market.json").write_text(json.dumps({"as_of": as_of, "url": urls[p], "rows": rows}))
    meta_path.write_text(json.dumps({
        "_what": "SBA 7(a) and 504 FOIA loans, cut to the seven-county Twin Cities market (ProjectCounty).",
        "source_page": PAGE, "licence": "U.S. Government Works (public domain)",
        "attribution": "U.S. Small Business Administration, 7(a) & 504 FOIA release",
        "as_of": as_of, "urls": urls, "rows": {p: len(r) for p, r in files.items()},
    }, indent=1) + "\n")
    print("as of", as_of)


if __name__ == "__main__":
    main()
