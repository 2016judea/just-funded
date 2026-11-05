#!/usr/bin/env python3
"""Round 1 distribution: 50 named vendors across three segments, each with an own-record opener,
a /for/<token>/ page that opens on their county and trade, an A/B variant, and a draft. Nothing sent.

    python3 scripts/outreach.py            # pull, verify, dedupe, draft; writes outreach/round1/* and site/for.json

Segments (Overture places with an email, cc-by-4.0, pulled 2026-08-19 into bricks closed_system):
  gc         contractor, construction_services          -> borrowers opening, under 2 years, or changed hands
  equipment  industrial_equipment, business_manufacturing_and_supply, restaurant_equipment_and_supply
             -> Industrial & wholesale, Restaurant & food, Construction trade
  hvac       hvac_services                              -> Restaurant & food, Clinic & care, Retail, Hotel, Salon
Own record = the vendor's own SBA loan if it has one, else a borrower in THEIR city in their segment's
groups. No such borrower -> status=hold. Email verified by reading it off the vendor's own site today;
not found -> hold. Deduped against ~/Desktop/workspace/outreach-ledger/outreach.duckdb (contacted).
A/B (one variable, pooled across the seven products): A states the price in the email, B leaves it to the page.
"""
import csv, datetime as dt, hashlib, json, re, ssl, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import duckdb

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outreach" / "round1"
CLOSED = Path.home() / "Desktop/workspace/bricks/data/closed_system.duckdb"
LEDGER = Path.home() / "Desktop/workspace/outreach-ledger/outreach.duckdb"
OFFER = json.loads((ROOT / "site/public/offer.json").read_text())
ROWS = json.load(open(ROOT / "private/rows.json"))["rows"]
TODAY = dt.date.today().isoformat()
TARGET = {"gc": 22, "equipment": 16, "hvac": 12}
SEG = {
    "gc": (("contractor", "construction_services"), None, ("Opening", "Changed hands", "Under 2 years old")),
    "equipment": (("industrial_equipment", "business_manufacturing_and_supply", "restaurant_equipment_and_supply"),
                  ("Industrial & wholesale", "Restaurant & food", "Construction trade"), None),
    "hvac": (("hvac_services",), ("Restaurant & food", "Clinic & care", "Retail & storefront", "Hotel, fitness & fun", "Salon, pet & auto service"), None),
}
SEG_WORD = {"gc": "fit-out work", "equipment": "equipment", "hvac": "HVAC work"}
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126.0 Safari/537.36"}
CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE
CITY_FIX = {"St Paul": "Saint Paul", "St. Paul": "Saint Paul", "Mpls": "Minneapolis"}
norm = lambda s: re.sub(r"[^a-z0-9]", "", re.sub(r"\b(llc|inc|co|corp|corporation|company|ltd|the)\b", "", (s or "").lower()))


