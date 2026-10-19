"""The model loader (pipeline/build.py): its derived fields and its filters, checked against
data/*.json and private/rows.json. Run from the repo root."""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))
from build import GROUP_ORDER, WHY_ORDER, COUNTY_ORDER, group_of, band  # noqa: E402

D = json.load(open(ROOT / "private" / "rows.json"))
ROWS = D["rows"]
META = json.load(open(ROOT / "data" / "_meta.json"))


def test_group_rules():
    assert group_of("722511") == "Restaurant & food"
    assert group_of("621210") == "Clinic & care"
    assert group_of("332710") == "Industrial & wholesale"
    assert group_of("448140") == "Retail & storefront"
    assert group_of("812112") == "Salon, pet & auto service"
    assert group_of("236115") == "Construction trade"
    assert group_of("541110") == "Office & professional"
    assert group_of("") == "Other" and group_of("99") == "Other"


def test_bands_cover_every_amount():
    assert band(10_000) == "under $50k" and band(200_000) == "$150k to $350k" and band(6e6) == "over $5M"
    for r in ROWS:
        assert r["band"] == band(r["amount"]), r["name"]


def test_every_row_has_the_fields_the_vendor_acts_on():
    need = ["name", "city", "county", "naics", "what", "group", "why", "program", "amount", "band", "approved", "month", "lender"]
    for r in ROWS:
        for k in need:
            assert r.get(k) not in (None, ""), (r["name"], k)
        assert r["county"] in COUNTY_ORDER and r["group"] in GROUP_ORDER and r["why"] in WHY_ORDER
        assert r["program"] in ("7(a)", "504")


def test_unfunded_loans_are_dropped_and_window_is_twelve_months():
    assert D["dropped_unfunded"] > 0
    months = sorted({r["month"] for r in ROWS})
    # 2025-10 has no approvals in the file (the October 2025 federal shutdown), so 11 of 12 months carry rows
    assert 11 <= len(months) <= 12 and months[-1] == D["as_of"][:7] and months[0] == D["since"][:7]
    assert all(D["since"][:7] <= m <= D["as_of"][:7] for m in months)


def test_source_is_the_latest_release_and_public_domain():
    assert "public domain" in META["licence"] and META["as_of"] == D["as_of"][2:4] + D["as_of"][5:7] + D["as_of"][8:10]
    assert META["urls"]["7a"].endswith(f"asof_{META['as_of']}.csv")
    raw = json.load(open(ROOT / "data" / "7a_market.json"))["rows"]
    assert {r["ProjectCounty"].strip().upper() for r in raw} <= {c.upper() for c in COUNTY_ORDER}
