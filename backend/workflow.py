"""
Defines all 7 onboarding workflow stages, their required items, and per-stage LLM instructions.
"""

from dataclasses import dataclass


@dataclass
class WorkflowItem:
    id: str
    label: str
    description: str


@dataclass
class WorkflowStage:
    id: str
    name: str
    description: str
    icon: str
    items: list[WorkflowItem]
    llm_instructions: str


STAGES: list[WorkflowStage] = [
    WorkflowStage(
        id="document_collection",
        name="Document Collection",
        description="Gather required identity and employment documents",
        icon="📄",
        items=[
            WorkflowItem("govt_id", "Government ID", "Passport, Aadhaar, or driving licence"),
            WorkflowItem("address_proof", "Address Proof", "Utility bill, bank statement, or rental agreement"),
            WorkflowItem("education_cert", "Education Certificates", "Degree, diploma, or marksheets"),
            WorkflowItem("prev_employment", "Previous Employment Proof", "Experience letters or relieving letters"),
        ],
        llm_instructions=(
            "Help the employee understand which documents are needed and how to upload them via the Documents panel. "
            "Ask about one document type at a time. Confirm when each is received. "
            "Accepted formats are PDF, JPG, PNG. "
            "If they ask what counts as valid proof, answer specifically."
        ),
    ),
    WorkflowStage(
        id="bgv",
        name="Background Verification",
        description="Complete background check consent and provide reference details",
        icon="🔍",
        items=[
            WorkflowItem("bgv_consent", "BGV Consent", "Employee has given written consent for background check"),
            WorkflowItem("prev_employer_details", "Previous Employer Details", "Company name, HR contact, and dates of employment"),
            WorkflowItem("reference_contacts", "Reference Contacts", "2 professional references with name, designation, and phone"),
        ],
        llm_instructions=(
            "Explain what background verification involves, why it is required, and the typical timeline (7–10 business days). "
            "Collect consent clearly — explain what will be checked (employment history, criminal record, education). "
            "Then gather previous employer details and two professional references one at a time. "
            "Reassure them this is a standard process for all new hires."
        ),
    ),
    WorkflowStage(
        id="offer_letter",
        name="Offer Letter",
        description="Review offer letter, resolve queries, and confirm acceptance",
        icon="📋",
        items=[
            WorkflowItem("offer_reviewed", "Offer Reviewed", "Employee has read the full offer letter"),
            WorkflowItem("questions_answered", "Questions Answered", "All queries about the offer are resolved"),
            WorkflowItem("offer_acknowledged", "Offer Acknowledged", "Digital acknowledgment of acceptance recorded"),
        ],
        llm_instructions=(
            "Help the employee understand all aspects of their offer: role, compensation, CTC breakdown, joining date, "
            "probation period, notice period, and any conditions. "
            "Answer questions thoroughly — be transparent. If something needs HR confirmation, say so. "
            "Once all questions are resolved, guide them to click 'Mark as Acknowledged' in the checklist."
        ),
    ),
    WorkflowStage(
        id="id_access",
        name="ID & Access Allocation",
        description="Set up corporate identity and system access",
        icon="🔐",
        items=[
            WorkflowItem("email_setup", "Corporate Email", "Work email account created and credentials shared"),
            WorkflowItem("system_access", "System Access", "Required software, VPN, and tool access granted"),
            WorkflowItem("building_access", "Building Access", "Access card or badge issued"),
            WorkflowItem("equipment_request", "Equipment Request", "Laptop and peripherals assigned or ordered"),
        ],
        llm_instructions=(
            "Walk the employee through what access they will receive and expected timelines for each item. "
            "Help them raise specific access requests for their role (e.g., developer tools, finance systems). "
            "Explain who to contact if access is delayed — IT helpdesk for systems, admin for building access. "
            "Confirm each item as it gets set up."
        ),
    ),
    WorkflowStage(
        id="training",
        name="Training Assignment",
        description="Assign and track mandatory and role-specific training courses",
        icon="🎓",
        items=[
            WorkflowItem("compliance_training", "Compliance Training", "POSH, Code of Conduct, Data Privacy (mandatory for all)"),
            WorkflowItem("role_training", "Role-Specific Training", "Training relevant to the employee's department and role"),
            WorkflowItem("tools_training", "Tools & Systems Training", "HRMS, project tools, and internal platforms"),
        ],
        llm_instructions=(
            "Explain the assigned training courses, why each is important, and their deadlines. "
            "Start with mandatory compliance training (POSH, data privacy, code of conduct). "
            "Then cover role-specific training and tools. "
            "Help them understand how to access the Learning Management System (LMS) and track their progress."
        ),
    ),
    WorkflowStage(
        id="policy_acknowledgment",
        name="Policy Acknowledgment",
        description="Review and sign off on company policies",
        icon="✅",
        items=[
            WorkflowItem("code_of_conduct", "Code of Conduct", "Employee behaviour, ethics, and disciplinary policy"),
            WorkflowItem("it_policy", "IT & Security Policy", "Acceptable use of company systems, devices, and data"),
            WorkflowItem("leave_policy", "Leave Policy", "Leave types, accrual, carryover, and application process"),
            WorkflowItem("harassment_policy", "POSH / Anti-Harassment Policy", "Prevention of sexual harassment at workplace"),
        ],
        llm_instructions=(
            "Walk the employee through each policy conversationally — explain the key points, do not just say 'read the document'. "
            "Invite questions after each policy. Be specific and practical. "
            "Once they understand a policy, ask them to acknowledge it in the checklist. "
            "Collect acknowledgment one policy at a time."
        ),
    ),
    WorkflowStage(
        id="payroll_setup",
        name="Payroll Setup",
        description="Complete banking and payroll configuration",
        icon="💰",
        items=[
            WorkflowItem("bank_details", "Bank Account Details", "Account number, IFSC code, and bank name for salary credit"),
            WorkflowItem("tax_declaration", "Tax Declaration", "Investment declarations for TDS computation (Form 12BB)"),
            WorkflowItem("salary_acknowledged", "Salary Structure Understood", "Employee understands CTC, in-hand, PF, PT, and deductions"),
        ],
        llm_instructions=(
            "Help the employee complete payroll setup. Collect bank account details — remind them never to share OTPs or card CVVs. "
            "Explain the tax declaration process (Form 12BB), deadlines, and what counts as a valid investment declaration. "
            "Walk them through their salary structure: gross CTC, net in-hand, PF deduction, PT, and any allowances. "
            "Answer questions about pay dates, payslips, and reimbursement claims."
        ),
    ),
]

STAGE_MAP: dict[str, WorkflowStage] = {s.id: s for s in STAGES}
STAGE_IDS: list[str] = [s.id for s in STAGES]


def get_next_stage(current_stage_id: str) -> str | None:
    try:
        idx = STAGE_IDS.index(current_stage_id)
    except ValueError:
        return None
    return STAGE_IDS[idx + 1] if idx + 1 < len(STAGE_IDS) else None


def overall_progress_pct(current_stage_id: str) -> float:
    try:
        idx = STAGE_IDS.index(current_stage_id)
    except ValueError:
        return 0.0
    return round((idx / len(STAGE_IDS)) * 100, 1)
