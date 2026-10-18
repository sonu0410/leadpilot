"""
LeadPilot engine
----------------
Takes a raw lead (from the capture form) and, using an LLM (Groq), returns:
  - a score 0-100 (how likely/valuable this lead is)
  - a category: Hot / Warm / Cold
  - a one-line summary of what they want
  - a personalized follow-up email draft

If no Groq key is set, it falls back to a simple rule-based score so the app
still works for demos.
"""

import os
import re
import json
import requests

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")

# Budget text -> a rough weight, used by the fallback scorer.
BUDGET_WEIGHT = {
    "under ₹10,000": 10, "₹10,000 – ₹25,000": 30, "₹25,000 – ₹50,000": 55,
    "₹50,000+": 80, "not sure yet": 20, "": 15,
}


def _fallback(lead):
    """Simple score when there's no LLM: budget + message detail + company."""
    score = BUDGET_WEIGHT.get((lead.get("budget") or "").lower(), 15)
    msg = (lead.get("message") or "")
    if len(msg) > 120:
        score += 15
    elif len(msg) > 40:
        score += 8
    if lead.get("company"):
        score += 8
    if re.search(r"urgent|asap|ready|soon|this week|budget|hire|start", msg, re.I):
        score += 12
    score = max(5, min(score, 95))
    category = "Hot" if score >= 65 else "Warm" if score >= 40 else "Cold"
    name = lead.get("name") or "there"
    summary = (msg[:90] + "…") if len(msg) > 90 else (msg or "No details provided.")
    email = (
        f"Hi {name},\n\nThanks for reaching out! I'd love to learn more about "
        f"{('your project at ' + lead['company']) if lead.get('company') else 'your project'}. "
        "Could we set up a quick 15-minute call this week to go over what you need?\n\n"
        "Best,\nMohit"
    )
    return {"score": score, "category": category, "summary": summary, "followup_email": email}


PROMPT = """You are a sales assistant. Score and qualify this incoming lead for a freelance developer.

Return ONLY valid JSON with these keys:
- "score": integer 0-100 (how valuable and ready-to-buy this lead is; consider budget, clarity, urgency, fit)
- "category": one of "Hot", "Warm", "Cold" (Hot = high score/ready, Cold = low/vague)
- "summary": one short sentence describing what they want
- "followup_email": a short, friendly, personalized follow-up email (3-5 sentences, sign off as "Mohit")

LEAD:
name: {name}
email: {email}
company: {company}
budget: {budget}
message: {message}
"""


def qualify(lead):
    if not GROQ_API_KEY:
        return _fallback(lead)
    prompt = PROMPT.format(
        name=lead.get("name", ""), email=lead.get("email", ""),
        company=lead.get("company", ""), budget=lead.get("budget", ""),
        message=lead.get("message", ""),
    )
    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={"model": GROQ_MODEL,
                  "messages": [{"role": "user", "content": prompt}],
                  "temperature": 0.3, "max_tokens": 400,
                  "response_format": {"type": "json_object"}},
            timeout=20,
        )
        r.raise_for_status()
        raw = r.json()["choices"][0]["message"]["content"]
        out = json.loads(raw)
        score = int(max(0, min(100, out.get("score", 0))))
        cat = out.get("category") or ("Hot" if score >= 65 else "Warm" if score >= 40 else "Cold")
        return {
            "score": score,
            "category": cat,
            "summary": str(out.get("summary", ""))[:160],
            "followup_email": str(out.get("followup_email", "")),
        }
    except Exception as e:
        print("Groq error:", e)
        return _fallback(lead)
