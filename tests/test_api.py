"""The paywall functions, driven with a fake req/res in node (no Vercel CLI on this Mac).
/api/data must 401 with no password or a made-up one, and hand the full list to a comp
password minted the way scripts/issue_password.py mints it. Run from the repo root."""
import hashlib, hmac, json, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SECRET = "test-secret-not-the-real-one"
ALPHA = "23456789BCDFGHJKMNPQRSTVWXYZ"

DRIVER = """
console.log = (...a) => process.stderr.write(a.join(" ") + String.fromCharCode(10)); // the handler logs unlocks; keep stdout for the result
const handlerPath = process.env.HANDLER, pw = process.env.PW || "";
const h = require(handlerPath);
const req = { method: "GET", headers: pw ? { "x-password": pw } : {}, query: {} };
let status = 0, body = null; const headers = {};
const res = { setHeader: (k, v) => { headers[k] = v; }, status(s) { status = s; return res; },
  json(j) { body = j; done(); return res; }, end(b) { body = b; done(); return res; } };
function done() { process.stdout.write(JSON.stringify({ status, headers, gz: Buffer.isBuffer(body), body: Buffer.isBuffer(body) ? body.length : body })); }
h(req, res).catch((e) => { process.stdout.write(JSON.stringify({ status: -1, error: String(e) })); });
"""


def chars(b, n):
    return "".join(ALPHA[x % len(ALPHA)] for x in b[:n])


def comp_password(label):
    s = SECRET.encode()
    nonce = chars(hmac.new(s, ("label:" + label).encode(), hashlib.sha256).digest(), 5)
    raw = nonce + chars(hmac.new(s, ("comp:" + nonce).encode(), hashlib.sha256).digest(), 7)
    return f"{raw[:4]}-{raw[4:8]}-{raw[8:]}"


def call(pw):
    env = {"ACCESS_SECRET": SECRET, "STRIPE_SECRET_KEY": "sk_test_unused", "FULL_DIR": str(ROOT / "private" / "bundle"),
           "PATH": "/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin", "HANDLER": str(ROOT / "site" / "api" / "data.js"), "PW": pw or ""}
    out = subprocess.run(["node", "-e", DRIVER],
                         capture_output=True, text=True, env=env, cwd=ROOT, timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_no_password_is_401():
    r = call("")
    assert r["status"] == 401 and "password" in r["body"]["error"].lower()


def test_made_up_password_is_401():
    r = call("ABCD-EFGH-JKLM")
    assert r["status"] == 401


def test_comp_password_unlocks_the_full_list():
    r = call(comp_password("comp:test"))
    assert r["status"] == 200 and r["gz"] and r["headers"]["X-Access"] == "comp"
    assert r["headers"]["Content-Encoding"] == "gzip" and r["body"] > 10_000


def test_issue_password_matches_the_handler():
    """scripts/issue_password.py and api/_lib.js must agree on the comp HMAC domain."""
    src = (ROOT / "scripts" / "issue_password.py").read_text()
    lib = (ROOT / "site" / "api" / "_lib.js").read_text()
    assert '"comp:" + nonce' in src and 'mac(nonce, "comp:")' in lib
    assert ALPHA in src and ALPHA in lib


def test_checkout_sells_one_price_from_offer():
    offer = json.loads((ROOT / "site" / "public" / "offer.json").read_text())
    assert offer["product"] == "just-funded" and offer["price_usd"] > 0 and str(offer["price_usd"]) in offer["line"]
    assert "once" in offer["line"]
    co = (ROOT / "site" / "api" / "checkout.js").read_text()
    assert "OFFER.price_usd * 100" in co and '"metadata[product]": PRODUCT' in co
