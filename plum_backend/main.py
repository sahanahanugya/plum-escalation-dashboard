"""
Plum Escalation Dashboard — FastAPI Backend
Endpoints:
  GET  /                        → health check
  GET  /api/stats               → summary counts
  GET  /api/escalations         → paginated list with filters
  GET  /api/escalations/{id}    → single record
  PUT  /api/escalations/{id}    → update status/owner
  POST /api/sync                → pull fresh data from all sources
  POST /api/ai/pipeline         → run Claude AI on all P1 escalations
  POST /api/ai/summarise/{id}   → AI summary + reply draft for one record
  GET  /api/sources/status      → live vs mock status per source
  POST /webhook/whatsapp        → Twilio webhook for live WhatsApp
"""

import os
import uuid
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv

load_dotenv(override=True)

from fastapi import FastAPI, HTTPException, Query, Depends, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import Escalation, get_db, init_db, SessionLocal
from mock_sources import generate_mock_records
from gmail_imap_connector import fetch_gmail_messages
from slack_connector import fetch_slack_messages
from whatsapp_connector import fetch_whatsapp_messages, parse_twilio_webhook

# ──────────────────────────────────────────────
# App setup
# ──────────────────────────────────────────────

app = FastAPI(title="Plum Escalation Dashboard API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
PORT = int(os.getenv("PORT", "8000"))

# ──────────────────────────────────────────────
# Startup: init DB and seed if empty
# ──────────────────────────────────────────────

@app.on_event("startup")
def startup_event():
    init_db()
    db = SessionLocal()
    try:
        count = db.query(Escalation).count()
        if count == 0:
            print("[Startup] Seeding 1200 mock records...")
            records = generate_mock_records(1200)
            db.add_all(records)
            db.commit()
            print(f"[Startup] Seeded {len(records)} records.")
        else:
            print(f"[Startup] DB has {count} records — skip seed.")
    finally:
        db.close()


# ──────────────────────────────────────────────
# Pydantic models
# ──────────────────────────────────────────────

class EscalationUpdate(BaseModel):
    status: Optional[str] = None
    assigned_to: Optional[str] = None
    assigned_role: Optional[str] = None


class EscalationOut(BaseModel):
    id: str
    source: str
    sender_name: str
    sender_email: str
    company: str
    subject: str
    body: str
    category: str
    priority: str
    status: str
    assigned_to: Optional[str]
    assigned_role: Optional[str]
    ai_summary: Optional[str]
    ai_reply_draft: Optional[str]
    channel: Optional[str]
    thread_ts: Optional[str]
    created_at: datetime
    updated_at: datetime
    is_live: bool

    class Config:
        from_attributes = True


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _esc_to_dict(e: Escalation) -> dict:
    return {
        "id": e.id,
        "source": e.source,
        "sender_name": e.sender_name,
        "sender_email": e.sender_email,
        "company": e.company,
        "subject": e.subject,
        "body": e.body,
        "category": e.category,
        "priority": e.priority,
        "status": e.status,
        "assigned_to": e.assigned_to,
        "assigned_role": e.assigned_role,
        "ai_summary": e.ai_summary,
        "ai_reply_draft": e.ai_reply_draft,
        "channel": e.channel,
        "thread_ts": e.thread_ts,
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "updated_at": e.updated_at.isoformat() if e.updated_at else None,
        "is_live": e.is_live,
    }


def _upsert_records(db: Session, records: list) -> int:
    """Insert new records, skip duplicates by thread_ts+source or id."""
    added = 0
    for r in records:
        existing = db.query(Escalation).filter(Escalation.id == r["id"]).first()
        if not existing:
            esc = Escalation(**r)
            db.add(esc)
            added += 1
    db.commit()
    return added


async def _call_claude(prompt: str) -> str:
    if not ANTHROPIC_API_KEY:
        return "[Claude API key not configured — add ANTHROPIC_API_KEY to .env]"
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text
    except Exception as e:
        return f"[Claude error: {e}]"


# ──────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────

@app.get("/")
def health_check():
    return {
        "status": "ok",
        "service": "Plum Escalation Dashboard API",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/api/stats")
def get_stats(db: Session = Depends(get_db)):
    total = db.query(Escalation).count()
    by_category = {}
    by_priority = {}
    by_status = {}
    by_source = {}

    for cat in ["Escalation", "Complaint", "Follow-up", "Query", "Initiation", "Appreciation"]:
        by_category[cat] = db.query(Escalation).filter(Escalation.category == cat).count()
    for pri in ["P1", "P2", "P3"]:
        by_priority[pri] = db.query(Escalation).filter(Escalation.priority == pri).count()
    for st in ["open", "in-progress", "resolved"]:
        by_status[st] = db.query(Escalation).filter(Escalation.status == st).count()
    for src in ["email", "slack", "whatsapp"]:
        by_source[src] = db.query(Escalation).filter(Escalation.source == src).count()

    p1_open = db.query(Escalation).filter(
        Escalation.priority == "P1",
        Escalation.status != "resolved"
    ).count()

    team_members = [
        "Ipsita Sahu", "Manashi Goswami", "Mikhel Dhiman", "Arun Saseedharan",
        "Vaishnavi Bhat", "Rajorshi Chowdhury", "Subash P", "Deepika Nair",
    ]
    by_assignee = {}
    for member in team_members:
        by_assignee[member] = {
            "total": db.query(Escalation).filter(Escalation.assigned_to == member).count(),
            "open": db.query(Escalation).filter(Escalation.assigned_to == member, Escalation.status == "open").count(),
            "in_progress": db.query(Escalation).filter(Escalation.assigned_to == member, Escalation.status == "in-progress").count(),
            "resolved": db.query(Escalation).filter(Escalation.assigned_to == member, Escalation.status == "resolved").count(),
            "p1": db.query(Escalation).filter(Escalation.assigned_to == member, Escalation.priority == "P1").count(),
        }

    return {
        "total": total,
        "p1_open": p1_open,
        "by_category": by_category,
        "by_priority": by_priority,
        "by_status": by_status,
        "by_source": by_source,
        "by_assignee": by_assignee,
    }


@app.get("/api/escalations")
def list_escalations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    source: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    assigned_to: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    sort_by: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    from sqlalchemy import case
    q = db.query(Escalation)
    if source:
        q = q.filter(Escalation.source == source)
    if category:
        q = q.filter(Escalation.category == category)
    if priority:
        q = q.filter(Escalation.priority == priority)
    if status:
        q = q.filter(Escalation.status == status)
    if assigned_to:
        q = q.filter(Escalation.assigned_to == assigned_to)
    if search:
        like = f"%{search}%"
        q = q.filter(
            (Escalation.subject.ilike(like)) |
            (Escalation.body.ilike(like)) |
            (Escalation.sender_name.ilike(like)) |
            (Escalation.company.ilike(like))
        )

    total = q.count()

    if sort_by == "category":
        order_col = case(
            (Escalation.category == "Escalation", 1),
            (Escalation.category == "Complaint", 2),
            (Escalation.category == "Follow-up", 3),
            (Escalation.category == "Query", 4),
            (Escalation.category == "Initiation", 5),
            (Escalation.category == "Appreciation", 6),
            else_=7
        )
    elif sort_by == "priority":
        order_col = case(
            (Escalation.priority == "P1", 1),
            (Escalation.priority == "P2", 2),
            (Escalation.priority == "P3", 3),
            else_=4
        )
    else:
        order_col = Escalation.created_at.desc()

    items = (
        q.order_by(order_col)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
        "items": [_esc_to_dict(e) for e in items],
    }


@app.get("/api/escalations/{esc_id}")
def get_escalation(esc_id: str, db: Session = Depends(get_db)):
    e = db.query(Escalation).filter(Escalation.id == esc_id).first()
    if not e:
        raise HTTPException(status_code=404, detail="Escalation not found")
    return _esc_to_dict(e)


@app.put("/api/escalations/{esc_id}")
def update_escalation(esc_id: str, data: EscalationUpdate, db: Session = Depends(get_db)):
    e = db.query(Escalation).filter(Escalation.id == esc_id).first()
    if not e:
        raise HTTPException(status_code=404, detail="Escalation not found")
    if data.status is not None:
        e.status = data.status
    if data.assigned_to is not None:
        e.assigned_to = data.assigned_to
    if data.assigned_role is not None:
        e.assigned_role = data.assigned_role
    e.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(e)
    return _esc_to_dict(e)


@app.post("/api/sync")
def sync_sources(db: Session = Depends(get_db)):
    results = {"gmail": 0, "slack": 0, "whatsapp": 0, "errors": []}

    try:
        gmail_recs = fetch_gmail_messages()
        results["gmail"] = _upsert_records(db, gmail_recs)
    except Exception as e:
        results["errors"].append(f"Gmail: {e}")

    try:
        slack_recs = fetch_slack_messages()
        results["slack"] = _upsert_records(db, slack_recs)
    except Exception as e:
        results["errors"].append(f"Slack: {e}")

    try:
        wa_recs = fetch_whatsapp_messages()
        results["whatsapp"] = _upsert_records(db, wa_recs)
    except Exception as e:
        results["errors"].append(f"WhatsApp: {e}")

    results["total_added"] = results["gmail"] + results["slack"] + results["whatsapp"]
    return results


@app.post("/api/ai/pipeline")
async def run_ai_pipeline(db: Session = Depends(get_db)):
    """Run Claude AI summarisation on all P1 escalations that don't have a summary yet."""
    p1_pending = (
        db.query(Escalation)
        .filter(Escalation.priority == "P1", Escalation.ai_summary == None)
        .limit(20)
        .all()
    )

    processed = []
    for e in p1_pending:
        prompt = f"""You are a health insurance escalation analyst for Plum, a B2B health insurance platform.

Analyse this escalation message and provide:
1. A concise 2-3 sentence summary of the issue
2. Key action items (bullet points)
3. A professional reply draft

Message details:
From: {e.sender_name} ({e.company})
Subject: {e.subject}
Body: {e.body}

Format your response as:
SUMMARY:
[2-3 sentence summary]

ACTION ITEMS:
- [item 1]
- [item 2]

REPLY DRAFT:
[professional reply]"""

        response = await _call_claude(prompt)

        # Parse sections
        summary = ""
        reply = ""
        if "SUMMARY:" in response:
            parts = response.split("REPLY DRAFT:")
            summary = parts[0].replace("SUMMARY:", "").strip()
            if "ACTION ITEMS:" in summary:
                summary = summary.split("ACTION ITEMS:")[0].strip()
            reply = parts[1].strip() if len(parts) > 1 else ""

        e.ai_summary = summary or response[:500]
        e.ai_reply_draft = reply or ""
        e.updated_at = datetime.utcnow()
        processed.append(e.id)

    db.commit()
    return {"processed": len(processed), "ids": processed}


@app.post("/api/ai/summarise/{esc_id}")
async def summarise_one(esc_id: str, db: Session = Depends(get_db)):
    e = db.query(Escalation).filter(Escalation.id == esc_id).first()
    if not e:
        raise HTTPException(status_code=404, detail="Escalation not found")

    prompt = f"""You are a health insurance escalation analyst for Plum, a B2B health insurance platform.

Analyse this message and provide:
1. A concise 2-3 sentence summary
2. A professional, empathetic reply draft

From: {e.sender_name} ({e.company})
Subject: {e.subject}
Body: {e.body}
Category: {e.category} | Priority: {e.priority}

Format:
SUMMARY:
[summary here]

REPLY DRAFT:
[reply here]"""

    response = await _call_claude(prompt)

    summary = ""
    reply = ""
    if "SUMMARY:" in response and "REPLY DRAFT:" in response:
        parts = response.split("REPLY DRAFT:")
        summary = parts[0].replace("SUMMARY:", "").strip()
        reply = parts[1].strip()
    else:
        summary = response[:500]

    e.ai_summary = summary
    e.ai_reply_draft = reply
    e.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(e)
    return _esc_to_dict(e)


@app.get("/api/sources/status")
def sources_status():
    gmail_live = bool(os.getenv("GMAIL_ADDRESS") and os.getenv("GMAIL_APP_PASSWORD"))
    slack_live = bool(os.getenv("SLACK_BOT_TOKEN", "").startswith("xoxb-"))
    wa_live = bool(os.getenv("TWILIO_ACCOUNT_SID") and os.getenv("TWILIO_AUTH_TOKEN"))
    ai_live = bool(os.getenv("ANTHROPIC_API_KEY"))

    return {
        "gmail": {"connected": gmail_live, "mode": "live" if gmail_live else "mock"},
        "slack": {"connected": slack_live, "mode": "live" if slack_live else "mock"},
        "whatsapp": {"connected": wa_live, "mode": "live" if wa_live else "mock"},
        "ai": {"connected": ai_live, "mode": "live" if ai_live else "mock"},
    }


@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request, db: Session = Depends(get_db)):
    """Twilio webhook — receives live WhatsApp messages."""
    form_data = dict(await request.form())
    record = parse_twilio_webhook(form_data)
    if record:
        esc = Escalation(**record)
        db.add(esc)
        db.commit()
        print(f"[Webhook] New WhatsApp message from {record['sender_name']}: {record['subject'][:60]}")
        # Respond with empty TwiML so Twilio doesn't retry
        return JSONResponse(
            content={"status": "ok", "id": record["id"]},
            headers={"Content-Type": "application/json"},
        )
    return JSONResponse(content={"status": "ignored"})


# ──────────────────────────────────────────────
# Run
# ──────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    host = os.getenv("HOST", "0.0.0.0")
    uvicorn.run("main:app", host=host, port=PORT, reload=True)
