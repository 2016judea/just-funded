"""The page prints counts straight from private/rows.json, and site/ ships only the free slice.
Pins the 2026-10-18 finding: a row is a LOAN, and a borrower often closes two the same day
(69 of 710 rows), so "710 borrowers" and "N businesses got a loan in June" counted loans as
businesses. Run from the repo root: python3 -m pytest -q tests
"""
import datetime as dt, gzip, json, re, statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D = json.load(open(ROOT / "private" / "rows.json"))
ROWS = D["rows"]
PAGE = (ROOT / "site" / "public" / "index.html").read_text()
FREE = json.loads(re.search(r"\nconst FREE=(\{.*?\});\n", PAGE).group(1))
FULL = json.loads(gzip.open(ROOT / "private" / "bundle" / "full.json.gz", "rt").read())["rows"]
PAID = ["street", "zip", "amount", "lender", "drawn", "naics", "lat", "lon", "jobs", "term", "id"]
biz = lambda rs: len({(r["name"], r["city"]) for r in rs})


def test_rows_sit_inside_the_window():
    for r in ROWS:
        assert D["since"] <= r["approved"] <= D["as_of"], (r["name"], r["approved"])
        assert r["month"] == r["approved"][:7] and r["amount"] > 0, r["name"]


def test_page_counts_businesses_not_loans():
    latest = max(r["month"] for r in ROWS)
    latest_rows = [r for r in ROWS if r["month"] == latest]
    month = dt.date.fromisoformat(latest + "-15").strftime("%B %Y")
    opening = biz([r for r in ROWS if r["why"] in ("Opening", "Changed hands")])
    assert biz(ROWS) < len(ROWS)  # the premise: some borrowers closed two loans
    assert f"<b>{biz(latest_rows)}</b> Twin Cities businesses got an SBA loan in {month}." in PAGE
    assert f"<b>{len(ROWS)} loans to {biz(ROWS)} borrowers</b>" in PAGE
    assert f"<b>{opening}</b> of them are opening a business or just bought one" in PAGE
    assert f"median <b>${statistics.median(r['amount'] for r in ROWS):,.0f}</b>" in PAGE
    assert f'content="{biz(ROWS)} Twin Cities businesses got an SBA' in PAGE
    assert f"({D['dropped_unfunded']} of them)" in PAGE
    assert FREE["total"] == len(ROWS) and sum(FREE["cells"].values()) == len(ROWS)


def test_site_ships_only_the_free_slice():
    assert len(FREE["rows"]) == 5 and len(FULL) == len(ROWS)
    keys = {k for r in FREE["rows"] for k in r}
    assert not keys & set(PAID), keys & set(PAID)
    for r in FREE["rows"]:
        assert any(f["name"] == r["name"] and f["approved"] == r["approved"] and f["band"] == r["band"] for f in FULL), r["name"]
    assert not list((ROOT / "site").rglob("*.gz")) and not (ROOT / "site" / "api" / "_full").exists()
    assert "_vercel/insights/script.js" in PAGE and "posthog" in PAGE


def test_only_public_is_static_so_the_bundle_is_never_a_url():
    """2026-10-18, three sibling products: with outputDirectory "." the paid bundle was a URL at
    /api/_full%2Ffull.json.gz (the redirect matches the raw path only). Only site/public/ is static here."""
    vj = json.loads((ROOT / "site" / "vercel.json").read_text())
    assert vj["outputDirectory"] == "public"
    top = {p.name for p in (ROOT / "site").iterdir() if p.is_file()}
    assert top == {"vercel.json"}, top
    assert not list((ROOT / "site" / "public").rglob("*.gz")) and not (ROOT / "site" / "public" / "api").exists()
    assert (ROOT / "site" / "public" / "offer.json").exists() and (ROOT / "site" / "public" / "paywall.js").exists()


def test_deploy_does_not_override_the_public_output():
    """2026-10-19: vercel.json said "public" but deploy.py's projectSettings said ".", and the
    REST deploy took projectSettings: the paid bundle was a 200 at /api/%5Ffull/full.json.gz for
    two hours. Both must say public."""
    src = (ROOT / "scripts" / "deploy.py").read_text()
    assert '"outputDirectory": "public"' in src and '"outputDirectory": "."' not in src
    assert '"site" / "public" / "offer.json"' in src
