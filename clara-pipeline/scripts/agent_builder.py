"""
agent_builder.py
Generates a Retell-compatible Agent Spec JSON from an account memo.
Produces richly detailed system prompts with correct call-flow hygiene.
"""

import json
from datetime import datetime
from typing import Optional


# ─── SYSTEM PROMPT TEMPLATE ───────────────────────────────────────────────────

SYSTEM_PROMPT_TEMPLATE = """You are a professional, warm, and efficient virtual receptionist for {company_name}.
Your name is Clara. You handle incoming calls on behalf of {company_name}.
Always speak naturally and conversationally — never sound robotic or scripted.
Never mention that you are an AI, virtual assistant, or automated system unless directly asked.
Never mention "function calls", "tools", "system", or any technical processes to callers.

---

## YOUR IDENTITY
You are Clara, a live receptionist for {company_name}.
Company address: {office_address}
Business hours: {business_hours_description}
Timezone: {timezone}

---

## SERVICES YOU SUPPORT
{company_name} provides the following services:
{services_list}

---

## BUSINESS HOURS CALL FLOW

When a caller reaches you DURING BUSINESS HOURS ({business_hours_description}, {timezone}):

1. GREET: "Thank you for calling {company_name}, this is Clara, how can I help you today?"
2. LISTEN: Let the caller explain their need. Do not interrupt.
3. COLLECT: Get the caller's name and callback number.
   - "May I have your name please?"
   - "And what's a good callback number for you?"
4. ROUTE: Based on their need, transfer to the appropriate line.
   - Standard calls: Transfer to {office_transfer_number}
   - {special_routing_rules}
   - Tell the caller: "Let me connect you right now, one moment please."
5. TRANSFER FAILS: If transfer does not connect after {ring_timeout}:
   - "I'm sorry, our team appears to be assisting other customers right now."
   - "I've got your name and number and I'll make sure someone reaches out to you shortly."
   - Confirm: "I have [name] at [number], is that correct?"
6. WRAP UP: "Is there anything else I can help you with?"
7. CLOSE: "Thank you for calling {company_name}, have a great day!"

---

## AFTER-HOURS CALL FLOW

When a caller reaches you OUTSIDE OF BUSINESS HOURS:

1. GREET: "Thank you for calling {company_name}, this is Clara. Our office is currently closed, but I'm here to help."
2. PURPOSE: "What's the reason for your call today?"
3. ASSESS EMERGENCY: Listen for emergency signals. Emergencies include:
{emergency_list}
4. IF EMERGENCY:
   a. ACKNOWLEDGE: "I understand this is urgent — I'm going to get someone on the line for you right away."
   b. COLLECT (quickly): 
      - "Can I get your full name?"
      - "Your callback number?"
      - "And your address or service location?"
   c. ATTEMPT TRANSFER: Immediately attempt emergency transfer.
      {emergency_transfer_sequence}
   d. IF TRANSFER FAILS:
      - "I wasn't able to reach our on-call technician directly, but I've sent an urgent message."
      - "Someone from our team will call you back at [number] within {callback_promise}."
      - "If this is a life-threatening emergency, please call 911 immediately."
   e. DISCLAIMER (if applicable): {after_hours_disclaimer}
5. IF NOT EMERGENCY:
   a. "I understand. Our team will be able to assist you during business hours, {business_hours_description}."
   b. Collect: name, callback number, brief description.
   c. "I'll make sure someone follows up with you by {non_emergency_callback_promise}."
6. WRAP UP: "Is there anything else I can help you with?"
7. CLOSE: "Thank you for calling {company_name}, we appreciate your patience."

---

## CALL TRANSFER PROTOCOL
- Primary transfer line (office hours): {office_transfer_number}
- Emergency line: {emergency_primary_number}
- Transfer attempt window: {ring_timeout}
- If primary fails: {escalation_step_2}
- If all contacts fail: {fallback_action}

---

## STRICT RULES — NEVER VIOLATE
{integration_constraints}
- Never quote prices or provide estimates over the phone.
- Never make scheduling commitments without office confirmation.
- Never discuss compliance, permits, or regulatory timelines.
- Only collect: name, callback number, address (for emergencies), and brief issue description.
- Do not ask more than 3 questions before routing or taking a message.
- Do not confirm our team's availability before they've confirmed it themselves.
- Never mention the name of our software systems (ServiceTrade, FieldEdge, etc.) to callers.

---

## TONE AND STYLE
- Warm, professional, and reassuring.
- Speak at a natural conversational pace.
- Use plain language — avoid jargon.
- If a caller is upset or panicking, lower your voice slightly, slow down, and be extra calm.
- Mirror the caller's urgency appropriately — don't be casual when someone is panicking.
"""


