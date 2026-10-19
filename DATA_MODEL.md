# Data model: Just Funded

Written from the need alone, before touching the data (BUSINESS.md rule 5), 2026-10-18.
Then checked against reality, field by field, below.

**The need.** A general contractor, an equipment dealer or an HVAC-R shop in the Twin
Cities sells capex. Their best customer is a business that just got the money: an SBA 7(a)
or 504 loan closed this month. The step we take over: finding the next customer the week
they have the money, before the trade finds out from a permit three months later.

## Ideal model

**Borrower** (one per loan; a business that just borrowed)

| field | answers for the vendor |
|---|---|
| business name | who to call |
| street, city, zip, county | is it on my route; which county list do I buy |
| lat / lon | put it on a map against my shop |
| what they do (NAICS code + plain words) | is this my kind of customer |
| what they will buy (trade group: fit-out, kitchen, industrial, HVAC) | is this my trade's money |
| program (7(a) or 504) | 504 = real estate and heavy equipment; 7(a) = working capital and fit-out |
| amount approved | how big a job can they fund |
| approval date | how fresh the money is |
| first disbursement date | do they have it in hand yet, or is it still committed |
| loan status | was it funded, or cancelled before any money moved |
| business age (startup / new / change of ownership / existing) | a startup needs everything; a change of ownership repaints and re-signs |
| lender | who introduced them; a lender is a referral channel |
| franchise | a franchise build-out follows a national spec |
| jobs supported | size of the operation |
| contact (phone, email, website) | how to reach the owner |
| the owner's name | who signs |

**Vendor** (the buyer of this list; one per contractor or dealer)

| field | answers |
|---|---|
| name, city, trade | which borrowers are theirs |
| email, website | where the list goes |
| their own SBA loan, if any | their own record, for the opener |

**Join:** borrower.trade_group ∈ vendor.trades and borrower.county = vendor's service area.

## Reality, field by field (checked 2026-10-18)

Source: SBA 7(a) and 504 FOIA release, public domain, as of **2026-06-30** (the latest
file on data.sba.gov on 2026-10-18; the release is quarterly). Cut to the seven counties by
`ProjectCounty`. 2,801 loans approved since 2024-01-01; 59 to 130 a month.

| field | filled? | note |
|---|---|---|
| business name, street, city, zip, county | **yes**, every row | BorrName, BorrStreet, BorrCity, BorrZip, ProjectCounty |
| lat / lon | **partial**: 1,590 of 2,801 (57%) join to a county parcel | the rest geocode by address later; no map in v1 |
| NAICS code + words | **yes** | NaicsCode, NaicsDescription |
| trade group | **derived** from NAICS | rule table in `pipeline/build.py` |
| program, amount, approval date | **yes** | median $200,000; quartiles $50k / $510k |
| first disbursement date | **yes** for 2,141 of 2,801 | median 17 days after approval |
| loan status | **yes** | 263 CANCLD + 118 NOT FUNDED are dropped: no money moved |
| business age | **yes** | 1,560 existing / 482 new / 417 startup / 334 change of ownership |
| lender | **yes** | BankName |
| franchise | **yes** | 290 of 2,801 |
| jobs supported | **yes** | |
| contact (phone, email, website) | **no** | not in the FOIA file. Overture places can match ~half by name + city; left out of v1 so no number on the page is a guess |
| owner's name | **no** | not public in this file |
| freshness | **the gap**: the file is quarterly, so "this month" is 1 to 4 months old | the as-of date is printed on the page; we re-pull weekly and the list changes when SBA publishes |

**Verdict: build.** Every field the vendor acts on (who, where, what, how much, how fresh,
who lent) fills. The two that do not (contact, owner) are a lookup the vendor does in a
minute once they have the name; the step we take over is finding the name the week the money
lands. The freshness gap is stated, not hidden.
