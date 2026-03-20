"""
Gmail IMAP connector for Plum Escalation Dashboard.
Reads emails using IMAP + App Password (no OAuth needed).
Falls back gracefully if credentials are missing.
"""

import imaplib
import email
import uuid
import os
import re
from email.header import decode_header
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv(override=True)

GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
IMAP_SERVER = "imap.gmail.com"
IMAP_PORT = 993


def _decode_header_value(value: str) -> str:
    if not value:
        return ""
    parts = decode_header(value)
    result = []
    for part, enc in parts:
        if isinstance(part, bytes):
            result.append(part.decode(enc or "utf-8", errors="replace"))
        else:
            result.append(str(part))
    return " ".join(result)


def _get_body(msg) -> str:
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            cd = str(part.get("Content-Disposition", ""))
            if ct == "text/plain" and "attachment" not in cd:
                payload = part.get_payload(decode=True)
                if payload:
                    body = payload.decode(errors="replace")
                    break
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            body = payload.decode(errors="replace")
    return body.strip()


def _classify_category(subject: str, body: str) -> tuple:
    """Returns (category, priority)."""
    text = (subject + " " + body).lower()

    p1_keywords = ["emergency", "critical", "life threatening", "icu", "cashless reject",
                   "irdai complaint", "legal notice"]
    p2_keywords = ["escalat", "urgent", "asap", "complaint", "unhappy", "dissatisfied",
                   "unacceptable", "terrible", "worst", "horrible"]

    if any(k in text for k in ["escalat", "emergency", "critical", "urgent", "immediate"]):
        cat = "Escalation"
    elif any(k in text for k in ["complaint", "unhappy", "dissatisfied", "terrible", "unacceptable"]):
        cat = "Complaint"
    elif any(k in text for k in ["follow up", "following up", "reminder", "still waiting",
                                   "overdue", "2nd reminder", "3rd reminder"]):
        cat = "Follow-up"
    elif any(k in text for k in ["thank you", "thanks", "great", "excellent", "appreciate",
                                   "wonderful", "happy with", "good experience"]):
        cat = "Appreciation"
    elif any(k in text for k in ["new policy", "interested in", "onboarding", "enrollment",
                                   "getting started", "proposal", "new joiners"]):
        cat = "Initiation"
    else:
        cat = "Query"

    if cat in ("Escalation", "Complaint"):
        if any(k in text for k in p1_keywords):
            priority = "P1"
        elif any(k in text for k in p2_keywords):
            priority = "P2"
        else:
            priority = "P2"
    else:
        priority = "P3"

    return cat, priority


def _assign_owner(category: str, subject: str, body: str) -> tuple:
    text = (subject + " " + body).lower()
    if any(k in text for k in ["cashless", "icu", "admitted", "surgery", "claim", "reimburs"]):
        return "Ipsita Sahu", "Claims Lead"
    if any(k in text for k in ["irdai", "legal", "compliance", "regulation"]):
        return "Manashi Goswami", "Compliance Manager"
    if any(k in text for k in ["portal", "tech", "login", "app", "down", "error"]):
        return "Mikhel Dhiman", "Tech Support Lead"
    if category == "Escalation":
        return "Arun Saseedharan", "Senior AM"
    if category == "Complaint":
        return "Vaishnavi Bhat", "Account Manager"
    if category in ("Query", "Initiation"):
        return "Rajorshi Chowdhury", "Junior AM"
    return "Subash P", "Customer Success"


def fetch_gmail_messages(lookback_hours: int = 48) -> list:
    """
    Connects to Gmail via IMAP and returns a list of dicts representing emails.
    Returns empty list if credentials are missing or connection fails.
    """
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        print("[Gmail] No credentials found — skipping live fetch.")
        return []

    records = []
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        mail.select("INBOX")

        since_date = (datetime.now() - timedelta(hours=lookback_hours)).strftime("%d-%b-%Y")
        _, message_numbers = mail.search(None, f'(SINCE "{since_date}")')

        ids = message_numbers[0].split()
        print(f"[Gmail] Found {len(ids)} emails since {since_date}")

        for num in ids[-200:]:  # cap at 200 most recent
            try:
                _, msg_data = mail.fetch(num, "(RFC822)")
                raw = msg_data[0][1]
                msg = email.message_from_bytes(raw)

                subject = _decode_header_value(msg.get("Subject", "(no subject)"))
                from_raw = _decode_header_value(msg.get("From", ""))
                body = _get_body(msg)

                # parse sender name + email
                match = re.match(r"^(.*?)\s*<(.+?)>$", from_raw)
                if match:
                    sender_name = match.group(1).strip().strip('"')
                    sender_email = match.group(2).strip()
                else:
                    sender_name = from_raw
                    sender_email = from_raw

                date_str = msg.get("Date", "")
                try:
                    from email.utils import parsedate_to_datetime
                    created_at = parsedate_to_datetime(date_str).replace(tzinfo=None)
                except Exception:
                    created_at = datetime.utcnow()

                category, priority = _classify_category(subject, body)
                owner, role = _assign_owner(category, subject, body)

                # guess company from sender email domain
                domain = sender_email.split("@")[-1] if "@" in sender_email else "unknown.com"
                company = domain.split(".")[0].capitalize()

                records.append({
                    "id": str(uuid.uuid4()),
                    "source": "email",
                    "sender_name": sender_name or "Unknown",
                    "sender_email": sender_email,
                    "company": company,
                    "subject": subject,
                    "body": body[:4000],  # cap body length
                    "category": category,
                    "priority": priority,
                    "status": "open",
                    "assigned_to": owner,
                    "assigned_role": role,
                    "channel": None,
                    "thread_ts": None,
                    "created_at": created_at,
                    "updated_at": created_at,
                    "is_live": True,
                })
            except Exception as e:
                print(f"[Gmail] Error parsing message {num}: {e}")
                continue

        mail.logout()

    except imaplib.IMAP4.error as e:
        print(f"[Gmail] IMAP auth/connection error: {e}")
    except Exception as e:
        print(f"[Gmail] Unexpected error: {e}")

    print(f"[Gmail] Successfully parsed {len(records)} emails.")
    return records


if __name__ == "__main__":
    msgs = fetch_gmail_messages(lookback_hours=72)
    if msgs:
        print(f"\n--- First message ---")
        print(f"From   : {msgs[0]['sender_name']} <{msgs[0]['sender_email']}>")
        print(f"Subject: {msgs[0]['subject']}")
        print(f"Category: {msgs[0]['category']} | Priority: {msgs[0]['priority']}")
        print(f"Assigned: {msgs[0]['assigned_to']}")
    else:
        print("No messages fetched (check credentials in .env)")