# ─── HELPER FORMATTERS ────────────────────────────────────────────────────────

def format_business_hours(bh: dict) -> str:
    parts = []
    days = bh.get("days", "Monday-Friday")
    start = bh.get("start", "8:00 AM")
    end = bh.get("end", "5:00 PM")
    parts.append(f"{days} {start}–{end}")
    if bh.get("saturday"):
        parts.append(f"Saturday {bh['saturday']}")
    if bh.get("sunday") and bh["sunday"] != "Closed":
        parts.append(f"Sunday {bh['sunday']}")
    return ", ".join(parts)


def format_services(services: list) -> str:
    if not services:
        return "- General services (see account details)"
    return "\n".join(f"- {s}" for s in services)


def format_emergencies(emergencies: list) -> str:
    if not emergencies:
        return "- Any situation causing immediate risk to property or safety"
    return "\n".join(f"- {e}" for e in emergencies)


def format_emergency_transfer(contacts: list) -> str:
    if not contacts:
        return "Transfer to on-call number as provided."
    lines = []
    for c in contacts:
        lines.append(f"   Step {c.get('order', '?')}: Call {c.get('name', 'On-call')} at {c.get('phone', 'TBD')}")
    return "\n".join(lines)


def format_constraints(constraints: list) -> str:
    if not constraints:
        return "- Follow all standard call handling protocols."
    return "\n".join(f"- {c}" for c in constraints)


def format_special_routing(call_transfer_rules: dict) -> str:
    rules = []
    primary = call_transfer_rules.get("office_hours_transfer_to")
    if primary:
        rules.append(f"Transfer to {primary} for standard calls")
    extras = call_transfer_rules.get("special_routes", [])
    for r in extras:
        rules.append(r)
    return "\n   - ".join(rules) if rules else "Transfer to main office line"


# ─── MAIN BUILDER ─────────────────────────────────────────────────────────────

