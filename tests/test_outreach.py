"""The A/B test varies ONE thing, the price sentence (coordinator, 2026-10-19). The opener is
chosen by the recipient (own loan or a borrower in their city), never by the variant; arms are
balanced within each segment and within each opener kind. Skips when the gitignored ledger is absent."""
import csv
from collections import Counter
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "outreach" / "round1" / "ledger.csv"
PRICE = "The full list is $300, once."


@pytest.mark.skipif(not LEDGER.exists(), reason="ledger is gitignored")
def test_only_the_price_sentence_differs_and_arms_balance():
    rows = [r for r in csv.DictReader(LEDGER.open()) if r["status"] == "draft"]
    seg, kind = Counter(), Counter()
    for r in rows:
        t = (ROOT / "outreach" / "round1" / "drafts" / f"{r['token']}.txt").read_text()
        assert (PRICE in t) == (r["variant"] == "A"), r["token"]
        own = r["own_record"].startswith("their own")
        assert ("The SBA's public file shows" in t) == own, r["token"]
        sign = 1 if r["variant"] == "A" else -1
        seg[r["segment"]] += sign
        kind[(r["segment"], own)] += sign
    assert all(abs(v) <= 1 for v in seg.values()) and all(abs(v) <= 1 for v in kind.values()), (seg, kind)
