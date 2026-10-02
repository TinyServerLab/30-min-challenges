"""In-process tests for Discord/Telegram notifications with fake Discord + Telegram servers.

Needs a reachable, freshly bootstrapped database (env vars as for the app), then:
    cd backend && python ../scripts/test_notifications.py
"""
import json
import logging
import sys
from datetime import date, timedelta

import httpx
from fastapi.testclient import TestClient

sys.path.insert(0, ".")
from app import notify  # noqa: E402
from app.main import application  # noqa: E402

TOKEN = "7123456789:AAHfakeTokenForTestsOnly_abcdefghijklmnop"
HOOK = "https://discord.com/api/webhooks/123456789012345678/fakeWebhookToken_ABCDEFGHIJKLMNOPQRSTUVWXYZ"
sent: list[dict] = []


def fake(request: httpx.Request) -> httpx.Response:
    url = str(request.url)
    body = json.loads(request.content or b"{}") if request.headers.get("content-type", "").startswith("application/json") else {}
    sent.append({"url": url, "body": body})
    if request.url.host == "discord.com":
        if "/webhooks/999" in url:
            return httpx.Response(404, json={"message": "Unknown Webhook", "code": 10015})
        return httpx.Response(200, json={"id": "1"})
    if request.url.host == "api.telegram.org":
        if f"/bot{TOKEN}/" not in url:
            return httpx.Response(401, json={"ok": False, "error_code": 401, "description": "Unauthorized"})
        method = url.rsplit("/", 1)[-1]
        if method == "getMe":
            return httpx.Response(200, json={"ok": True, "result": {"id": 7123456789, "username": "HomeInvBot", "first_name": "Home Inventory"}})
        if method == "getUpdates":
            return httpx.Response(200, json={"ok": True, "result": [
                {"update_id": 1, "message": {"chat": {"id": 55501, "type": "private", "first_name": "Sathya", "username": "sathya"}}},
                {"update_id": 2, "my_chat_member": {"chat": {"id": -1001234567890, "type": "supergroup", "title": "Family"}}},
            ]})
        if method == "sendMessage":
            if str(body.get("chat_id")) == "-999":
                return httpx.Response(400, json={"ok": False, "error_code": 400, "description": "Bad Request: chat not found"})
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})
    return httpx.Response(200, text="ok")   # ntfy etc.


notify.http = httpx.Client(transport=httpx.MockTransport(fake))

logs: list[str] = []


class Grab(logging.Handler):
    def emit(self, record):
        logs.append(record.getMessage())


logging.getLogger().addHandler(Grab(level=logging.DEBUG))
logging.getLogger().setLevel(logging.DEBUG)
logging.getLogger("httpx").setLevel(logging.WARNING)   # what notify does; asserted below anyway

failures = 0


def ok(cond, msg):
    global failures
    print(("PASS " if cond else "FAIL ") + msg)
    failures += 0 if cond else 1


H = {"X-Requested-With": "fetch"}
B = "/inventory/api"

