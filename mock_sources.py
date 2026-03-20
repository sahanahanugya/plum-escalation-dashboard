"""
Generates realistic B2B health insurance mock messages for Plum.
If mock_data.json exists, loads from it (editable). Otherwise generates randomly.
"""

import uuid
import json
import os
import random
from datetime import datetime, timedelta
from database import Escalation

random.seed(42)


def load_from_json() -> list:
    """Load mock records from mock_data.json if it exists."""
    json_path = os.path.join(os.path.dirname(__file__), "mock_data.json")
    if not os.path.exists(json_path):
        return []
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        records = []
        now = datetime.utcnow()
        for i, item in enumerate(data):
            created = now - timedelta(hours=i * 2)
            records.append(Escalation(
                id=str(uuid.uuid5(uuid.NAMESPACE_DNS, f"mock-json-{i}")),
                source=item.get("source", "email"),
                sender_name=item.get("sender_name", "Unknown"),
                sender_email=item.get("sender_email", ""),
                company=item.get("company", ""),
                subject=item.get("subject", ""),
                body=item.get("body", ""),
                category=item.get("category", "Query"),
                priority=item.get("priority", "P3"),
                status=item.get("status", "open"),
                assigned_to=item.get("assigned_to"),
                assigned_role=item.get("assigned_role"),
                ai_summary=None,
                ai_reply_draft=None,
                channel=item.get("channel"),
                thread_ts=None,
                created_at=created,
                updated_at=created,
                is_live=False,
            ))
        print(f"[Mock] Loaded {len(records)} records from mock_data.json")
        return records
    except Exception as e:
        print(f"[Mock] Failed to load mock_data.json: {e}")
        return []

# ──────────────────────────────────────────────
# Reference data
# ──────────────────────────────────────────────

COMPANIES = [
    "Infosys Ltd", "TCS", "Wipro Technologies", "Zomato India", "Swiggy",
    "Razorpay", "CRED", "Dunzo", "Meesho", "ShareChat", "PhonePe",
    "Ola Cabs", "Nykaa", "Urban Company", "Groww", "Zepto",
    "Lenskart", "Moglix", "Vedantu", "Byju's", "Unacademy",
    "Freshworks", "Chargebee", "Postman", "BrowserStack", "Hasura",
    "Pine Labs", "BharatPe", "Slice", "Jupiter Money", "Fi Money",
    "Rapido", "Porter", "Shiprocket", "Delhivery", "Blue Dart",
    "Apollo Hospitals", "Fortis Healthcare", "Max Healthcare",
    "Manipal Hospitals", "Narayana Health", "Aster DM Healthcare",
    "HDFC Life", "Bajaj Finserv", "Paytm Insurance", "Digit Insurance",
    "Acko", "Go Digit", "ICICI Lombard", "Niva Bupa",
]

CONTACTS = {
    c: [
        (f"Rahul {c.split()[0]}", f"rahul.{c.split()[0].lower()}@{c.lower().replace(' ', '')}.com"),
        (f"Priya {c.split()[0]}", f"priya.{c.split()[0].lower()}@{c.lower().replace(' ', '')}.com"),
        (f"Amit Kumar", f"amit.kumar@{c.lower().replace(' ', '')}.com"),
        (f"Sneha Sharma", f"sneha.sharma@{c.lower().replace(' ', '')}.com"),
        (f"Vikram Singh", f"vikram.singh@{c.lower().replace(' ', '')}.com"),
    ]
    for c in COMPANIES
}

TEAM = [
    ("Ipsita Sahu", "Claims Lead"),
    ("Manashi Goswami", "Compliance Manager"),
    ("Mikhel Dhiman", "Tech Support Lead"),
    ("Arun Saseedharan", "Senior AM"),
    ("Vaishnavi Bhat", "Account Manager"),
    ("Rajorshi Chowdhury", "Junior AM"),
    ("Subash P", "Customer Success"),
    ("Deepika Nair", "Operations"),
]

SOURCES = ["email", "slack", "whatsapp"]
STATUSES = ["open", "in-progress", "resolved"]

SLACK_CHANNELS = [
    "all-plum-escalation-dashboard",
    "new-channel",
    "general",
    "claims-support",
    "hr-benefits",
]

# ──────────────────────────────────────────────
# Message templates per scenario
# ──────────────────────────────────────────────

