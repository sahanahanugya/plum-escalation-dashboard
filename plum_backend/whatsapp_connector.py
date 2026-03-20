"""
WhatsApp connector for Plum Escalation Dashboard.
Receives messages via Twilio webhook (POST /webhook/whatsapp).
Also supports polling Twilio message logs if credentials are set.
Falls back gracefully if Twilio credentials are missing.
"""

import uuid
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv(override=True)

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER", "+14155238886")
TWILIO_TARGET_NUMBER = os.getenv("TWILIO_TARGET_NUMBER", "")


def _classify_category(text: str) -> tuple:
    t = text.lower()
    if any(k in t for k in ["escalat", "emergency", "critical", "urgent", "asap", "immediate"]):
        cat = "Escalation"
    elif any(k in t for k in ["complaint", "unhappy", "dissatisfied", "terrible", "unacceptable"]):
        cat = "Complaint"
    elif any(k in t for k in ["follow up", "following up", "reminder", "any update", "still waiting"]):
        cat = "Follow-up"
    elif any(k in t for k in ["thank you", "thanks", "great", "appreciate"]):
        cat = "Appreciation"
    elif any(k in t for k in ["enroll", "new policy", "onboard", "new joiners"]):
        cat = "Initiation"
    else:
        cat = "Query"

    if cat in ("Escalation", "Complaint"):
        p1 = ["emergency", "icu", "critical", "life", "irdai", "legal"]
        priority = "P1" if any(k in t for k in p1) else "P2"
    else:
        priority = "P3"

    return cat, priority


def _assign_owner(category: str, text: str) -> tuple:
    t = text.lower()
    if any(k in t for k in ["cashless", "claim", "reimburs", "icu", "surgery"]):
        return "Ipsita Sahu", "Claims Lead"
    if any(k in t for k in ["irdai", "legal", "compliance"]):
        return "Manashi Goswami", "Compliance Manager"
    if any(k in t for k in ["portal", "login", "app", "tech", "error"]):
        return "Mikhel Dhiman", "Tech Support Lead"
    if category == "Escalation":
        return "Arun Saseedharan", "Senior AM"
    if category == "Complaint":
        return "Vaishnavi Bhat", "Account Manager"
    if category in ("Query", "Initiation"):
        return "Rajorshi Chowdhury", "Junior AM"
    return "Subash P", "Customer Success"


def parse_twilio_webhook(form_data: dict) -> dict | None:
    """
    Parses an incoming Twilio webhook payload into an Escalation dict.
    Called by FastAPI POST /webhook/whatsapp.
    """
    body = form_data.get("Body", "").strip()
    from_number = form_data.get("From", "")
    profile_name = form_data.get("ProfileName", from_number)

    if not body:
        return None

    category, priority = _classify_category(body)
    owner, role = _assign_owner(category, body)

    return {
        "id": str(uuid.uuid4()),
        "source": "whatsapp",
        "sender_name": profile_name,
        "sender_email": from_number,
        "company": "WhatsApp User",
        "subject": body[:120],
        "body": body,
        "category": category,
        "priority": priority,
        "status": "open",
        "assigned_to": owner,
        "assigned_role": role,
        "channel": None,
        "thread_ts": None,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "is_live": True,
    }


def fetch_whatsapp_messages(lookback_hours: int = 48) -> list:
    """
    Polls Twilio API for recent WhatsApp messages to TWILIO_TARGET_NUMBER.
    Returns a list of dicts ready for DB insertion.
    """
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
        print("[WhatsApp] No Twilio credentials — skipping live fetch.")
        return []

    try:
        from twilio.rest import Client
    except ImportError:
        print("[WhatsApp] twilio not installed. Run: pip install twilio")
        return []

    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    records = []

    since = datetime.utcnow() - timedelta(hours=lookback_hours)

    try:
        whatsapp_from = f"whatsapp:{TWILIO_WHATSAPP_NUMBER}"
        messages = client.messages.list(
            to=whatsapp_from,
            date_sent_after=since,
            limit=200,
        )
        print(f"[WhatsApp] Found {len(messages)} messages")

        for msg in messages:
            if not msg.body:
                continue

            # Filter by target number if set
            if TWILIO_TARGET_NUMBER and TWILIO_TARGET_NUMBER not in msg.from_:
                continue

            category, priority = _classify_category(msg.body)
            owner, role = _assign_owner(category, msg.body)
            from_num = msg.from_.replace("whatsapp:", "")

            records.append({
                "id": str(uuid.uuid4()),
                "source": "whatsapp",
                "sender_name": from_num,
                "sender_email": from_num,
                "company": "WhatsApp User",
                "subject": msg.body[:120],
                "body": msg.body,
                "category": category,
                "priority": priority,
                "status": "open",
                "assigned_to": owner,
                "assigned_role": role,
                "channel": None,
                "thread_ts": msg.sid,
                "created_at": msg.date_sent or datetime.utcnow(),
                "updated_at": msg.date_sent or datetime.utcnow(),
                "is_live": True,
            })

    except Exception as e:
        print(f"[WhatsApp] Error fetching messages: {e}")

    print(f"[WhatsApp] Parsed {len(records)} messages.")
    return records


if __name__ == "__main__":
    print("Testing WhatsApp connector...")
    print(f"SID    : {'SET' if TWILIO_ACCOUNT_SID else 'NOT SET'}")
    print(f"Token  : {'SET' if TWILIO_AUTH_TOKEN else 'NOT SET'}")
    print(f"WA Num : {TWILIO_WHATSAPP_NUMBER}")
    msgs = fetch_whatsapp_messages()
    print(f"Fetched {len(msgs)} messages.")
