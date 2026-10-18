"""
LeadPilot backend (FastAPI)
---------------------------
- Public lead-capture form posts to /api/lead.
- Each lead is scored & categorized by the AI engine, a follow-up email is
  drafted, and it's stored.
- Hot leads trigger an instant Telegram alert (if configured).
- A CRM-style dashboard reads /api/leads and /api/stats.
"""

import os
import json
import uuid
import datetime
import requests
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

import engine

HERE = os.path.dirname(__file__)
LEADS = os.path.join(HERE, "leads.jsonl")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

app = FastAPI(title="LeadPilot")


def read_leads():
    items = []
    if os.path.exists(LEADS):
        for line in open(LEADS, encoding="utf-8"):
            line = line.strip()
            if line:
                try:
                    items.append(json.loads(line))
                except Exception:
                    pass
    return items


def notify_hot(lead):
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        return
    text = (f"🔥 New HOT lead (score {lead['score']})\n\n"
            f"{lead['name']} · {lead.get('company') or '—'}\n"
            f"{lead['email']}\n\n“{lead['summary']}”")
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text}, timeout=10,
        )
    except Exception as e:
        print("Telegram error:", e)


@app.post("/api/lead")
async def new_lead(request: Request):
    body = await request.json()
    lead = {
        "name": (body.get("name") or "").strip(),
        "email": (body.get("email") or "").strip(),
        "company": (body.get("company") or "").strip(),
        "budget": (body.get("budget") or "").strip(),
        "message": (body.get("message") or "").strip(),
        "source": (body.get("source") or "Website").strip(),
    }
    if not lead["name"] or not lead["message"]:
        return JSONResponse({"error": "Name and message are required."}, status_code=400)

    q = engine.qualify(lead)
    lead.update(q)
    lead["id"] = uuid.uuid4().hex[:8]
    lead["time"] = datetime.datetime.now().isoformat(timespec="seconds")
    lead["status"] = "New"

    with open(LEADS, "a", encoding="utf-8") as f:
        f.write(json.dumps(lead, ensure_ascii=False) + "\n")

    if lead["category"] == "Hot":
        notify_hot(lead)

    return JSONResponse({"ok": True, "category": lead["category"], "score": lead["score"]})


@app.get("/api/leads")
async def leads():
    return JSONResponse({"leads": list(reversed(read_leads()))})


@app.get("/api/stats")
async def stats():
    items = read_leads()
    total = len(items)
    today = datetime.date.today().isoformat()
    cats = {"Hot": 0, "Warm": 0, "Cold": 0}
    sources, new_today, score_sum = {}, 0, 0
    for i in items:
        c = i.get("category", "Cold")
        cats[c] = cats.get(c, 0) + 1
        s = i.get("source") or "Website"
        sources[s] = sources.get(s, 0) + 1
        if (i.get("time") or "")[:10] == today:
            new_today += 1
        score_sum += i.get("score", 0)
    qualified = cats["Hot"] + cats["Warm"]
    return JSONResponse({
        "total": total, "new_today": new_today,
        "hot": cats["Hot"], "warm": cats["Warm"], "cold": cats["Cold"],
        "qualified": qualified,
        "qualified_rate": round(qualified / total * 100) if total else 0,
        "avg_score": round(score_sum / total) if total else 0,
        "sources": sources,
        "ai": bool(engine.GROQ_API_KEY),
    })


@app.get("/health")
async def health():
    return {"ok": True, "leads": len(read_leads()), "ai": bool(engine.GROQ_API_KEY)}


@app.get("/dashboard")
async def dashboard():
    return FileResponse(os.path.join(HERE, "public", "dashboard.html"))


app.mount("/", StaticFiles(directory=os.path.join(HERE, "public"), html=True), name="static")
