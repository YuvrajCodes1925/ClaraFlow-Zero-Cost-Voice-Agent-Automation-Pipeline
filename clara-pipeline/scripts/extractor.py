"""
extractor.py
Core extraction module for Clara Answers Pipeline.
Supports: Ollama (local LLM, zero-cost) and rule-based fallback.
"""

import re
import json
import os
import hashlib
import subprocess
from datetime import datetime
from typing import Optional


# ─── LLM PROVIDER CONFIG ─────────────────────────────────────────────────────

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral")   # or llama3, phi3, etc.
OLLAMA_HOST  = os.getenv("OLLAMA_HOST", "http://localhost:11434")
USE_OLLAMA   = os.getenv("USE_OLLAMA", "true").lower() == "true"


# ─── PROMPT TEMPLATES ─────────────────────────────────────────────────────────

DEMO_EXTRACTION_PROMPT = """You are a data extraction specialist for a call answering service.
Extract structured information from the following demo call transcript.

Return ONLY valid JSON with exactly these fields (no extra commentary):
{{
  "company_name": "string or null",
  "business_hours": {{
    "days": "e.g. Monday-Friday",
    "start": "e.g. 7:00 AM",
    "end": "e.g. 6:00 PM",
    "timezone": "e.g. Central Time",
    "saturday": "e.g. 8:00 AM - 2:00 PM or null",
    "sunday": "e.g. Closed or null"
  }},
  "office_address": "full address string or null",
  "services_supported": ["list", "of", "services"],
  "emergency_definition": ["trigger1", "trigger2"],
  "emergency_routing_rules": {{
    "contacts": [
      {{"name": "string", "phone": "string", "order": 1}},
      {{"name": "string", "phone": "string", "order": 2}}
    ],
    "ring_timeout_seconds": 30,
    "fallback_action": "string describing what to do if all fail"
  }},
  "non_emergency_routing_rules": "string description",
  "call_transfer_rules": {{
    "office_hours_transfer_to": "phone number or description",
    "ring_timeout": "e.g. 4 rings",
    "if_no_answer": "string"
  }},
  "integration_constraints": ["constraint1", "constraint2"],
  "after_hours_flow_summary": "brief paragraph",
  "office_hours_flow_summary": "brief paragraph",
  "questions_or_unknowns": ["question1"],
  "notes": "short freeform notes"
}}

Rules:
- Never invent data not present in the transcript.
- If something is unknown or not mentioned, use null or empty list [].
- For questions_or_unknowns, only include if genuinely ambiguous.

TRANSCRIPT:
{transcript}
"""

ONBOARDING_PATCH_PROMPT = """You are a data extraction specialist.
Given an existing account memo (JSON) and a new onboarding call transcript, produce a JSON "patch" 
that describes ONLY the changes. Do not reproduce unchanged fields.

Return ONLY valid JSON in this format:
{{
  "changes": [
    {{
      "field": "dot.path.to.field",
      "action": "update|add|remove",
      "old_value": "previous value or null",
      "new_value": "new value",
      "reason": "brief reason from transcript"
    }}
  ],
  "updated_memo": {{ ...complete updated memo with all fields... }}
}}

EXISTING MEMO:
{existing_memo}

ONBOARDING TRANSCRIPT:
{transcript}
"""


# ─── OLLAMA CALLER ────────────────────────────────────────────────────────────

