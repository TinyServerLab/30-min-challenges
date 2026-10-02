"""End-to-end API smoke test.  python scripts/smoke_test.py http://localhost:8000/inventory email password"""
import io
import sys
from datetime import date, timedelta

import httpx
from PIL import Image, ImageDraw, ImageFont

base, email, pw = sys.argv[1].rstrip("/"), sys.argv[2], sys.argv[3]
H = {"X-Requested-With": "fetch"}
c = httpx.Client(base_url=base, headers=H, follow_redirects=False, timeout=120)


def ok(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        sys.exit(1)


# ---- auth
ok(c.get("/api/assets").status_code == 401, "unauthenticated API is blocked")
ok(httpx.post(base + "/api/auth/login", json={"login": email, "password": pw}).status_code == 403,
   "POST without X-Requested-With is rejected (CSRF guard)")
ok(c.post("/api/auth/login", json={"login": email, "password": "wrong"}).status_code == 401, "bad password rejected")
r = c.post("/api/auth/login", json={"login": email.upper(), "password": pw})
ok(r.status_code == 200, "login ok (case-insensitive email)")
sc = r.headers["set-cookie"]
ok("HttpOnly" in sc and "Path=/inventory" in sc and "SameSite=lax" in sc, f"cookie flags: {sc.split(';',1)[1]}")

cats = c.get("/api/categories").json()
ok(len(cats) >= 5, f"{len(cats)} seeded categories")

# ---- invoice upload with OCR
img = Image.new("RGB", (1400, 1000), "white")
d = ImageDraw.Draw(img)
try:
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 30)
except OSError:
    font = ImageFont.load_default()
txt = ["CROMA - Infiniti Retail Ltd", "TAX INVOICE", "GSTIN: 33AABCI1234F1Z5",
       "Invoice No: CRM/24-25/004512", "Invoice Date: 15/08/2025", "",
       "1  Samsung 253L Double Door Refrigerator   1   28,490.00",
       "Model No: RT28C3052S8", "Serial No: R2BX45K9Q", "1 Year manufacturer warranty", "",
       "Sub Total   24,144.07", "CGST 9%  2,172.97", "Grand Total   Rs. 28,490.00"]
for i, t in enumerate(txt):
    d.text((60, 40 + i * 62), t, fill="black", font=font)
buf = io.BytesIO()
img.save(buf, "JPEG", quality=92)
r = c.post("/api/attachments", files={"file": ("invoice.jpg", buf.getvalue(), "image/jpeg")},
           data={"kind": "invoice", "extract": "true"})
ok(r.status_code == 201, f"upload invoice ({r.status_code})")
up = r.json()
print("     extracted:", up["extracted"])
att_id = up["attachment"]["id"]
ex = up["extracted"] or {}
ok(ex.get("purchase_price") in ("28490.00", "28490.0", "28490"), "OCR total amount")
ok(ex.get("purchase_date") == "2025-08-15", "OCR invoice date")

ok(c.post("/api/attachments", files={"file": ("x.html", b"<script>alert(1)</script>", "image/jpeg")}
          ).status_code == 415, "non-image/pdf upload rejected by content sniffing")

# ---- create asset
body = {"name": "Samsung 253L Refrigerator", "brand": "Samsung", "model": "RT28C3052S8",
        "category_id": next(x["id"] for x in cats if x["name"] == "Kitchen Appliances"),
        "purchase_date": "2025-08-15", "purchase_price": "28490", "vendor": "Croma",
        "warranty_months": 12, "ext_warranty_provider": "Croma Zip Care", "ext_warranty_months": 24,
        "location": "Kitchen", "attachment_ids": [att_id]}
r = c.post("/api/assets", json=body)
ok(r.status_code == 201, f"create asset ({r.status_code} {r.text[:200]})")
a = r.json()
ok(a["warranty_expiry_date"] == "2026-08-14", f"12-month warranty ends 2026-08-14 (got {a['warranty_expiry_date']})")
ok(a["ext_warranty_expiry_date"] == "2028-08-14", f"extended +24m ends 2028-08-14 (got {a['ext_warranty_expiry_date']})")
ok(a["effective_expiry_date"] == "2028-08-14" and a["warranty_state"] == "active", "effective = extended")
ok(len(a["attachments"]) == 1, "draft invoice linked to asset")

# expiring + expired assets for dashboard
today = date.today()
c.post("/api/assets", json={"name": "Philips Air Fryer", "brand": "Philips", "purchase_date": str(today - timedelta(days=350)),
                            "purchase_price": "7999", "warranty_months": 12, "vendor": "Amazon",
                            "category_id": body["category_id"]})
c.post("/api/assets", json={"name": "boAt Airdopes", "purchase_date": str(today - timedelta(days=400)),
                            "purchase_price": "1499", "warranty_months": 12, "vendor": "Flipkart"})
c.post("/api/assets", json={"name": "Office chair", "purchase_date": str(today - timedelta(days=20)),
                            "purchase_price": "12500", "warranty_months": 0, "warranty_expiry_manual": True,
                            "warranty_expiry_date": str(today + timedelta(days=5)), "vendor": "IKEA",
                            "category_id": next(x["id"] for x in cats if x["name"] == "Furniture")})

dash = c.get("/api/dashboard").json()
print("     counts:", dash["counts"])
ok(dash["counts"]["expiring_soon"] >= 2 and dash["counts"]["expired"] >= 1, "dashboard buckets")

lst = c.get("/api/assets", params={"warranty": "expiring"}).json()
ok(lst["total"] >= 2, f"filter expiring → {lst['total']}")
ok(c.get("/api/assets", params={"q": "RT28C"}).json()["total"] >= 1, "search by model")

# ---- file access
f = c.get(f"/api/attachments/{att_id}/file")
ok(f.status_code == 200 and f.headers["content-type"] == "image/jpeg", "invoice served to logged-in user")
ok(httpx.get(f"{base}/api/attachments/{att_id}/file").status_code == 401, "invoice blocked without session")
ok(c.get(f"/api/attachments/{att_id}/thumb").status_code == 200, "thumbnail")

# ---- service record + spending
c.post(f"/api/assets/{a['id']}/services", json={"service_date": str(today), "description": "Gas refill",
                                                  "cost": "1200", "under_warranty": False})
sp = c.get("/api/reports/spending", params={"year": 2025}).json()
ok(float(sp["totals"]["purchases"]) >= 28490, f"spending 2025 purchases = {sp['totals']['purchases']}")

csv_r = c.get("/api/assets/export.csv", params={"status": "all"})
ok(csv_r.status_code == 200 and "Samsung" in csv_r.text, "CSV export")

st = c.get("/api/notifications/status").json()
ok(st["due_now"] >= 2, f"reminders due now: {st['due_now']}")

# ---- SPA under base path
html = c.get("/").text
ok('<base href="/inventory/" />' in html, "index.html has <base href=/inventory/>")
ok(c.get("/assets/123").status_code == 200, "deep link served by SPA fallback")
ok(c.get("/api/nope").status_code == 404, "unknown API path → 404 JSON")

ok(c.post("/api/auth/logout").status_code == 204, "logout")
ok(c.get("/api/auth/me").status_code == 401, "session gone after logout")
print("ALL SMOKE TESTS PASSED")