def build_agent_spec(memo: dict) -> dict:
    """
    Build a complete Retell Agent Spec from an account memo.
    """
    account_id   = memo.get("account_id", "unknown")
    company_name = memo.get("company_name", "Our Company")
    version      = memo.get("version", "v1")
    bh           = memo.get("business_hours", {})
    routing      = memo.get("emergency_routing_rules", {})
    transfer     = memo.get("call_transfer_rules", {})
    contacts     = routing.get("contacts", [])

    bh_description   = format_business_hours(bh)
    timezone         = bh.get("timezone", "local time")
    services_list    = format_services(memo.get("services_supported", []))
    emergency_list   = format_emergencies(memo.get("emergency_definition", []))
    transfer_seq     = format_emergency_transfer(contacts)
    constraint_block = format_constraints(memo.get("integration_constraints", []))

    primary_emergency = contacts[0]["phone"] if contacts else "On-call line TBD"
    step2 = (f"Call {contacts[1]['name']} at {contacts[1]['phone']}"
             if len(contacts) > 1 else "Attempt voicemail on primary line")
    fallback = routing.get("fallback_action", "Leave voicemail; inform caller of 30-minute callback window")
    ring_timeout = transfer.get("ring_timeout", "4 rings / ~30 seconds")
    office_transfer = transfer.get("office_hours_transfer_to", "Main office line")
    non_emerg_cb = "9:00 AM next business day"
    callback_promise = "30 minutes"
    after_hours_disclaimer = ""

    # Check for trip charge disclaimer
    constraints_raw = memo.get("integration_constraints", [])
    for c in constraints_raw:
        if "dispatch fee" in c.lower() or "trip charge" in c.lower():
            after_hours_disclaimer = ("Please note that after-hours emergency service "
                                      "may include an additional dispatch fee.")
            break

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        company_name             = company_name,
        office_address           = memo.get("office_address") or "On file",
        business_hours_description = bh_description,
        timezone                 = timezone,
        services_list            = services_list,
        office_transfer_number   = office_transfer,
        special_routing_rules    = format_special_routing(transfer),
        ring_timeout             = ring_timeout,
        emergency_list           = emergency_list,
        emergency_transfer_sequence = transfer_seq,
        emergency_primary_number = primary_emergency,
        escalation_step_2        = step2,
        fallback_action          = fallback,
        callback_promise         = callback_promise,
        non_emergency_callback_promise = non_emerg_cb,
        after_hours_disclaimer   = after_hours_disclaimer,
        integration_constraints  = constraint_block,
    )

    # Build key variables block
    key_variables = {
        "company_name":        company_name,
        "timezone":            timezone,
        "business_hours":      bh_description,
        "office_address":      memo.get("office_address"),
        "emergency_contacts":  contacts,
        "office_transfer_line": office_transfer,
        "after_hours_fallback": fallback,
    }

    # Tool invocation placeholders (for actual Retell integration)
    tool_placeholders = [
        {
            "tool_name": "transfer_call",
            "description": "Transfers the live call to a phone number",
            "parameters": {"phone_number": "string"},
            "internal_note": "Never say 'transferring call' or reference this function to caller"
        },
        {
            "tool_name": "send_sms_summary",
            "description": "Sends SMS summary of call to on-call contact",
            "parameters": {"to": "string", "message": "string"},
            "internal_note": "Fire after failed transfer attempt"
        },
        {
            "tool_name": "log_call_record",
            "description": "Logs caller info and reason to internal system",
            "parameters": {
                "caller_name": "string",
                "caller_phone": "string",
                "caller_address": "string (emergency only)",
                "issue_summary": "string",
                "is_emergency": "boolean"
            },
            "internal_note": "Always fire at end of call"
        }
    ]

    agent_spec = {
        "agent_name": f"{company_name} - Clara Receptionist",
        "account_id": account_id,
        "version": version,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "voice_style": {
            "provider": "elevenlabs",
            "voice_id": "recommended: Rachel (warm, professional female)",
            "speed": 1.0,
            "stability": 0.75,
            "similarity_boost": 0.75
        },
        "llm_config": {
            "model": "gpt-4o",
            "temperature": 0.3,
            "max_tokens": 400,
            "note": "Low temperature for consistent, reliable call handling"
        },
        "system_prompt": system_prompt,
        "key_variables": key_variables,
        "tool_invocation_placeholders": tool_placeholders,
        "call_transfer_protocol": {
            "office_hours_primary": office_transfer,
            "ring_timeout": ring_timeout,
            "if_no_answer": transfer.get("if_no_answer", "Take message"),
            "emergency_sequence": contacts,
            "transfer_announcement": "Let me connect you right now, one moment please.",
            "transfer_fail_message": (
                "I'm sorry, our team appears to be assisting other customers. "
                "I've captured your information and will ensure a prompt callback."
            )
        },
        "fallback_protocol": {
            "trigger": "All transfer attempts exhausted",
            "action": fallback,
            "sms_alert": True,
            "voicemail": True,
            "caller_message": (
                "I wasn't able to reach our team directly, but I've sent an urgent message. "
                f"Someone will call you back within {callback_promise}."
            )
        },
        "retell_import_instructions": {
            "step1": "Log in to app.retellai.com",
            "step2": "Click 'Create Agent' → 'Custom LLM'",
            "step3": "Paste the 'system_prompt' field into the System Prompt box",
            "step4": "Configure voice settings per 'voice_style'",
            "step5": "Add tools under 'Tools' tab using 'tool_invocation_placeholders'",
            "step6": "Set LLM model per 'llm_config'",
            "step7": "Save and test with a trial call"
        }
    }

    return agent_spec