def call_ollama(prompt: str) -> str:
    """Call local Ollama LLM. Returns raw text response."""
    try:
        import urllib.request
        payload = json.dumps({
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 2000}
        }).encode()
        req = urllib.request.Request(
            f"{OLLAMA_HOST}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
            return data.get("response", "")
    except Exception as e:
        print(f"[WARN] Ollama call failed: {e}")
        return ""


def extract_json_from_text(text: str) -> Optional[dict]:
    """Pull JSON block out of LLM response (handles markdown fences)."""
    # Try direct parse first
    try:
        return json.loads(text.strip())
    except Exception:
        pass
    # Try pulling from markdown code block
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            pass
    # Try finding first {...} block
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            pass
    return None


# ─── RULE-BASED FALLBACK EXTRACTOR ───────────────────────────────────────────

TIMEZONE_MAP = {
    "central": "Central Time (CT)",
    "mountain": "Mountain Time (MT)",
    "pacific": "Pacific Time (PT)",
    "eastern": "Eastern Time (ET)",
}

DAY_PATTERNS = {
    "monday": "Monday", "tuesday": "Tuesday", "wednesday": "Wednesday",
    "thursday": "Thursday", "friday": "Friday", "saturday": "Saturday", "sunday": "Sunday"
}

EMERGENCY_KEYWORDS = [
    "no heat", "no ac", "no air", "burst pipe", "flooding", "sewage backup",
    "power outage", "electrical fire", "gas leak", "refrigeration down",
    "system down", "discharge", "sprinkler", "temperature", "freezer"
]

SERVICE_KEYWORDS = [
    "hvac", "heating", "cooling", "air conditioning", "plumbing", "drain",
    "electrical", "refrigeration", "fire protection", "sprinkler", "generator",
    "maintenance", "installation", "repair", "water heater", "panel", "ev charger",
    "indoor air quality", "water softener", "hood suppression"
]


def rule_based_extract(transcript: str, call_type: str = "demo") -> dict:
    """
    Regex/keyword extraction fallback when Ollama is unavailable.
    Returns a partially-filled memo dict.
    """
    t = transcript.lower()
    lines = transcript.split("\n")

    # Company name
    company = None
    for line in lines:
        m = re.search(r"Account:\s*(.+)", line)
        if m:
            company = m.group(1).strip()
            break
    if not company:
        m = re.search(r"we(?:'re| are)\s+([A-Z][^,\.\n]+(?:LLC|Inc|Services|Solutions|Co\.|Plumbing|HVAC|Electrical|Refrigeration|Protection)?)", transcript)
        if m:
            company = m.group(1).strip()

    # Phone numbers
    phones = re.findall(r"\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b", transcript)

    # Address
    address = None
    m = re.search(r"\d{3,5}\s+[A-Z][^,\n]+(?:Road|Street|Ave|Boulevard|Blvd|Drive|Dr|Way|Suite|Rd|St)\b[^,\n]*(?:,\s*[^,\n]+){1,3}", transcript)
    if m:
        address = m.group(0).strip()

    # Timezone
    timezone = None
    for tz_key, tz_val in TIMEZONE_MAP.items():
        if tz_key in t:
            timezone = tz_val
            break

    # Business hours
    biz_hours = {"days": None, "start": None, "end": None, "timezone": timezone,
                 "saturday": None, "sunday": "Closed"}

    m = re.search(r"(monday(?:\s+through|-)\s*friday)", t)
    if m:
        biz_hours["days"] = "Monday-Friday"

    # Look for time patterns like "7 AM to 6 PM"
    time_matches = re.findall(r"(\d{1,2}(?::\d{2})?\s*[AP]M)", transcript)
    if len(time_matches) >= 2:
        biz_hours["start"] = time_matches[0]
        biz_hours["end"] = time_matches[1]

    # Saturday hours
    sat_match = re.search(r"saturday[^.]*?(\d{1,2}(?::\d{2})?\s*[AP]M)[^.]*?(\d{1,2}(?::\d{2})?\s*[AP]M)", transcript, re.IGNORECASE)
    if sat_match:
        biz_hours["saturday"] = f"{sat_match.group(1)} - {sat_match.group(2)}"

    # Services
    services = []
    for svc in SERVICE_KEYWORDS:
        if svc in t:
            services.append(svc.title())

    # Emergency definitions
    emergencies = []
    for kw in EMERGENCY_KEYWORDS:
        if kw in t:
            emergencies.append(kw.title())

    # Emergency contacts (names near phone numbers)
    contacts = []
    for i, line in enumerate(lines):
        phones_in_line = re.findall(r"\d{3}[-.\s]\d{3}[-.\s]\d{4}", line)
        if phones_in_line:
            # Look for a name in this line or adjacent line
            name_match = re.search(r"([A-Z][a-z]+\s+[A-Z][a-z]+)", line)
            name = name_match.group(1) if name_match else f"Contact {len(contacts)+1}"
            contacts.append({
                "name": name,
                "phone": phones_in_line[0],
                "order": len(contacts) + 1
            })

    # Integration constraints
    constraints = []
    for tool in ["ServiceTitan", "FieldEdge", "ServiceTrade", "Housecall Pro", "Jobber"]:
        if tool.lower() in t:
            constraints.append(f"Do not create jobs/tickets in {tool}")

    return {
        "company_name": company,
        "business_hours": biz_hours,
        "office_address": address,
        "services_supported": list(dict.fromkeys(services)),  # dedupe
        "emergency_definition": list(dict.fromkeys(emergencies)),
        "emergency_routing_rules": {
            "contacts": contacts[:3],
            "ring_timeout_seconds": 30,
            "fallback_action": "Leave voicemail and inform caller of callback timeframe"
        },
        "non_emergency_routing_rules": "Take name and phone number; follow up next business day",
        "call_transfer_rules": {
            "office_hours_transfer_to": phones[0] if phones else None,
            "ring_timeout": "4 rings",
            "if_no_answer": "Take message with name and callback number"
        },
        "integration_constraints": constraints,
        "after_hours_flow_summary": "Greet caller, determine if emergency, collect name/phone, attempt transfer or take message",
        "office_hours_flow_summary": "Greet caller, collect name and purpose, transfer to office line",
        "questions_or_unknowns": [],
        "notes": "Extracted via rule-based parser — verify with client"
    }


# ─── MAIN EXTRACTION FUNCTION ─────────────────────────────────────────────────

def extract_demo_memo(transcript: str, account_id: str) -> dict:
    """
    Extract account memo from a demo call transcript.
    Tries Ollama first, falls back to rule-based.
    """
    print(f"[INFO] Extracting memo for {account_id}...")
    memo = None

    if USE_OLLAMA:
        prompt = DEMO_EXTRACTION_PROMPT.format(transcript=transcript)
        response = call_ollama(prompt)
        if response:
            memo = extract_json_from_text(response)
            if memo:
                print(f"[INFO] LLM extraction successful for {account_id}")
            else:
                print(f"[WARN] LLM returned unparseable JSON for {account_id}, falling back")

    if not memo:
        print(f"[INFO] Using rule-based extraction for {account_id}")
        memo = rule_based_extract(transcript, "demo")

    # Always inject metadata
    memo["account_id"]  = account_id
    memo["version"]     = "v1"
    memo["created_at"]  = datetime.utcnow().isoformat() + "Z"
    memo["updated_at"]  = datetime.utcnow().isoformat() + "Z"
    memo["source_type"] = "demo_call"
    memo.setdefault("questions_or_unknowns", [])
    memo.setdefault("notes", "")

    return memo


def extract_onboarding_patch(transcript: str, existing_memo: dict) -> tuple[dict, list]:
    """
    Extract updates from onboarding transcript.
    Returns (updated_memo, list_of_changes).
    """
    account_id = existing_memo.get("account_id", "unknown")
    print(f"[INFO] Extracting onboarding updates for {account_id}...")
    changes = []

    if USE_OLLAMA:
        prompt = ONBOARDING_PATCH_PROMPT.format(
            existing_memo=json.dumps(existing_memo, indent=2),
            transcript=transcript
        )
        response = call_ollama(prompt)
        if response:
            result = extract_json_from_text(response)
            if result and "updated_memo" in result:
                updated = result["updated_memo"]
                changes  = result.get("changes", [])
                updated["version"]    = "v2"
                updated["updated_at"] = datetime.utcnow().isoformat() + "Z"
                updated["account_id"] = account_id
                print(f"[INFO] LLM onboarding patch successful for {account_id}")
                return updated, changes

    # Rule-based patch fallback
    print(f"[INFO] Using rule-based patch for {account_id}")
    updated = json.loads(json.dumps(existing_memo))  # deep copy
    changes = rule_based_patch(transcript, updated)
    updated["version"]    = "v2"
    updated["updated_at"] = datetime.utcnow().isoformat() + "Z"
    return updated, changes


def rule_based_patch(transcript: str, memo: dict) -> list:
    """
    Detect changes from onboarding transcript using pattern matching.
    Mutates memo in place. Returns list of change records.
    """
    changes = []
    lines   = transcript.split("\n")

    # New phone numbers for contacts
    new_phones = re.findall(r"(?:new number is|changed to|updated to)\s+(\d{3}[-.\s]\d{3}[-.\s]\d{4})", transcript, re.IGNORECASE)
    for phone in new_phones:
        old = memo.get("emergency_routing_rules", {}).get("contacts", [{}])[0].get("phone")
        if old and old != phone:
            if "contacts" in memo.get("emergency_routing_rules", {}):
                memo["emergency_routing_rules"]["contacts"][0]["phone"] = phone
            changes.append({
                "field": "emergency_routing_rules.contacts[0].phone",
                "action": "update",
                "old_value": old,
                "new_value": phone,
                "reason": "New on-call number provided in onboarding"
            })

    # New services mentioned
    added_services = re.findall(r"(?:added|new service line|now (?:also )?doing|new service:)\s+([^\.\n,]+)", transcript, re.IGNORECASE)
    for svc in added_services:
        svc = svc.strip()
        if svc and svc.lower() not in [s.lower() for s in memo.get("services_supported", [])]:
            memo.setdefault("services_supported", []).append(svc.title())
            changes.append({
                "field": "services_supported",
                "action": "add",
                "old_value": None,
                "new_value": svc.title(),
                "reason": "New service announced in onboarding"
            })

    # Address change
    addr_match = re.search(r"(?:new address|moved|address is now)[:\s]+(\d{3,5}\s+[A-Za-z\s]+(?:Road|Street|Ave|Blvd|Way|East|West|South|North)[^,\n]*(?:,\s*[^\n]+)*)", transcript, re.IGNORECASE)
    if addr_match:
        new_addr = addr_match.group(1).strip()
        old_addr = memo.get("office_address")
        if old_addr != new_addr:
            memo["office_address"] = new_addr
            changes.append({
                "field": "office_address",
                "action": "update",
                "old_value": old_addr,
                "new_value": new_addr,
                "reason": "Office address changed per onboarding"
            })

    # New emergency triggers
    new_triggers = re.findall(r"(?:also count as|now.*emergency|add.*emergency)[^\.\n]*:?\s+([^\.\n]+)", transcript, re.IGNORECASE)
    for trigger in new_triggers:
        trigger = trigger.strip().rstrip(".")
        if trigger and trigger.lower() not in [e.lower() for e in memo.get("emergency_definition", [])]:
            memo.setdefault("emergency_definition", []).append(trigger)
            changes.append({
                "field": "emergency_definition",
                "action": "add",
                "old_value": None,
                "new_value": trigger,
                "reason": "New emergency trigger added in onboarding"
            })

    # New contacts
    new_contacts = re.findall(r"([A-Z][a-z]+\s+[A-Z][a-z]+)(?:[,\s]+at)?\s+(\d{3}[-.\s]\d{3}[-.\s]\d{4})", transcript)
    existing_phones = {c["phone"] for c in memo.get("emergency_routing_rules", {}).get("contacts", [])}
    for name, phone in new_contacts:
        if phone not in existing_phones:
            order = len(memo.get("emergency_routing_rules", {}).get("contacts", [])) + 1
            memo.setdefault("emergency_routing_rules", {}).setdefault("contacts", []).append({
                "name": name, "phone": phone, "order": order
            })
            changes.append({
                "field": f"emergency_routing_rules.contacts[{order-1}]",
                "action": "add",
                "old_value": None,
                "new_value": {"name": name, "phone": phone, "order": order},
                "reason": "New contact added in onboarding"
            })
            existing_phones.add(phone)

    # Hour changes
    hour_change = re.search(r"(?:extended|changed|now open until|hours.*?now)[^\n]*?(\d{1,2}\s*(?:AM|PM))\s+on\s+(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)", transcript, re.IGNORECASE)
    if hour_change:
        new_time = hour_change.group(1)
        day = hour_change.group(2)
        changes.append({
            "field": f"business_hours.{day.lower()}_end",
            "action": "update",
            "old_value": memo.get("business_hours", {}).get("end"),
            "new_value": new_time,
            "reason": f"Extended hours on {day}"
        })
        if day.lower() == "friday":
            memo.setdefault("business_hours", {})["end_friday"] = new_time

    # Saturday removal
    if re.search(r"saturday.*(?:remov|no longer|not working|closed)", transcript, re.IGNORECASE):
        old = memo.get("business_hours", {}).get("saturday")
        memo.setdefault("business_hours", {})["saturday"] = None
        changes.append({
            "field": "business_hours.saturday",
            "action": "remove",
            "old_value": old,
            "new_value": None,
            "reason": "Saturday hours removed per onboarding"
        })

    # Software switch
    sw_change = re.search(r"switched?\s+from\s+(\w+(?:\s+\w+)?)\s+to\s+(\w+(?:\s+\w+)?)", transcript, re.IGNORECASE)
    if sw_change:
        old_sw = sw_change.group(1)
        new_sw = sw_change.group(2)
        old_constraints = memo.get("integration_constraints", [])
        updated = [c.replace(old_sw, new_sw) if old_sw in c else c for c in old_constraints]
        if updated != old_constraints:
            memo["integration_constraints"] = updated
            changes.append({
                "field": "integration_constraints",
                "action": "update",
                "old_value": old_constraints,
                "new_value": updated,
                "reason": f"Software switched from {old_sw} to {new_sw}"
            })

    return changes
