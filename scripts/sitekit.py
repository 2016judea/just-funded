"""Render site/index.html from template.html with the free slice baked in, and gzip the full
rows for /api/data (private/bundle/, uploaded by scripts/deploy.py as api/_full/).

The free slice is: the sample rows with every paid field stripped, and COUNTS of the whole
list by month x county x group x why. No other row of the full list ever lands in site/.
"""
import gzip, json, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
SITE, BUNDLE = ROOT / "site" / "public", ROOT / "private" / "bundle"  # only public/ is static on Vercel
dump = lambda o: json.dumps(o, separators=(",", ":"))


def analytics(site):
    ph = subprocess.run(["python3", str(Path.home() / ".claude/skills/site-analytics/posthog_inject.py"), "--site", site, "--print"],
                        capture_output=True, text=True, check=True).stdout
    reader = (Path(__file__).resolve().parent / "reader_events.js").read_text().strip()
    return ph + "<script>" + reader + "</script>"


def free_slice(rows, sample, paid_fields):
    for r in sample:
        assert r in rows
    free_rows = [{k: v for k, v in r.items() if k not in paid_fields} for r in sample]
    cells = {}
    for r in rows:
        k = f"{r['month']}|{r['county']}|{r['group']}|{r['why']}"
        cells[k] = cells.get(k, 0) + 1
    free = {"rows": free_rows, "cells": cells, "total": len(rows)}
    leak = [f for f in paid_fields if any(r.get(f) not in (None, "", 0) for r in free_rows)]
    assert not leak, leak
    return free


def render(*, rows, sample, paid_fields, cfg_js, subs, site):
    free = free_slice(rows, sample, paid_fields)
    h = (Path(__file__).resolve().parent / "template.html").read_text()
    for k, v in subs.items():
        h = h.replace(k, v)
    h = h.replace("__ANALYTICS__", analytics(site)).replace("__CFG__", cfg_js).replace("__FREE__", dump(free))
    head = h.split('<script src="/paywall.js">')[0]
    assert "__" not in head.replace("__SV", "").replace("__proto__", ""), "unfilled token"
    (SITE / "index.html").write_text(h)
    BUNDLE.mkdir(parents=True, exist_ok=True)
    (BUNDLE / "full.json.gz").write_bytes(gzip.compress(dump({"rows": rows}).encode(), 9))
    return free