ESCALATION_SCENARIOS = [
    {
        "subject": "URGENT: Cashless claim rejected at {hospital} — Employee admitted",
        "body": (
            "Hi Plum team,\n\nOur employee {name} was admitted to {hospital} last night for {condition}. "
            "The cashless claim has been REJECTED by the TPA citing 'policy exclusion'. "
            "This is an emergency situation and the hospital is demanding immediate payment. "
            "Please escalate this immediately. The claim ID is CLM-{claim_id}.\n\n"
            "This is completely unacceptable and needs resolution in the next 2 hours."
        ),
        "category": "Escalation", "priority": "P1",
        "keywords": ["cashless", "emergency", "admitted"],
    },
    {
        "subject": "CRITICAL: Pre-authorization denied for surgery — scheduled tomorrow",
        "body": (
            "Urgent escalation needed!\n\nEmployee {name} has surgery scheduled for tomorrow at {hospital}. "
            "Pre-authorization has been denied saying the procedure is not covered. "
            "Our policy document clearly states it IS covered under major surgical procedures. "
            "Claim ID: CLM-{claim_id}. Policy: POL-{policy_id}.\n\n"
            "Patient is distressed. Please intervene ASAP."
        ),
        "category": "Escalation", "priority": "P1",
        "keywords": ["surgery", "pre-authorization", "denied"],
    },
    {
        "subject": "Escalation: TPA not responding for 5 days — Reimbursement claim pending",
        "body": (
            "Dear Plum,\n\nWe submitted a reimbursement claim (CLM-{claim_id}) on {date_ago} days ago. "
            "The TPA has not responded despite 4 follow-up emails and 3 calls. "
            "Amount: ₹{amount}. Employee {name} is waiting urgently.\n\n"
            "We are escalating this to Plum as our broker. Please resolve this at the earliest."
        ),
        "category": "Escalation", "priority": "P2",
        "keywords": ["TPA", "reimbursement", "escalation"],
    },
    {
        "subject": "Escalating to senior management — Policy renewal disaster",
        "body": (
            "I am escalating this to your senior management.\n\nOur group health policy (POL-{policy_id}) "
            "renewal was supposed to happen on {date_ago} days ago. We have sent 6 emails and "
            "no one has reverted. Our 450 employees are now WITHOUT HEALTH COVER.\n\n"
            "This is a serious lapse. I need the CEO/head to call me today."
        ),
        "category": "Escalation", "priority": "P1",
        "keywords": ["renewal", "management", "escalating"],
    },
    {
        "subject": "Emergency: Employee in ICU — Insurance company refusing to pay",
        "body": (
            "EMERGENCY ESCALATION\n\nEmployee {name} is in ICU at {hospital}. "
            "Hospital bill has crossed ₹{amount} and the insurance company is refusing cashless. "
            "The hospital has sent a legal notice threatening to stop treatment.\n\n"
            "Please help immediately. This is life and death."
        ),
        "category": "Escalation", "priority": "P1",
        "keywords": ["ICU", "emergency", "refusing"],
    },
]

COMPLAINT_SCENARIOS = [
    {
        "subject": "Complaint: Extremely poor service from Plum team",
        "body": (
            "Dear Sir/Madam,\n\nI am writing to formally complain about the terrible service "
            "we have received from Plum over the past month. "
            "Our account manager has not responded to 8 emails over 3 weeks. "
            "Employee {name} has a pending claim of ₹{amount} unresolved for {date_ago} days.\n\n"
            "This is completely unprofessional and we are considering switching our broker."
        ),
        "category": "Complaint", "priority": "P2",
        "keywords": ["complaint", "poor service", "unprofessional"],
    },
    {
        "subject": "Formal complaint — Wrong premium deduction from employee salary",
        "body": (
            "This is a formal complaint.\n\nFor the past 3 months, wrong premium amounts have been "
            "deducted from employee {name}'s salary. The correct premium is ₹{amount}/month "
            "but ₹{amount2} has been deducted each month.\n\n"
            "We want immediate rectification and refund of excess amount. "
            "This has impacted {count} employees total."
        ),
        "category": "Complaint", "priority": "P2",
        "keywords": ["complaint", "wrong deduction", "premium"],
    },
    {
        "subject": "Unhappy with claim settlement — Amount drastically reduced",
        "body": (
            "We are very unhappy with the claim settlement for CLM-{claim_id}.\n\n"
            "The approved amount was ₹{amount} against a claim of ₹{amount2}. "
            "No explanation was given for this reduction. The employee {name} is dissatisfied "
            "and so are we as an organization.\n\n"
            "Please provide a detailed breakdown and reconsider."
        ),
        "category": "Complaint", "priority": "P2",
        "keywords": ["unhappy", "claim settlement", "reduced"],
    },
    {
        "subject": "Complaint regarding IRDAI non-compliance in claim processing",
        "body": (
            "To Whom It May Concern,\n\nWe have identified potential IRDAI guideline violations "
            "in how our claim (CLM-{claim_id}) was processed. "
            "The claim was rejected citing reasons not permissible under IRDAI circular dated {date_ago}/2024.\n\n"
            "We will be filing a formal complaint with IRDAI if this is not addressed in 48 hours."
        ),
        "category": "Complaint", "priority": "P1",
        "keywords": ["IRDAI", "complaint", "legal", "compliance"],
    },
    {
        "subject": "Worst experience — Portal not working and no support",
        "body": (
            "This is the worst experience we've had with any vendor!\n\n"
            "The Plum portal has been down for our team for 3 days. "
            "We cannot view any employee health cards, claim status, or policy documents. "
            "Support team is completely unresponsive.\n\nThis is unacceptable for a critical service."
        ),
        "category": "Complaint", "priority": "P2",
        "keywords": ["portal", "tech", "down", "complaint"],
    },
]

