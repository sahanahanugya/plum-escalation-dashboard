"""
Slack connector for Plum Escalation Dashboard.
Uses slack-sdk to read messages from specified channels.
Bot must be invited to each channel with channels:history and channels:read scopes.
"""

import uuid
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv(override=True)

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")
SLACK_CHANNELS_ENV = os.getenv("SLACK_CHANNELS", "all-plum-escalation-dashboard,general")
SLACK_LOOKBACK_HOURS = int(os.getenv("SLACK_LOOKBACK_HOURS", "48"))
SLACK_TARGET_USER_ID = os.getenv("SLACK_TARGET_USER_ID", "")

TARGET_CHANNELS = [c.strip() for c in SLACK_CHANNELS_ENV.split(",") if c.strip()]


def _classify_category(text: str) -> tuple:
    t = text.lower()
    if any(k in t for k in ["escalat", "emergency", "critical", "urgent", "immediate", "asap"]):
        cat = "Escalation"
    elif any(k in t for k in ["complaint", "unhappy", "dissatisfied", "terrible", "unacceptable"]):
        cat = "Complaint"
    elif any(k in t for k in ["follow up", "following up", "reminder", "still waiting", "any update"]):
        cat = "Follow-up"
    elif any(k in t for k in ["thank you", "thanks", "great job", "appreciate", "well done"]):
        cat = "Appreciation"
    elif any(k in t for k in ["new joiners", "enroll", "onboard", "add employee", "new policy"]):
        cat = "Initiation"
    else:
        cat = "Query"

    if cat in ("Escalation", "Complaint"):
        p1 = ["emergency", "icu", "life", "critical", "irdai", "legal notice"]
        priority = "P1" if any(k in t for k in p1) else "P2"
    else:
        priority = "P3"

    return cat, priority


def _assign_owner(category: str, text: str) -> tuple:
    t = text.lower()
    if any(k in t for k in ["cashless", "icu", "claim", "reimburs", "surgery"]):
        return "Ipsita Sahu", "Claims Lead"
    if any(k in t for k in ["irdai", "legal", "compliance"]):
        return "Manashi Goswami", "Compliance Manager"
    if any(k in t for k in ["portal", "login", "app", "tech", "bug", "error"]):
        return "Mikhel Dhiman", "Tech Support Lead"
    if category == "Escalation":
        return "Arun Saseedharan", "Senior AM"
    if category == "Complaint":
        return "Vaishnavi Bhat", "Account Manager"
    if category in ("Query", "Initiation"):
        return "Rajorshi Chowdhury", "Junior AM"
    return "Subash P", "Customer Success"


def fetch_slack_messages() -> list:
    """
    Reads messages from configured Slack channels.
    Returns a list of dicts ready for DB insertion.
    """
    if not SLACK_BOT_TOKEN or not SLACK_BOT_TOKEN.startswith("xoxb-"):
        print("[Slack] No valid bot token found — skipping live fetch.")
        return []

    try:
        from slack_sdk import WebClient
        from slack_sdk.errors import SlackApiError
    except ImportError:
        print("[Slack] slack-sdk not installed. Run: pip install slack-sdk")
        return []

    client = WebClient(token=SLACK_BOT_TOKEN)
    records = []

    oldest_ts = str((datetime.utcnow() - timedelta(hours=SLACK_LOOKBACK_HOURS)).timestamp())

    # Resolve channel names → IDs
    channel_map = {}
    try:
        cursor = None
        while True:
            kwargs = {"limit": 200, "types": "public_channel"}  # groups:read not required
            if cursor:
                kwargs["cursor"] = cursor
            resp = client.conversations_list(**kwargs)
            for ch in resp["channels"]:
                channel_map[ch["name"]] = ch["id"]
            cursor = resp.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
        print(f"[Slack] Found {len(channel_map)} channels in workspace.")
    except Exception as e:
        print(f"[Slack] Could not list channels: {e}")
        return []

    # Fetch messages per target channel
    for ch_name in TARGET_CHANNELS:
        ch_id = channel_map.get(ch_name)
        if not ch_id:
            print(f"[Slack] Channel '{ch_name}' not found or bot not invited. Skipping.")
            continue

        try:
            history = client.conversations_history(
                channel=ch_id,
                oldest=oldest_ts,
                limit=200,
            )
            messages = history.get("messages", [])
            print(f"[Slack] #{ch_name}: {len(messages)} messages in last {SLACK_LOOKBACK_HOURS}h")

            for msg in messages:
                # skip bot messages and system messages
                if msg.get("bot_id") or msg.get("subtype"):
                    continue

                text = msg.get("text", "").strip()
                if not text or len(text) < 10:
                    continue

                # Filter by specific user if configured
                if SLACK_TARGET_USER_ID and msg.get("user") != SLACK_TARGET_USER_ID:
                    continue

                # Resolve sender display name
                user_id = msg.get("user", "unknown")
                sender_name = user_id
                sender_email = f"{user_id}@slack.workspace"
                try:
                    user_info = client.users_info(user=user_id)
                    profile = user_info["user"]["profile"]
                    sender_name = profile.get("real_name") or profile.get("display_name") or user_id
                    sender_email = profile.get("email") or sender_email
                except Exception:
                    pass

                ts_float = float(msg.get("ts", 0))
                created_at = datetime.utcfromtimestamp(ts_float)

                category, priority = _classify_category(text)
                owner, role = _assign_owner(category, text)

                # Use first line of text as subject equivalent
                subject = text.split("\n")[0][:120]

                records.append({
                    "id": str(uuid.uuid4()),
                    "source": "slack",
                    "sender_name": sender_name,
                    "sender_email": sender_email,
                    "company": "Slack User",
                    "subject": subject,
                    "body": text[:4000],
                    "category": category,
                    "priority": priority,
                    "status": "open",
                    "assigned_to": owner,
                    "assigned_role": role,
                    "channel": ch_name,
                    "thread_ts": msg.get("ts"),
                    "created_at": created_at,
                    "updated_at": created_at,
                    "is_live": True,
                })

        except Exception as e:
            print(f"[Slack] Error reading #{ch_name}: {e}")
            continue

    print(f"[Slack] Total live messages fetched: {len(records)}")
    return records


if __name__ == "__main__":
    print("Testing Slack connector...")
    print(f"Token  : {'SET (' + SLACK_BOT_TOKEN[:12] + '...)' if SLACK_BOT_TOKEN else 'NOT SET'}")
    print(f"Channels: {TARGET_CHANNELS}")
    print(f"Lookback: {SLACK_LOOKBACK_HOURS}h\n")

    msgs = fetch_slack_messages()
    if msgs:
        print(f"\n✓ Fetched {len(msgs)} messages")
        for m in msgs[:3]:
            print(f"  [{m['channel']}] {m['sender_name']}: {m['subject'][:80]}")
            print(f"    Category: {m['category']} | Priority: {m['priority']} | Assigned: {m['assigned_to']}")
    else:
        print("No messages fetched. Check your token and channel names in .env")
        print("Make sure the bot is invited to each channel with /invite @PlumESCBot")
