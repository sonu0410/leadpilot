# LeadPilot — AI Lead Generation & Follow-Up

Captures leads from a form, uses an LLM to **score, categorize, and summarize**
each one, drafts a **personalized follow-up email**, shows everything in a
CRM-style dashboard, and **pings you on Telegram** for hot leads.

```
Lead fills the form
   → AI scores it (0-100) + category (Hot/Warm/Cold) + summary + follow-up email
   → stored and shown on the dashboard
   → Hot lead → instant Telegram alert
```

## Why this design
- **AI qualification:** no more guessing which lead to chase — each is scored.
- **Follow-up drafted for you:** reply in one click instead of writing from scratch.
- **Human in control:** you review and send; the AI drafts, it doesn't auto-send.
- **No training:** it uses an LLM via API; nothing to train.

## Tech
- **Python + FastAPI** backend
- **Groq (LLM)** for scoring, categorizing and email drafting (optional — falls
  back to a rule-based score with no key)
- Plain HTML/CSS/JS for the capture form and CRM dashboard
- **Telegram** alerts for hot leads

## Run locally
```
python -m venv venv
source venv/Scripts/activate      # Windows (Git Bash); use venv\Scripts\activate on CMD
pip install -r requirements.txt
export GROQ_API_KEY=your_key       # optional, for AI scoring
uvicorn app:app --reload
```
- Capture form: http://localhost:8000
- Dashboard: http://localhost:8000/dashboard

## Environment variables
- `GROQ_API_KEY` — enables AI scoring & email drafting (from console.groq.com)
- `GROQ_MODEL` — defaults to `openai/gpt-oss-20b`
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` — optional, for hot-lead alerts

## Note on data
Leads are stored in `leads.jsonl`. On a free host (Render) the disk is
ephemeral, so data resets on redeploy — the data layer is isolated, so moving
to a persistent database (Supabase/Postgres) is a small change.

## Endpoints
- `POST /api/lead` — submit a lead → `{ok, category, score}`
- `GET  /api/leads` — all leads
- `GET  /api/stats` — KPIs, sources, category counts
- `GET  /health`