FOLLOWUP_SCENARIOS = [
    {
        "subject": "Follow-up: Claim CLM-{claim_id} still pending — 2nd reminder",
        "body": (
            "Hi,\n\nThis is a follow-up on claim CLM-{claim_id} submitted {date_ago} days ago. "
            "We had previously written on this matter but have not received any update.\n\n"
            "Employee {name} is waiting for the reimbursement of ₹{amount}. "
            "Please provide an ETA for resolution."
        ),
        "category": "Follow-up", "priority": "P3",
        "keywords": ["follow-up", "reminder", "pending"],
    },
    {
        "subject": "Reminder: Premium invoice INV-{inv_id} overdue by {date_ago} days",
        "body": (
            "Dear Finance Team,\n\nThis is a reminder that invoice INV-{inv_id} for ₹{amount} "
            "is overdue by {date_ago} days. Please process the payment at the earliest to "
            "avoid any disruption to your health coverage.\n\n"
            "Policy: POL-{policy_id} | Due date: {date_ago} days ago"
        ),
        "category": "Follow-up", "priority": "P3",
        "keywords": ["invoice", "reminder", "overdue"],
    },
    {
        "subject": "Checking status on employee addition request — 3rd follow-up",
        "body": (
            "Hello,\n\nWe submitted a request to add {count} new employees to our policy "
            "on {date_ago} days ago (Ticket: TKT-{claim_id}). "
            "These employees are still not reflecting on the portal.\n\n"
            "Please update us on the status. This is our 3rd follow-up email."
        ),
        "category": "Follow-up", "priority": "P3",
        "keywords": ["employee addition", "status", "follow-up"],
    },
    {
        "subject": "Following up on health card issuance for new joiners",
        "body": (
            "Hi Plum team,\n\nFollowing up on the health card issuance for {count} new joiners "
            "who joined last month. The cards were supposed to be ready in 7 working days "
            "but it's been {date_ago} days now.\n\nKindly expedite this."
        ),
        "category": "Follow-up", "priority": "P3",
        "keywords": ["health card", "new joiners", "follow-up"],
    },
]

QUERY_SCENARIOS = [
    {
        "subject": "Query: Is maternity benefit available for employee joining 2 months ago?",
        "body": (
            "Hi,\n\nI have a query regarding maternity benefits. "
            "Our employee {name} joined 2 months ago and is 3 months pregnant. "
            "Will she be eligible for maternity cover under our group policy POL-{policy_id}?\n\n"
            "Please clarify the waiting period and coverage amount."
        ),
        "category": "Query", "priority": "P3",
        "keywords": ["query", "maternity", "eligible"],
    },
    {
        "subject": "Question: How to add dependents for employees under our group policy",
        "body": (
            "Hello Plum team,\n\nWe have {count} employees who want to add their dependents "
            "(spouse + children) to their health cover. "
            "Could you please share the process, documents required, and additional premium?\n\n"
            "Policy number: POL-{policy_id}"
        ),
        "category": "Query", "priority": "P3",
        "keywords": ["query", "dependents", "process"],
    },
    {
        "subject": "Query regarding pre-existing disease coverage",
        "body": (
            "Dear Sir,\n\nOne of our employees {name} has a pre-existing condition (diabetes). "
            "They want to know if their condition is covered under our group health policy "
            "and after what waiting period?\n\nAlso, does the policy cover insulin costs monthly?"
        ),
        "category": "Query", "priority": "P3",
        "keywords": ["query", "pre-existing", "coverage"],
    },
    {
        "subject": "Can you help clarify room rent sublimit in our policy?",
        "body": (
            "Hi,\n\nWe're trying to understand the room rent sublimit in our policy POL-{policy_id}. "
            "An employee was told the room rent is capped but the policy wording is unclear.\n\n"
            "Could you explain what the actual cap is and which hospitals have private rooms within this limit?"
        ),
        "category": "Query", "priority": "P3",
        "keywords": ["query", "room rent", "sublimit"],
    },
    {
        "subject": "Need help understanding claim process for reimbursement",
        "body": (
            "Hello,\n\nNew HR here at {company}. Could you walk me through the reimbursement "
            "claim process? Employee {name} had an outpatient visit and paid out of pocket.\n\n"
            "What documents are needed? Where to submit? What's the typical turnaround time?"
        ),
        "category": "Query", "priority": "P3",
        "keywords": ["query", "reimbursement", "process"],
    },
]

