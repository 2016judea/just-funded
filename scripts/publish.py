#!/usr/bin/env python3
"""Write site/index.html (free slice) and private/bundle/full.json.gz (the paid list) from
private/rows.json (pipeline/build.py). Every number on the page is computed here."""
import datetime as dt, json, statistics, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pipeline"))
from sitekit import render
from build import GROUP_ORDER, WHY_ORDER, COUNTY_ORDER
ROOT = Path(__file__).resolve().parent.parent
OFFER = json.loads((ROOT / "site/public/offer.json").read_text())
D = json.load(open(ROOT / "private" / "rows.json"))
rows = D["rows"]
# Paid: where exactly, how much exactly, who lent, is the money drawn, the NAICS code, the map coordinates.
PAID = ["street", "zip", "amount", "lender", "drawn", "naics", "lat", "lon", "jobs", "term", "id"]
as_of = dt.date.fromisoformat(D["as_of"])
latest = max(r["month"] for r in rows)
latest_rows = [r for r in rows if r["month"] == latest]
month_name = dt.date.fromisoformat(latest + "-15").strftime("%B %Y")
median = statistics.median(r["amount"] for r in rows)
# A row is a LOAN; a borrower often closes two the same day (69 of 710 on 2026-10-18). Every
# "business" or "borrower" on the page counts distinct borrowers, never rows.
biz = lambda rs: len({(r["name"], r["city"]) for r in rs})
borrowers, latest_biz = biz(rows), biz(latest_rows)
opening = biz([r for r in rows if r["why"] in ("Opening", "Changed hands")])
# The free five: the newest month, the biggest first, spread across trade groups so the sample reads as a list, not a niche.
seen, sample = set(), []
for r in sorted(latest_rows, key=lambda r: -r["amount"]):
    if r["group"] not in seen:
        seen.add(r["group"]); sample.append(r)
    if len(sample) == 5:
        break
COLS = [("name", "Borrower"), ("street", "Street"), ("city", "City"), ("zip", "Zip"), ("county", "County"), ("naics", "NAICS"), ("what", "What they do"),
        ("group", "Likely buying"), ("why", "Why now"), ("program", "Program"), ("amount", "Amount approved"), ("approved", "Approval date"),
        ("drawn", "First disbursement"), ("lender", "Lender"), ("franchise", "Franchise"), ("jobs", "Jobs supported"), ("term", "Term (months)"), ("lat", "Lat"), ("lon", "Lon")]
cfg = """{groupOrder:%s,countyOrder:%s,csv:"just-funded-twin-cities-sba.csv",cols:%s,
 sorts:[["newest","Newest first",false],["biggest","Biggest loan first",true],["drawn","Money drawn most recently",true],["county","By county",false]],
 sortFn:{newest:r=>r.sort((a,b)=>b.approved.localeCompare(a.approved)||b.amount-a.amount),biggest:r=>r.sort((a,b)=>b.amount-a.amount),drawn:r=>r.sort((a,b)=>(b.drawn||"").localeCompare(a.drawn||"")||b.approved.localeCompare(a.approved)),county:r=>r.sort((a,b)=>a.county.localeCompare(b.county)||b.approved.localeCompare(a.approved))},
 lockText:n=>`${n} more borrowers, with street, zip, exact amount, lender, and whether the money is drawn`}""" % (
    json.dumps(GROUP_ORDER), json.dumps(COUNTY_ORDER), json.dumps(COLS))
as_of_s = as_of.strftime("%b %-d, %Y")
free = render(rows=rows, sample=sample, paid_fields=PAID, cfg_js=cfg, site=OFFER["product"], subs={
    "__TITLE__": "Just Funded",
    "__DESC__": f"{borrowers} Twin Cities businesses got an SBA 7(a) or 504 loan approved in the last twelve months. Who, where, how much, and what they are about to buy.",
    "__EYEBROW__": f"For contractors, equipment dealers and HVAC-R · SBA public records · as of {as_of_s}",
    "__H1__": f"<b>{latest_biz}</b> Twin Cities businesses got an SBA loan in {month_name}. Here is who, and what they are about to buy.",
    "__LEDE__": f"Every SBA 7(a) and 504 loan approved in the seven counties in the last twelve months: <b>{len(rows)} loans to {borrowers} borrowers</b>, median <b>${median:,.0f}</b>. "
                f"<b>{opening}</b> of them are opening a business or just bought one. They have the money now, and the fit-out, the kitchen, the line and the rooftop unit are what it buys.",
    "__NOTE__": f"<p>Source: the U.S. Small Business Administration's 7(a) and 504 FOIA release, public domain, as of {as_of_s} (the SBA publishes it quarterly, so the newest loans here are one to four months old; we re-pull every week and the list changes when the SBA does). Project county in Hennepin, Ramsey, Dakota, Anoka, Washington, Scott or Carver. Loans cancelled or never funded are left out ({D['dropped_unfunded']} of them).</p>"
                f"<p>How to read it. The amount is what the SBA approved, not what has been spent. <i>Drawn</i> is the SBA's first-disbursement date; a loan not yet drawn is committed money the borrower has not pulled. <i>Likely buying</i> is read off the borrower's NAICS code: a restaurant buys a kitchen and a hood, a clinic buys a fit-out, a manufacturer buys a line. <i>Why now</i> is the SBA's business-age field: opening, under two years old, changed hands, or existing.</p>"
                f"<p>From Aidan Jude at Brick &amp; Mortar (aidan@brickandmortar.dev).</p>",
})
print("rows", len(rows), "borrowers", borrowers, "latest", latest, len(latest_rows), latest_biz, "median", median, "opening/changed", opening, "sample", [r["name"] for r in sample], "cells", len(free["cells"]))
