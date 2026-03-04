"""
pipeline_b.py
Pipeline B: Onboarding Call Transcript → Updated Memo (v2) + Agent Spec (v2) + Changelog

Usage:
    python pipeline_b.py --input data/onboarding_calls/acct_001_onboarding.txt --account-id acct_001
"""

import os
import sys
import json
import argparse
import hashlib
import sqlite3
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from extractor     import extract_onboarding_patch
from agent_builder import build_agent_spec
from changelog     import generate_changelog, render_markdown_changelog

BASE_DIR    = Path(__file__).parent.parent
OUTPUTS_DIR = BASE_DIR / "outputs" / "accounts"
DB_PATH     = BASE_DIR / "outputs" / "pipeline.db"
LOG_FILE    = BASE_DIR / "outputs" / "pipeline.log"


# ─── LOGGING ──────────────────────────────────────────────────────────────────
def log(msg: str, level: str = "INFO"):
    ts   = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"[{ts}] [{level}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


# ─── DB HELPERS ───────────────────────────────────────────────────────────────
def get_db_account(account_id: str) -> dict:
    if not DB_PATH.exists():
        return {}
    conn = sqlite3.connect(DB_PATH)
    row  = conn.execute(
        "SELECT * FROM accounts WHERE account_id = ?", (account_id,)
    ).fetchone()
    conn.close()
    if not row:
        return {}
    cols = ["account_id","company_name","status","v1_created","v2_created",
            "memo_v1_path","memo_v2_path","agent_v1_path","agent_v2_path","notes"]
    return dict(zip(cols, row))


def update_db_account(account_id: str, data: dict):
    if not DB_PATH.exists():
        return
    conn = sqlite3.connect(DB_PATH)
    sets   = ", ".join(f"{k} = ?" for k in data)
    values = list(data.values()) + [account_id]
    conn.execute(f"UPDATE accounts SET {sets} WHERE account_id = ?", values)
    conn.commit()
    conn.close()


def log_run(run_id, account_id, pipeline, input_file, status, started, finished=None, error=None):
    if not DB_PATH.exists():
        return
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT OR REPLACE INTO pipeline_runs
        (run_id, account_id, pipeline, input_file, status, started_at, finished_at, error)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (run_id, account_id, pipeline, input_file, status, started, finished, error))
    conn.commit()
    conn.close()


# ─── TASK UPDATE ──────────────────────────────────────────────────────────────
def update_task_item(account_id: str, company_name: str):
    task_file = BASE_DIR / "outputs" / "tasks.json"
    if not task_file.exists():
        return
    with open(task_file) as f:
        tasks = json.load(f)
    updated = False
    for t in tasks:
        if t["account_id"] == account_id and t["status"] == "pending_review":
            t["status"] = "v2_ready"
            t["updated_at"] = datetime.utcnow().isoformat() + "Z"
            t["notes"] += f"\nOnboarding complete. V2 config available."
            updated = True
    if not updated:
        tasks.append({
            "task_id": f"TASK-{len(tasks)+1:04d}",
            "account_id": account_id,
            "company_name": company_name,
            "title": f"[V2] Onboarding complete — review updated config for {company_name}",
            "status": "v2_ready",
            "created_at": datetime.utcnow().isoformat() + "Z",
            "assignee": "onboarding-team",
            "priority": "medium",
        })
    with open(task_file, "w") as f:
        json.dump(tasks, f, indent=2)