INITIATION_SCENARIOS = [
    {
        "subject": "Interested in Plum group health insurance for our 200-person team",
        "body": (
            "Hi Plum team,\n\nWe are {company}, a {count}-person startup and we're looking "
            "to set up group health insurance for our employees.\n\n"
            "Could you share your plans, pricing, and how the onboarding process works? "
            "We want to get this done before our next payroll cycle."
        ),
        "category": "Initiation", "priority": "P3",
        "keywords": ["interested", "new policy", "onboarding"],
    },
    {
        "subject": "Request for proposal — Group health policy renewal for next year",
        "body": (
            "Dear Plum,\n\nOur current group health policy (not with Plum) expires in 2 months. "
            "We are evaluating brokers for renewal. Our team size: {count} employees.\n\n"
            "Please share a detailed proposal with coverage options and pricing."
        ),
        "category": "Initiation", "priority": "P3",
        "keywords": ["proposal", "renewal", "evaluating"],
    },
    {
        "subject": "New employee batch enrollment — 45 new joiners this month",
        "body": (
            "Hi,\n\nWe have {count} new joiners this month who need to be added to our "
            "existing policy POL-{policy_id}. I'm attaching the list with their details.\n\n"
            "Please initiate the enrollment process and confirm the additional premium."
        ),
        "category": "Initiation", "priority": "P3",
        "keywords": ["enrollment", "new joiners", "initiation"],
    },
    {
        "subject": "Getting started with Plum — referred by a portfolio company",
        "body": (
            "Hello,\n\nWe were referred to Plum by {company2}. We are looking to set up "
            "comprehensive health benefits for our team of {count} people.\n\n"
            "Can we schedule a call to understand what Plum offers and how it's different?"
        ),
        "category": "Initiation", "priority": "P3",
        "keywords": ["referred", "getting started", "initiation"],
    },
]

APPRECIATION_SCENARIOS = [
    {
        "subject": "Thank you — Excellent handling of our emergency claim",
        "body": (
            "Dear Plum team,\n\nI wanted to take a moment to thank {name} and the entire team "
            "for the exceptional handling of our emergency claim (CLM-{claim_id}).\n\n"
            "The quick response and coordination with the hospital during a stressful time "
            "was truly appreciated. Our employee and their family are very grateful."
        ),
        "category": "Appreciation", "priority": "P3",
        "keywords": ["thank you", "excellent", "appreciated"],
    },
    {
        "subject": "Great experience with Plum — Happy to renew",
        "body": (
            "Hi,\n\nJust wanted to share that we've had a great experience with Plum this year. "
            "The portal is intuitive, claim settlements have been smooth, and the support team "
            "is always responsive.\n\nWe are happy to renew our policy for another year."
        ),
        "category": "Appreciation", "priority": "P3",
        "keywords": ["great experience", "happy", "renew"],
    },
    {
        "subject": "Appreciation for Plum team — Smooth enrollment process",
        "body": (
            "Dear {name},\n\nWe recently completed the enrollment of {count} employees onto Plum. "
            "The process was seamless and your team's support was outstanding.\n\n"
            "Special thanks to the account manager for being proactive."
        ),
        "category": "Appreciation", "priority": "P3",
        "keywords": ["appreciation", "smooth", "outstanding"],
    },
]

ALL_SCENARIOS = (
    ESCALATION_SCENARIOS * 5 +
    COMPLAINT_SCENARIOS * 4 +
    FOLLOWUP_SCENARIOS * 4 +
    QUERY_SCENARIOS * 5 +
    INITIATION_SCENARIOS * 4 +
    APPRECIATION_SCENARIOS * 3
)