def vendors():
    c = duckdb.connect(str(CLOSED), read_only=True)
    out = []
    for seg, (cats, _, _) in SEG.items():
        q = """select attrs::varchar from record where layer='overture_places' and json_extract_string(attrs::json,'$.emails') not in ('null')
               and json_extract_string(attrs::json,'$.emails') is not null and json_extract_string(attrs::json,'$.category') in (%s)
               order by cast(json_extract_string(attrs::json,'$.confidence') as double) desc""" % ",".join(f"'{x}'" for x in cats)
        for (a,) in c.execute(q).fetchall():
            a = json.loads(a)
            email = (a.get("emails") or [None])[0]
            if not email or not re.match(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", email, re.I) or re.search(r"noreply|no-reply|example\.", email, re.I):
                continue
            site = (a.get("websites") or [None])[0]
            if not site:
                continue
            out.append({"segment": seg, "company": a["name"], "city": CITY_FIX.get(a.get("city") or "", a.get("city") or ""), "zip": (a.get("postcode") or "")[:5],
                        "email": email.lower(), "website": site, "lat": a.get("lat"), "lon": a.get("lon")})
    return out


def county_of(zip5, lat, lon):
    """County by the borrower file's own zip->county votes, else the nearest borrower with coordinates."""
    votes = {}
    for r in ROWS:
        if r["zip"] == zip5:
            votes[r["county"]] = votes.get(r["county"], 0) + 1
    if votes:
        return max(votes, key=votes.get)
    if lat and lon:
        near = min((r for r in ROWS if r["lat"]), key=lambda r: (r["lat"] - lat) ** 2 + (r["lon"] - lon) ** 2, default=None)
        if near and (near["lat"] - lat) ** 2 + (near["lon"] - lon) ** 2 < 0.05:
            return near["county"]
    return None


def own_record(v):
    """(kind, row). kind 'own' = the vendor's own SBA loan; 'city' = a borrower in their city for their trade."""
    me = norm(v["company"])
    if len(me) >= 6:
        for r in ROWS:
            if norm(r["name"]) == me and r["city"].lower() == v["city"].lower():
                return "own", r
    _, groups, whys = SEG[v["segment"]]
    fits = [r for r in ROWS if r["city"].lower() == v["city"].lower() and (groups is None or r["group"] in groups)
            and (whys is None or r["why"] in whys) and r["group"] != "Construction trade"]
    if fits:
        # an equipment dealer's example should make things or feed people, not broker goods
        pref = (lambda r: (v["segment"] == "equipment" and not (r["naics"].startswith("3") or r["group"] == "Restaurant & food"), r["approved"] < "0"))
        return "city", sorted(fits, key=lambda r: (pref(r), r["approved"]), reverse=False)[-1] if v["segment"] != "equipment" else sorted(fits, key=lambda r: (not pref(r)[0], r["approved"]), reverse=True)[0]
    return None, None


def fetch(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=12, context=CTX) as r:
            return r.read(400_000).decode("utf-8", "replace")
    except Exception:
        return ""


def verify(v):
    """The email read off the vendor's own site today: (source_url) or None."""
    base = v["website"].rstrip("/")
    needle = v["email"].lower()
    for path in ("", "/contact", "/contact-us", "/about"):
        html = fetch(base + path)
        if not html:
            continue
        low = html.lower().replace("&#64;", "@").replace("%40", "@").replace(" [at] ", "@").replace("(at)", "@")
        if needle in low:
            return base + path
    return None


def token(v):
    return hashlib.sha1(f"{OFFER['product']}:{v['email']}".encode()).hexdigest()[:10]


LATEST = max(r["month"] for r in ROWS)
latest_name = dt.date.fromisoformat(LATEST + "-15").strftime("%B")


def draft(v, kind, r, variant, link, cnt_city, cnt_county, month_n):
    amt = f"${r['amount']:,.0f}"
    date = dt.date.fromisoformat(r["approved"]).strftime("%B %-d, %Y")
    first = (v.get("name") or "").split(" ")[0]
    hi = f"Hi {first}," if first else "Hi,"
    if kind == "own":
        l1 = f"The SBA's public file shows {v['company']}'s own {r['program']} loan: {amt}, approved {date} through {r['lender']}."
        l2 = f"You know how fast that money turns into work. {cnt_county} more SBA loans in {r['county']} County in the last twelve months most likely buy {SEG_WORD[v['segment']]}, {month_n} of them in {latest_name}."
    else:
        l1 = f"{r['name']}, {r['what'].lower()} in {r['city']}, got a {amt} SBA {r['program']} loan approved on {date}" + (f" ({r['why'].lower()})." if r["why"] != "Existing" else ".")
        l2 = f"That is one of {cnt_city} in {v['city']} and {cnt_county} across {r['county']} County in the last twelve months whose money most likely buys {SEG_WORD[v['segment']]}."
    offer = f"I pulled every SBA 7(a) and 504 loan approved in the seven counties from the SBA's public file, with what each borrower does and whether the money is drawn yet. 5 are open to poke at, no login: {link}"
    if variant == "A":
        offer += f" The full list is ${OFFER['price_usd']}, once."
    body = [hi, "", l1 + " " + l2, "", offer, "", "Best,", "Aidan", "https://randomaidan.substack.com/p/business-prototypes"]
    return "\n".join(body)


def main():
    OUT.mkdir(parents=True, exist_ok=True); (OUT / "drafts").mkdir(exist_ok=True)
    allv = vendors()
    print("vendors with email+site:", {s: sum(v["segment"] == s for v in allv) for s in SEG})
    led = duckdb.connect(str(LEDGER), read_only=True)
    contacted = {k for (k,) in led.execute("select recipient_key from contacted").fetchall()}
    seen_org = set(); cand = []
    for v in allv:
        if v["email"] in contacted or norm(v["company"]) in seen_org or v["email"].split("@")[1] in {c["email"].split("@")[1] for c in cand}:
            continue
        seen_org.add(norm(v["company"]))
        kind, r = own_record(v)
        v["kind"], v["row"] = kind, r
        v["county"] = (r["county"] if r else None) or county_of(v["zip"], v["lat"], v["lon"])
        cand.append(v)
    print("after dedupe:", len(cand), "with own record:", sum(bool(v["kind"]) for v in cand), "own loan:", sum(v["kind"] == "own" for v in cand))
    # verify emails for those with a record, most recent record first, until each segment is full (+ spare)
    pool = {s: [v for v in cand if v["segment"] == s and v["kind"]] for s in SEG}
    for s in pool:
        pool[s].sort(key=lambda v: (v["kind"] != "own", v["row"]["approved"]), reverse=False)
        pool[s].sort(key=lambda v: v["row"]["approved"], reverse=True)
        pool[s].sort(key=lambda v: v["kind"] != "own")
    todo = [v for s in SEG for v in pool[s][: (TARGET[s] * 6 if s != "gc" else TARGET[s] * 3)]]
    with ThreadPoolExecutor(12) as ex:
        for v, src in zip(todo, ex.map(verify, todo)):
            v["email_source"] = src
    ledger, fors, n = [], {}, {s: 0 for s in SEG}
    ab = {s: 0 for s in SEG}
    for s in SEG:
        for v in pool[s]:
            if n[s] >= TARGET[s]:
                break
            if "email_source" not in v:
                continue
            tok = token(v)
            r = v["row"]
            cnt_city = sum(1 for x in ROWS if x["city"].lower() == v["city"].lower() and (SEG[s][1] is None or x["group"] in SEG[s][1]) and (SEG[s][2] is None or x["why"] in SEG[s][2]))
            cnt_county = sum(1 for x in ROWS if x["county"] == r["county"] and (SEG[s][1] is None or x["group"] in SEG[s][1]) and (SEG[s][2] is None or x["why"] in SEG[s][2]))
            month_n = sum(1 for x in ROWS if x["county"] == r["county"] and x["month"] == max(y["month"] for y in ROWS) and (SEG[s][1] is None or x["group"] in SEG[s][1]) and (SEG[s][2] is None or x["why"] in SEG[s][2]))
            if not v["email_source"]:
                status, hold = "hold", "email not on their own site"
                variant = ""
            else:
                status, hold = "draft", ""
                variant = "AB"[ab[s] % 2]; ab[s] += 1; n[s] += 1
            link = f"{OFFER['site']}/for/{tok}/"
            if status == "draft":  # holds never get a page; a GC's page opens on every trade in their county (fit-out is any opening business)
                fors[tok] = {"company": v["company"], "city": v["city"], "county": r["county"], "groups": list(SEG[s][1] or []), "variant": variant, "city_n": cnt_city}
            own = (f"their own SBA loan: {r['name']} {r['program']} ${r['amount']:,.0f} approved {r['approved']}" if v["kind"] == "own"
                   else f"{r['name']} ({r['what']}), {r['city']}: ${r['amount']:,.0f} {r['program']} approved {r['approved']}, {r['why']}")
            ledger.append({"token": tok, "variant": variant, "segment": s, "company": v["company"], "name": "", "email": v["email"],
                           "email_source": v["email_source"] or v["website"], "email_source_date": TODAY if v["email_source"] else "2026-08-19 (Overture only)",
                           "own_record": own, "status": status, "hold_reason": hold, "drafted_on": TODAY, "sent_on": "", "reply_kind": "", "reply_on": ""})
            if status == "draft":
                text = f"To: {v['email']}\nSubject: bricks / {v['company']}\n\n" + draft(v, v["kind"], r, variant, link, cnt_city, cnt_county, month_n)
                (OUT / "drafts" / f"{tok}.txt").write_text(text)
    # holds for segment members with no own record at all (the first few, so the hold reasons are on the ledger)
    for s in SEG:
        for v in [v for v in cand if v["segment"] == s and not v["kind"]][:4]:
            ledger.append({"token": token(v), "variant": "", "segment": s, "company": v["company"], "name": "", "email": v["email"], "email_source": v["website"],
                           "email_source_date": "2026-08-19 (Overture only)", "own_record": "", "status": "hold", "hold_reason": f"no borrower in {v['city']} for their trade in the last 12 months",
                           "drafted_on": TODAY, "sent_on": "", "reply_kind": "", "reply_on": ""})
    for stale in (OUT / "drafts").glob("*.txt"):  # a draft from an earlier run that is no longer on the ledger
        if stale.stem not in {l["token"] for l in ledger if l["status"] == "draft"}:
            stale.unlink()
    with (OUT / "ledger.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(ledger[0].keys())); w.writeheader(); w.writerows(ledger)
    (ROOT / "site/public/for.json").write_text(json.dumps(fors, separators=(",", ":")))
    drafted = [l for l in ledger if l["status"] == "draft"]
    print("drafted", len(drafted), {s: sum(l["segment"] == s for l in drafted) for s in SEG},
          "A/B", {v: sum(l["variant"] == v for l in drafted) for v in "AB"},
          "holds", {h: sum(l["hold_reason"] == h for l in ledger) for h in {l["hold_reason"] for l in ledger if l["hold_reason"]}})


if __name__ == "__main__":
    main()