with TestClient(application, base_url="http://testserver") as c:
    c.headers.update(H)
    r = c.post(f"{B}/auth/login", json={"login": "sathya@example.com", "password": "Admin#Pass123"})
    assert r.status_code == 200, r.text

    ch = {x["channel"]: x for x in c.get(f"{B}/notifications/channels").json()}
    ok(list(ch) == ["email", "ntfy", "discord", "telegram"], "4 channels listed")
    ok(not ch["discord"]["enabled"] and ch["discord"]["problem"], "discord off + needs setup by default")

    r = c.put(f"{B}/notifications/channels/discord", json={"enabled": True})
    ok(r.status_code == 400 and "webhook" in r.json()["detail"].lower(), "can't enable discord without URL")
    r = c.put(f"{B}/notifications/channels/discord", json={"config": {"webhook_url": "https://evil.example.com/x"}})
    ok(r.status_code == 400, "non-Discord URL rejected (no SSRF)")

    r = c.put(f"{B}/notifications/channels/discord", json={"enabled": True, "config": {"webhook_url": HOOK}})
    d = r.json()
    ok(r.status_code == 200 and d["enabled"], "discord saved + enabled")
    ok(HOOK not in r.text and "••••" in d["config"]["webhook_url"], f"webhook masked: {d['config']['webhook_url']}")
    r = c.put(f"{B}/notifications/channels/discord", json={"config": {"webhook_url": d["config"]["webhook_url"]}})
    ok(r.status_code == 200 and r.json()["enabled"], "masked value echoed back keeps the secret")
    r = c.put(f"{B}/notifications/channels/discord", json={"config": {"mention": "@everybody"}})
    ok(r.status_code == 400, "invalid mention rejected")

    sent.clear()
    r = c.post(f"{B}/notifications/channels/discord/test").json()
    ok(r["ok"], f"discord test: {r['detail']}")
    p = sent[-1]["body"]
    ok(p["embeds"][0]["title"].startswith("Home Inventory") and p["allowed_mentions"] == {"parse": []},
       "discord payload: embed + mentions disabled")

    # ---- telegram
    r = c.post(f"{B}/notifications/telegram/chats", json={"bot_token": "123:bad"})
    ok(r.status_code == 400, "bad token format rejected")
    r = c.post(f"{B}/notifications/telegram/chats", json={"bot_token": TOKEN}).json()
    ok(r["bot"]["username"] == "HomeInvBot" and len(r["chats"]) == 2, f"chat discovery: {[x['title'] for x in r['chats']]}")
    fam = next(x for x in r["chats"] if x["title"] == "Family")
    r = c.put(f"{B}/notifications/channels/telegram",
              json={"enabled": True, "config": {"bot_token": TOKEN, "chat_id": fam["id"], "chat_title": "Family"}})
    ok(r.status_code == 200 and TOKEN not in r.text, f"telegram saved, token masked: {r.json()['config']['bot_token']}")
    r = c.post(f"{B}/notifications/telegram/chats", json={}).json()
    ok(len(r["chats"]) == 2, "chat discovery reuses saved token")

    sent.clear()
    r = c.post(f"{B}/notifications/channels/telegram/test").json()
    ok(r["ok"], f"telegram test: {r['detail']}")
    body = sent[-1]["body"]
    ok(body["parse_mode"] == "HTML" and body["chat_id"] == "-1001234567890" and "<b>" in body["text"], "telegram payload")

    c.put(f"{B}/notifications/channels/telegram", json={"config": {"chat_id": "-999"}})
    r = c.post(f"{B}/notifications/channels/telegram/test").json()
    ok(not r["ok"] and "send any message to the bot" in r["detail"], f"helpful error: {r['detail']}")
    t = next(x for x in c.get(f"{B}/notifications/channels").json() if x["channel"] == "telegram")
    ok(t["last_ok"] is False and "chat not found" in t["last_error"], "last error recorded for UI")
    c.put(f"{B}/notifications/channels/telegram", json={"config": {"chat_id": fam["id"]}})

    # ---- real reminder run, with hostile names
    cat = c.get(f"{B}/categories").json()[0]["id"]
    soon = date.today() - timedelta(days=365) + timedelta(days=3)     # 12-month warranty ending in ~3 days
    c.post(f"{B}/assets", json={"name": "@everyone <b>Fridge</b> & co", "brand": "LG", "category_id": cat,
                                "purchase_date": str(soon), "purchase_price": "100", "warranty_months": 12})
    sent.clear()
    r = c.post(f"{B}/notifications/run").json()
    ok(r["sent"].get("discord", 0) >= 1 and r["sent"].get("telegram", 0) >= 1 and not r["errors"], f"run: {r}")
    dpay = next(s["body"] for s in sent if "discord.com" in s["url"])
    tpay = next(s["body"] for s in sent if "sendMessage" in s["url"])
    ok(dpay["allowed_mentions"] == {"parse": []} and "content" not in dpay, "discord: no pings from asset names")
    ok("&lt;b&gt;Fridge&lt;/b&gt; &amp; co" in tpay["text"] and "<b>Fridge" not in tpay["text"], "telegram: names HTML-escaped")
    ok(dpay["embeds"][0]["color"] == 0xE34948, "discord: urgent (≤7 days) shown red")
    r = c.post(f"{B}/notifications/run").json()
    ok(r["sent"].get("discord") == 0 and r["sent"].get("telegram") == 0, "second run sends nothing (dedupe)")

    c.put(f"{B}/notifications/channels/discord", json={"config": {"mention": "@here"}})
    c.post(f"{B}/assets", json={"name": "Mixer", "category_id": cat, "purchase_date": str(soon),
                                "purchase_price": "10", "warranty_months": 12})
    sent.clear()
    c.post(f"{B}/notifications/run")
    dpay = next(s["body"] for s in sent if "discord.com" in s["url"])
    ok(dpay.get("content") == "@here" and "everyone" in dpay["allowed_mentions"]["parse"], "configured @here mention used")

    # ---- toggle off
    c.put(f"{B}/notifications/channels/discord", json={"enabled": False})
    c.post(f"{B}/assets", json={"name": "Kettle", "category_id": cat, "purchase_date": str(soon),
                                "purchase_price": "10", "warranty_months": 12})
    sent.clear()
    r = c.post(f"{B}/notifications/run").json()
    ok("discord" not in r["sent"] and not any("discord.com" in s["url"] for s in sent), "switched-off channel sends nothing")
    st = c.get(f"{B}/notifications/status").json()
    ok("discord" not in st["channels"] and "telegram" in st["channels"], f"status channels: {st['channels']}")

    # ---- long digest splits under Telegram's 4096 limit
    big = notify.Message(title="T", lines=[notify.Line(label="Item %d " % i + "x" * 80, detail="ends soon",
                                                        url="https://home.tinyserverlab.in/inventory/assets/1")
                                           for i in range(80)])
    sent.clear()
    notify.send_telegram({"bot_token": TOKEN, "chat_id": "1"}, big)
    ok(len(sent) > 1 and all(len(s["body"]["text"]) <= 4096 for s in sent), f"80 items → {len(sent)} Telegram messages")
    sent.clear()
    notify.send_discord({"webhook_url": HOOK}, big)
    ok(all(len(s["body"]["embeds"][0]["description"]) <= 4096 for s in sent), f"80 items → {len(sent)} Discord messages")

    # ---- non-admin
    c.post(f"{B}/users", json={"email": "kid@example.com", "display_name": "Kid", "password": "Kid#Pass2026x"})
    k = TestClient(application, base_url="http://testserver")
    k.headers.update(H)
    k.post(f"{B}/auth/login", json={"login": "kid@example.com", "password": "Kid#Pass2026x"})
    kc = k.get(f"{B}/notifications/channels").json()
    ok(all("config" not in x and x["last_error"] is None for x in kc), "non-admin sees no secrets / errors")
    ok(k.put(f"{B}/notifications/channels/discord", json={"enabled": True}).status_code == 403, "non-admin can't change")

    # ---- clearing settings switches channel off
    r = c.put(f"{B}/notifications/channels/telegram", json={"config": {"bot_token": ""}}).json()
    ok(not r["enabled"] and r["problem"], "clearing the token switches Telegram off")

ok(not any(TOKEN in m or "fakeWebhookToken" in m for m in logs), f"no secrets in {len(logs)} log lines")
print("ALL NOTIFICATION TESTS PASSED" if not failures else f"{failures} FAILED")
sys.exit(1 if failures else 0)