HOSPITALS = [
    "Apollo Hospitals", "Fortis Healthcare", "Max Super Speciality",
    "Manipal Hospital", "Narayana Multispeciality", "AIIMS",
    "Lilavati Hospital", "Kokilaben Hospital", "Medanta",
]

CONDITIONS = [
    "appendicitis", "cardiac arrest", "dengue fever", "severe pneumonia",
    "kidney stones", "road accident injuries", "fractures", "stroke",
]


def _assign_owner(category: str, subject: str, body: str) -> tuple:
    text = (subject + " " + body).lower()
    if any(k in text for k in ["cashless", "emergency", "icu", "admitted", "surgery", "claim"]):
        return TEAM[0]  # Ipsita Sahu — Claims Lead
    if any(k in text for k in ["irdai", "legal", "compliance", "circular", "regulation"]):
        return TEAM[1]  # Manashi — Compliance
    if any(k in text for k in ["portal", "tech", "login", "app", "down", "error", "not working"]):
        return TEAM[2]  # Mikhel — Tech
    if category == "Escalation":
        return TEAM[3]  # Arun — Senior AM
    if category == "Complaint":
        return TEAM[4]  # Vaishnavi — AM
    if category in ("Query", "Initiation"):
        return TEAM[5]  # Rajorshi — Junior AM
    if category in ("Follow-up",) or any(k in text for k in ["invoice", "payment", "renewal"]):
        return TEAM[6]  # Subash — CS
    return TEAM[7]  # Deepika — Ops


def _fill(template: str, company: str) -> str:
    return template.format(
        name=random.choice(["Ravi Kumar", "Deepa Nair", "Suresh Menon", "Ananya Iyer",
                             "Rahul Shah", "Neha Gupta", "Kiran Rao", "Preethi Pillai"]),
        hospital=random.choice(HOSPITALS),
        condition=random.choice(CONDITIONS),
        claim_id=f"{random.randint(10000, 99999)}",
        policy_id=f"{random.randint(1000, 9999)}",
        inv_id=f"{random.randint(1000, 9999)}",
        amount=f"{random.randint(30, 900) * 1000:,}",
        amount2=f"{random.randint(10, 50) * 1000:,}",
        count=random.randint(10, 200),
        date_ago=random.randint(2, 30),
        company=company,
        company2=random.choice(COMPANIES),
    )


def generate_mock_records(count: int = 1200) -> list:
    # Try loading from editable JSON file first
    json_records = load_from_json()
    if json_records:
        return json_records
    # Fall back to random generation
    records = []
    now = datetime.utcnow()

    for i in range(count):
        company = random.choice(COMPANIES)
        contact_name, contact_email = random.choice(CONTACTS[company])
        scenario = random.choice(ALL_SCENARIOS)
        source = random.choice(SOURCES)

        subject = _fill(scenario["subject"], company)
        body = _fill(scenario["body"], company)

        category = scenario["category"]
        priority = scenario["priority"]
        # Only Escalation/Complaint get P1/P2; everything else is P3
        if category not in ("Escalation", "Complaint"):
            priority = "P3"

        owner_name, owner_role = _assign_owner(category, subject, body)
        status = random.choices(STATUSES, weights=[50, 30, 20])[0]

        age_hours = random.randint(0, 72 * 7)  # up to 7 weeks ago
        created_at = now - timedelta(hours=age_hours)
        updated_at = created_at + timedelta(hours=random.randint(0, min(age_hours, 48)))

        rec = Escalation(
            id=str(uuid.uuid4()),
            source=source,
            sender_name=contact_name,
            sender_email=contact_email,
            company=company,
            subject=subject,
            body=body,
            category=category,
            priority=priority,
            status=status,
            assigned_to=owner_name,
            assigned_role=owner_role,
            ai_summary=None,
            ai_reply_draft=None,
            channel=random.choice(SLACK_CHANNELS) if source == "slack" else None,
            thread_ts=f"{int(created_at.timestamp())}.{random.randint(100000, 999999)}" if source == "slack" else None,
            created_at=created_at,
            updated_at=updated_at,
            is_live=False,
        )
        records.append(rec)

    return records


if __name__ == "__main__":
    from database import init_db, SessionLocal
    init_db()
    db = SessionLocal()
    existing = db.query(Escalation).count()
    if existing == 0:
        records = generate_mock_records(1200)
        db.add_all(records)
        db.commit()
        print(f"Seeded {len(records)} mock records.")
    else:
        print(f"Database already has {existing} records. Skipping seed.")
    db.close()
