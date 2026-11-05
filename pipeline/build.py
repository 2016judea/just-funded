#!/usr/bin/env python3
"""The rolling list: every SBA 7(a) or 504 loan approved in the seven counties in the last
twelve months of the release, where money moved (cancelled and never-funded loans dropped).
Reads data/{7a,504}_market.json (pipeline/pull.py). Writes private/rows.json.

Every field is the SBA's own, except three derived ones, each with its rule here:
  group  what the borrower is likely buying, from the NAICS code (GROUPS)
  why    why now, from BusinessAge (WHY)
  drawn  the money is in hand: FirstDisbursementDate is set
Coordinates come from the bricks closed-system parcel join where one exists (57%).
"""
import datetime as dt, json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA, PRIV = ROOT / "data", ROOT / "private"
CLOSED = Path.home() / "Desktop/workspace/bricks/data/closed_system.duckdb"
MONTHS = 12

# NAICS prefix -> what the money most likely buys. First match wins; longest prefixes first.
GROUPS = [
    (("722", "7224", "7225", "311", "3118", "445", "4452", "4453"), "Restaurant & food"),
    (("621", "622", "623", "624", "6212", "6213"), "Clinic & care"),
    (("31", "32", "33", "42", "48", "49", "493"), "Industrial & wholesale"),
    (("44", "45", "453", "454"), "Retail & storefront"),
    (("812", "8121", "8123", "8129", "8111", "8112", "8113"), "Salon, pet & auto service"),
    (("71", "721", "713"), "Hotel, fitness & fun"),
    (("23",), "Construction trade"),
    (("54", "52", "53", "55", "56", "61", "51"), "Office & professional"),
]
WHY = {
    "Startup, Loan Funds will Open Business": "Opening",
    "New Business or 2 years or less": "Under 2 years old",
    "Change of Ownership": "Changed hands",
    "Existing or more than 2 years old": "Existing",
}
GROUP_ORDER = [g for _, g in GROUPS] + ["Other"]
WHY_ORDER = ["Opening", "Under 2 years old", "Changed hands", "Existing"]
COUNTY_ORDER = ["Hennepin", "Ramsey", "Dakota", "Anoka", "Washington", "Scott", "Carver"]


def group_of(naics):
    n = (naics or "").strip()
    for prefixes, g in GROUPS:
        if any(n.startswith(p) for p in prefixes):
            return g
    return "Other"


def band(amount):
    for lo, hi, label in ((0, 50e3, "under $50k"), (50e3, 150e3, "$50k to $150k"), (150e3, 350e3, "$150k to $350k"),
                          (350e3, 1e6, "$350k to $1M"), (1e6, 5e6, "$1M to $5M")):
        if lo <= amount < hi:
            return label
    return "over $5M"


def title(s):
    s = re.sub(r"\s+", " ", (s or "").strip())
    t = s.title()
    t = re.sub(r"\b(Llc|L\.L\.C\.|Inc|Pllc|Dds|Dmd|Pa|Ltd|Lp|Llp|Pc|Usa|Na|Fsb|Mn|Ne|Nw|Se|Sw|Cdc|Sba|Mhc|Mbc)\b", lambda m: m.group(1).upper(), t)
    return re.sub(r"(\d)(St|Nd|Rd|Th)\b", lambda m: m.group(1) + m.group(2).lower(), t)


def coords():
    try:
        import duckdb
        c = duckdb.connect(str(CLOSED), read_only=True)
        rows = c.execute("""select r.attrs->>'LocationID', r.attrs->>'ApprovalDate', r.attrs->>'BorrName', p.lat, p.lon
            from record r join parcel p on p.parcel_key=r.parcel_key where r.layer='sba_loans' and p.lat is not null""").fetchall()
        return {(a, b, (c_ or "").strip()): (lat, lon) for a, b, c_, lat, lon in rows}
    except Exception as e:  # no bricks checkout: rows ship without coordinates
        print("coords skipped:", e)
        return {}


def main():
    meta = json.loads((DATA / "_meta.json").read_text())
    as_of = dt.datetime.strptime(meta["as_of"], "%y%m%d").date()
    y, m = as_of.year, as_of.month - (MONTHS - 1)
    since = dt.date(y - (m <= 0), m + 12 if m <= 0 else m, 1)
    xy = coords()
    rows, dropped = [], 0
    for program in ("7a", "504"):
        for r in json.loads((DATA / f"{program}_market.json").read_text())["rows"]:
            d = (r.get("ApprovalDate") or "")[:10]
            if not d or d < since.isoformat():
                continue
            if (r.get("LoanStatus") or "").strip() in ("CANCLD", "NOT FUNDED"):
                dropped += 1
                continue
            amt = float(r.get("GrossApproval") or 0)
            key = (r.get("LocationID"), d, (r.get("BorrName") or "").strip())
            lat, lon = xy.get(key, (None, None))
            is_7a = program == "7a"
            rows.append({
                "id": f"{program}:{r.get('LocationID')}:{d}:{re.sub(r'[^a-z0-9]', '', (r.get('BorrName') or '').lower())[:24]}",
                "name": title(r.get("BorrName")),
                "street": title(r.get("BorrStreet")),
                "city": title(r.get("BorrCity")),
                "zip": (r.get("BorrZip") or "").strip()[:5],
                "county": (r.get("ProjectCounty") or "").strip().title(),
                "naics": (r.get("NaicsCode") or "").strip(),
                "what": (r.get("NaicsDescription") or "").strip(),
                "group": group_of(r.get("NaicsCode")),
                "why": WHY.get((r.get("BusinessAge") or "").strip(), "Existing"),
                "program": "7(a)" if is_7a else "504",
                "amount": amt,
                "band": band(amt),
                "approved": d,
                "month": d[:7],
                "drawn": (r.get("FirstDisbursementDate") or "")[:10],
                "lender": title(r.get("BankName") if is_7a else r.get("CDC_Name")),
                "franchise": (r.get("FranchiseName") or "").strip(),
                "jobs": int(float(r.get("JobsSupported") or 0)),
                "term": int(float(r.get("TermInMonths") or 0)),
                "lat": round(lat, 5) if lat else None,
                "lon": round(lon, 5) if lon else None,
            })
    rows.sort(key=lambda r: (r["approved"], r["amount"]), reverse=True)
    PRIV.mkdir(exist_ok=True)
    out = {"as_of": as_of.isoformat(), "since": since.isoformat(), "built": dt.date.today().isoformat(),
           "dropped_unfunded": dropped, "rows": rows}
    (PRIV / "rows.json").write_text(json.dumps(out, indent=0))
    latest = rows[0]["month"]
    print(f"{len(rows)} loans {since} to {as_of} ({dropped} cancelled/not funded dropped); latest month {latest}: "
          f"{sum(r['month'] == latest for r in rows)}; with coords {sum(bool(r['lat']) for r in rows)}")
    print({g: sum(r["group"] == g for r in rows) for g in GROUP_ORDER})
    print({w: sum(r["why"] == w for r in rows) for w in WHY_ORDER})


if __name__ == "__main__":
    main()
