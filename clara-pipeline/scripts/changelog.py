"""
changelog.py
Generates human-readable and machine-readable changelogs between memo versions.
"""

import json
from datetime import datetime
from typing import Any


def deep_diff(old: Any, new: Any, path: str = "") -> list:
    """
    Recursively diff two JSON-like objects.
    Returns list of change records.
    """
    changes = []

    if type(old) != type(new):
        if old != new:
            changes.append({
                "field": path,
                "action": "update",
                "old_value": old,
                "new_value": new,
                "reason": "Value type changed"
            })
        return changes

    if isinstance(old, dict):
        all_keys = set(old.keys()) | set(new.keys())
        for k in all_keys:
            child_path = f"{path}.{k}" if path else k
            if k not in old:
                changes.append({
                    "field": child_path,
                    "action": "add",
                    "old_value": None,
                    "new_value": new[k],
                    "reason": "New field added"
                })
            elif k not in new:
                changes.append({
                    "field": child_path,
                    "action": "remove",
                    "old_value": old[k],
                    "new_value": None,
                    "reason": "Field removed"
                })
            else:
                changes.extend(deep_diff(old[k], new[k], child_path))

    elif isinstance(old, list):
        if old != new:
            # Detect added/removed items
            old_set = set(json.dumps(i, sort_keys=True) for i in old)
            new_set = set(json.dumps(i, sort_keys=True) for i in new)
            added   = [json.loads(i) for i in (new_set - old_set)]
            removed = [json.loads(i) for i in (old_set - new_set)]
            for item in added:
                changes.append({
                    "field": path,
                    "action": "add",
                    "old_value": None,
                    "new_value": item,
                    "reason": "Item added to list"
                })
            for item in removed:
                changes.append({
                    "field": path,
                    "action": "remove",
                    "old_value": item,
                    "new_value": None,
                    "reason": "Item removed from list"
                })
    else:
        if old != new:
            # Skip meta fields
            skip = {"updated_at", "version", "created_at"}
            field_name = path.split(".")[-1]
            if field_name not in skip:
                changes.append({
                    "field": path,
                    "action": "update",
                    "old_value": old,
                    "new_value": new,
                    "reason": "Value changed"
                })

    return changes


def generate_changelog(v1_memo: dict, v2_memo: dict,
                        v1_agent: dict, v2_agent: dict,
                        manual_changes: list = None) -> dict:
    """
    Produce a complete changelog comparing v1 → v2.
    manual_changes: list of change records from extraction (higher fidelity reasons)
    """
    account_id   = v2_memo.get("account_id", "unknown")
    company_name = v2_memo.get("company_name", "Unknown Company")

    # Deep diff memos
    auto_changes = deep_diff(v1_memo, v2_memo)

    # Merge manual (from LLM/rule extraction) + auto diff, prefer manual
    all_changes = manual_changes if manual_changes else auto_changes
    if manual_changes and auto_changes:
        # Add any auto-detected changes not in manual list
        manual_fields = {c["field"] for c in manual_changes}
        for c in auto_changes:
            if c["field"] not in manual_fields:
                all_changes.append(c)

    # Categorize changes
    categorized = {"added": [], "updated": [], "removed": []}
    for c in all_changes:
        cat = c.get("action", "update")
        if cat in categorized:
            categorized[cat].append(c)
        else:
            categorized["updated"].append(c)

    changelog = {
        "account_id":    account_id,
        "company_name":  company_name,
        "changelog_date": datetime.utcnow().isoformat() + "Z",
        "from_version":  "v1",
        "to_version":    "v2",
        "summary": {
            "total_changes": len(all_changes),
            "added":   len(categorized["added"]),
            "updated": len(categorized["updated"]),
            "removed": len(categorized["removed"])
        },
        "changes": all_changes,
        "categorized": categorized
    }

    return changelog


def render_markdown_changelog(changelog: dict) -> str:
    """
    Render a human-readable markdown changelog.
    """
    acct   = changelog["account_id"]
    name   = changelog["company_name"]
    date   = changelog["changelog_date"][:10]
    total  = changelog["summary"]["total_changes"]
    added  = changelog["summary"]["added"]
    updated = changelog["summary"]["updated"]
    removed = changelog["summary"]["removed"]

    lines = [
        f"# Changelog: {name} (`{acct}`)",
        f"**Date:** {date}  |  **Transition:** v1 → v2",
        f"**Summary:** {total} change(s) — {added} added, {updated} updated, {removed} removed",
        "",
        "---",
        "",
    ]

    if changelog["categorized"]["added"]:
        lines.append("## ✅ Added")
        for c in changelog["categorized"]["added"]:
            val = json.dumps(c["new_value"]) if isinstance(c["new_value"], (dict, list)) else c["new_value"]
            lines.append(f"- **`{c['field']}`** → `{val}`")
            lines.append(f"  _{c.get('reason', 'No reason provided')}_")
        lines.append("")

    if changelog["categorized"]["updated"]:
        lines.append("## 🔄 Updated")
        for c in changelog["categorized"]["updated"]:
            old_val = json.dumps(c["old_value"]) if isinstance(c["old_value"], (dict, list)) else c["old_value"]
            new_val = json.dumps(c["new_value"]) if isinstance(c["new_value"], (dict, list)) else c["new_value"]
            lines.append(f"- **`{c['field']}`**")
            lines.append(f"  - Old: `{old_val}`")
            lines.append(f"  - New: `{new_val}`")
            lines.append(f"  _{c.get('reason', 'No reason provided')}_")
        lines.append("")

    if changelog["categorized"]["removed"]:
        lines.append("## ❌ Removed")
        for c in changelog["categorized"]["removed"]:
            val = json.dumps(c["old_value"]) if isinstance(c["old_value"], (dict, list)) else c["old_value"]
            lines.append(f"- **`{c['field']}`** (was: `{val}`)")
            lines.append(f"  _{c.get('reason', 'No reason provided')}_")
        lines.append("")

    lines.append("---")
    lines.append("_Generated automatically by Clara Answers Pipeline_")

    return "\n".join(lines)
