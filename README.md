# Just Funded

**Live:** https://just-funded.vercel.app

Who in the seven-county Twin Cities just closed an SBA 7(a) or 504 loan, so the contractors,
equipment dealers and HVAC-R shops that sell capex can reach them the week they have the money.
Every loan the SBA approved in Hennepin, Ramsey, Dakota, Anoka, Washington, Scott and Carver in
the last twelve months: borrower, where, what they do, what the money most likely buys, how much,
whether it is drawn yet, and who lent it. Source: the SBA's 7(a) and 504 FOIA release (public
domain), cut by project county; loans cancelled or never funded are left out.

The step taken over: finding the next customer the week they have the money, instead of three
months later from a permit.

## Free and paid

| | what | why |
|---|---|---|
| free | the counts for the whole year and the newest month, by county and by what the money buys; 5 real rows (borrower, city, what they do, amount band, why now) | proves the file is real on names the reader can look up |
| **$300** | all rows with street, zip, NAICS, exact amount, lender, first-disbursement date, jobs, term; the biggest-first and money-drawn sorts; the spreadsheet; one password that keeps working as the list refreshes | the part the vendor acts on is *where* and *how much* |

## Price

$300 once. **A hypothesis** (2026-10-19): the smallest buyer here is an HVAC-R shop, and one
rooftop unit or kitchen hood job on a new restaurant is roughly $25,000 billed at about 20%
margin, so $5,000 earned from one landed job; a tenth of that is $500. A fit-out GC's one job is
worth three times more. $300 sits under a tenth of the smallest win, so one landed job from any
segment pays for the list many times over. Revise on checkout-vs-payment evidence.

## Freshness, stated

The SBA publishes the file quarterly (this one is as of 2026-06-30, the latest on
data.sba.gov on 2026-10-18), so the newest loans on the page are one to four months old. The
as-of date is printed on the page. `pipeline/pull.py` re-pulls weekly and only downloads when the
page's as-of date is newer than `data/_meta.json`.

## The paywall

Ported from `~/Desktop/mpls-new-rentals` (`product-paywall` skill). Only `site/public/` is
static on Vercel; `scripts/publish.py` writes the full list to `private/bundle/full.json.gz`
(gitignored) and `scripts/deploy.py` uploads it as `api/_full/`, read only by `/api/data`.
(With `outputDirectory: "."` the bundle was a URL at `/api/_full%2F...` on three sibling
products on 2026-10-18; `tests/test_page.py` pins the `public/` layout.)

| route | does |
|---|---|
| `POST /api/checkout` | Stripe embedded Checkout, $300, mints the password into session metadata + invoice |
| `POST /api/stripe-webhook` | emails the buyer the password (Mailgun), once; registered with the shared `stripe-router` |
| `GET /api/session-status` | the return page's check; sends the password if the webhook has not |
| `GET /api/data` | password in `x-password`: HMAC check, then a paid session in Stripe |

Comp password: `python3 scripts/issue_password.py "comp:<label>"`. A lost password:
`python3 scripts/fulfil.py <session_id>`. Vercel env: `STRIPE_SECRET_KEY`,
`STRIPE_WEBHOOK_SECRET`, `ACCESS_SECRET`, `MAILGUN_*`, `SITE_URL`.

## Distribution

Round 1 is drafted, not sent (`outreach/round1/`, gitignored): three segments (fit-out GCs,
equipment dealers, HVAC-R), each recipient's page at `/for/<token>/` opens on their own county
and trade, and the opener is a borrower in their own city (or their own SBA loan). Emails were
verified by reading them off the vendor's own site on the drafting day; the rest are held.

**A/B, one variable, pooled across the seven products of this round.** Variant A states the
price in the email; variant B leaves the price to the page. Assigned alternately within each
segment; `variant` is in the ledger and in `site/public/for.json`, and the page fires
`preview_open {variant}` so visits, `checkout_open` and `paid` split by variant without the
variant ever appearing in the URL. **Hypothesis:** stating the price in the email lowers clicks
but raises paid-per-click. Readout at day 3 after the sends.

## Run it

    python3 pipeline/pull.py                       # SBA FOIA, cut to the 7 counties (bricks cache or download)
    python3 pipeline/build.py                      # the rolling 12-month list -> private/rows.json
    python3 scripts/publish.py                     # site/public/index.html + private/bundle/full.json.gz
    VERCEL_TOKEN=... python3 scripts/deploy.py     # REST deploy, polls READY, analytics on
    python3 -m pytest -q tests                     # 14 tests; output in test-output.log

See `DATA_MODEL.md` for the ideal model and which fields could not be filled (contact and owner
name are not in the file; freshness is quarterly).

MIT licence. Data: U.S. Small Business Administration, 7(a) & 504 FOIA release, public domain.