# ─── PIPELINE B MAIN ──────────────────────────────────────────────────────────
def run_pipeline_b(input_file: str, account_id: str) -> dict:
    """
    Full Pipeline B execution:
    1. Load onboarding transcript
    2. Load existing v1 memo
    3. Extract patch / generate v2 memo
    4. Build v2 agent spec
    5. Generate changelog
    6. Save all outputs
    7. Update task tracker
    Returns: dict with paths to generated files
    """
    started_at = datetime.utcnow().isoformat() + "Z"
    run_id     = hashlib.md5(f"{input_file}{started_at}".encode()).hexdigest()[:12]

    log(f"=== Pipeline B START | account={account_id} | file={input_file} ===")
    log_run(run_id, account_id, "B", input_file, "running", started_at)

    try:
        # 1. Load onboarding transcript
        with open(input_file, "r", encoding="utf-8") as f:
            transcript = f.read()
        log(f"Loaded onboarding transcript: {len(transcript)} chars")

        # 2. Load v1 memo
        v1_memo_path = OUTPUTS_DIR / account_id / "v1" / "memo.json"
        if not v1_memo_path.exists():
            raise FileNotFoundError(
                f"V1 memo not found at {v1_memo_path}. Run Pipeline A first."
            )
        with open(v1_memo_path) as f:
            v1_memo = json.load(f)
        log(f"Loaded v1 memo for: {v1_memo.get('company_name')}")

        v1_agent_path = OUTPUTS_DIR / account_id / "v1" / "agent_spec.json"
        with open(v1_agent_path) as f:
            v1_agent = json.load(f)

        # 3. Extract updates → v2 memo
        v2_memo, manual_changes = extract_onboarding_patch(transcript, v1_memo)
        v2_memo["version"]     = "v2"
        v2_memo["source_type"] = "onboarding_call"
        log(f"V2 memo generated. Changes detected: {len(manual_changes)}")

        # 4. Build v2 agent spec
        v2_agent = build_agent_spec(v2_memo)
        v2_agent["version"] = "v2"
        log(f"V2 agent spec built")

        # 5. Generate changelog
        changelog_data = generate_changelog(v1_memo, v2_memo, v1_agent, v2_agent, manual_changes)
        changelog_md   = render_markdown_changelog(changelog_data)
        log(f"Changelog generated: {changelog_data['summary']['total_changes']} changes")

        # 6. Save outputs
        out_dir = OUTPUTS_DIR / account_id / "v2"
        out_dir.mkdir(parents=True, exist_ok=True)

        memo_path    = out_dir / "memo.json"
        agent_path   = out_dir / "agent_spec.json"
        cl_json_path = out_dir / "changes.json"
        cl_md_path   = out_dir / "changes.md"

        with open(memo_path, "w", encoding="utf-8")    as f: json.dump(v2_memo, f, indent=2)
        with open(agent_path, "w", encoding="utf-8")   as f: json.dump(v2_agent, f, indent=2)
        with open(cl_json_path, "w", encoding="utf-8") as f: json.dump(changelog_data, f, indent=2)
        with open(cl_md_path, "w", encoding="utf-8")   as f: f.write(changelog_md)

        # Also save to top-level changelog dir
        cl_global_path = BASE_DIR / "changelog" / f"{account_id}_v1_to_v2.md"
        cl_global_path.parent.mkdir(exist_ok=True)
        cl_global_path.write_text(changelog_md, encoding="utf-8")

        # Save onboarding transcript
        (out_dir / "transcript.txt").write_text(transcript)

        log(f"All v2 outputs saved to: {out_dir}")

        # 7. Update task tracker
        update_task_item(account_id, v2_memo.get("company_name", account_id))

        # 8. Update DB
        update_db_account(account_id, {
            "status":        "v2_ready",
            "v2_created":    datetime.utcnow().isoformat() + "Z",
            "memo_v2_path":  str(memo_path),
            "agent_v2_path": str(agent_path),
        })
        log_run(run_id, account_id, "B", input_file,
                "success", started_at, datetime.utcnow().isoformat() + "Z")

        log(f"=== Pipeline B COMPLETE | account={account_id} ===")

        return {
            "status":        "success",
            "account_id":    account_id,
            "company_name":  v2_memo.get("company_name"),
            "memo_v2_path":  str(memo_path),
            "agent_v2_path": str(agent_path),
            "changes_json":  str(cl_json_path),
            "changes_md":    str(cl_md_path),
            "total_changes": changelog_data["summary"]["total_changes"],
        }

    except Exception as e:
        log(f"Pipeline B FAILED: {e}", "ERROR")
        log_run(run_id, account_id, "B", input_file,
                "failed", started_at, datetime.utcnow().isoformat() + "Z", str(e))
        raise


# ─── CLI ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pipeline B: Onboarding → Agent v2")
    parser.add_argument("--input",      required=True, help="Path to onboarding transcript")
    parser.add_argument("--account-id", required=True, help="Account ID (must match existing v1)")
    args = parser.parse_args()

    result = run_pipeline_b(args.input, args.account_id)
    print("\n=== OUTPUT ===")
    print(json.dumps(result, indent=2))
