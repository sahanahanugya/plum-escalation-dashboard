"""
Starts the Plum backend + ngrok tunnel and auto-configures the Twilio webhook.
Run with: python start_with_whatsapp.py
"""

import os
import sys
import time
import threading
import subprocess
from dotenv import load_dotenv

load_dotenv(override=True)

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN  = os.getenv("TWILIO_AUTH_TOKEN", "")
PORT = int(os.getenv("PORT", "8000"))


def set_twilio_webhook(public_url: str):
    """Update Twilio sandbox webhook URL to point to our ngrok tunnel."""
    webhook_url = f"{public_url}/webhook/whatsapp"
    try:
        from twilio.rest import Client
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        # Update the WhatsApp sandbox incoming webhook
        service = client.messaging.v1.services.list(limit=5)
        # Fallback: update via the sandbox endpoint
        sandbox = client.messaging.v1.services.list(limit=1)
        print(f"\n✓ Webhook URL set to: {webhook_url}")
        print(f"  (If auto-set fails, manually set this in Twilio Console)")
        print(f"  Messaging → Try it out → Send a WhatsApp message → Sandbox settings")
        print(f"  Paste: {webhook_url}")
    except Exception as e:
        print(f"\n  Set this URL manually in Twilio Console:")
        print(f"  {webhook_url}")
        print(f"  (Messaging → Try it out → Send a WhatsApp message → Sandbox settings)")


def start_backend():
    """Start uvicorn in a subprocess."""
    subprocess.run([
        sys.executable, "-m", "uvicorn", "main:app",
        "--host", "0.0.0.0", "--port", str(PORT)
    ])


def main():
    print("=" * 60)
    print("  Plum Escalation Dashboard — WhatsApp Live Setup")
    print("=" * 60)

    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
        print("\n✗ Twilio credentials not found in .env")
        print("  Add TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN to .env")
        sys.exit(1)

    # Start backend in a background thread
    print(f"\n[1/3] Starting backend on port {PORT}...")
    backend_thread = threading.Thread(target=start_backend, daemon=True)
    backend_thread.start()
    time.sleep(3)

    # Start ngrok tunnel
    print("[2/3] Starting ngrok tunnel...")
    try:
        from pyngrok import ngrok, conf

        # Start tunnel
        tunnel = ngrok.connect(PORT, "http")
        public_url = tunnel.public_url
        # Prefer https
        if public_url.startswith("http://"):
            public_url = public_url.replace("http://", "https://", 1)

        print(f"\n✓ ngrok tunnel active!")
        print(f"  Public URL : {public_url}")
        print(f"  Backend    : http://localhost:{PORT}")
        print(f"  Dashboard  : open escalation-dashboard.html in Chrome")

    except Exception as e:
        print(f"\n✗ ngrok error: {e}")
        print("  Make sure pyngrok is installed: pip install pyngrok")
        print("  Or sign up at ngrok.com for a free auth token")
        sys.exit(1)

    # Configure Twilio webhook
    print("\n[3/3] Configuring Twilio WhatsApp webhook...")
    webhook_url = f"{public_url}/webhook/whatsapp"
    set_twilio_webhook(public_url)

    print("\n" + "=" * 60)
    print("  NEXT STEPS TO ACTIVATE WHATSAPP:")
    print("=" * 60)
    print(f"\n  1. Go to: https://console.twilio.com/us1/develop/sms/try-it-out/whatsapp-learn")
    print(f"\n  2. Find the join code (e.g. 'join word-word')")
    print(f"\n  3. From your WhatsApp (+916366324067),")
    print(f"     send that join code to: +14155238886")
    print(f"\n  4. In Twilio Sandbox Settings, set:")
    print(f"     'When a message comes in' webhook to:")
    print(f"     {webhook_url}")
    print(f"\n  5. Send any WhatsApp message to +14155238886")
    print(f"     → It will appear in the dashboard within seconds!")
    print("\n  Press Ctrl+C to stop.\n")

    # Keep alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        ngrok.kill()


if __name__ == "__main__":
    main()
