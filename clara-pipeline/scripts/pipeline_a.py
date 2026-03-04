"""
pipeline_a.py
Pipeline A: Demo Call Transcript → Account Memo (v1) + Retell Agent Spec (v1)

Usage:
    python pipeline_a.py --input data/demo_calls/acct_001_demo.txt --account-id acct_001
    python pipeline_a.py --input data/demo_calls/acct_001_demo.txt  # auto-assigns ID
"""

import os
import sys
import json
import argparse
import hashlib
import sqlite3
from datetime import datetime
from pathlib import Path

# Ensure scripts dir is on path
sys.path.insert(0, str(Path(__file__).parent))

from extractor    import extract_demo_memo
from agent_builder import build_agent_spec

# ─── CONFIG ───────────────────────────────────────────────────────────────────
BASE_DIR     = Path(__file__).parent.parent
OUTPUTS_DIR  = BASE_DIR / "outputs" / "accounts"
DB_PATH      = BASE_DIR / "outputs" / "pipeline.db"
LOG_FILE     = BASE_DIR / "outputs" / "pipeline.log"


# ─── LOGGING ──────────────────────────────────────────────────────────────────
def log(msg: str, level: str = "INFO"):
    ts  = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"[{ts}] [{level}] {msg}"
    print(line)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


# ─── SQLITE TRACKER ───────────────────────────────────────────────────────────
def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            account_id   TEXT PRIMARY KEY,
            company_name TEXT,
            status       TEXT,
            v1_created   TEXT,
            v2_created   TEXT,
            memo_v1_path TEXT,
            memo_v2_path TEXT,
            agent_v1_path TEXT,
            agent_v2_path TEXT,
            notes        TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_runs (
            run_id       TEXT PRIMARY KEY,
            account_id   TEXT,
            pipeline     TEXT,
            input_file   TEXT,
            status       TEXT,
            started_at   TEXT,
            finished_at  TEXT,
            error        TEXT
        )
    """)
    conn.commit()
    conn.close()


def upsert_account(account_id: str, data: dict):
    conn = sqlite3.connect(DB_PATH)
    existing = conn.execute(
        "SELECT * FROM accounts WHERE account_id = ?", (account_id,)
    ).fetchone()
    if existing:
        sets   = ", ".join(f"{k} = ?" for k in data)
        values = list(data.values()) + [account_id]
        conn.execute(f"UPDATE accounts SET {sets} WHERE account_id = ?", values)
    else:
        data["account_id"] = account_id
        cols   = ", ".join(data.keys())
        placeholders = ", ".join("?" for _ in data)
        conn.execute(f"INSERT INTO accounts ({cols}) VALUES ({placeholders})", list(data.values()))
    conn.commit()
    conn.close()


def log_run(run_id: str, account_id: str, pipeline: str, input_file: str,
            status: str, started: str, finished: str = None, error: str = None):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT OR REPLACE INTO pipeline_runs
        (run_id, account_id, pipeline, input_file, status, started_at, finished_at, error)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (run_id, account_id, pipeline, input_file, status, started, finished, error))
    conn.commit()
    conn.close()


# ─── FILE I/O ─────────────────────────────────────────────────────────────────
def save_json(data: dict, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    log(f"Saved: {path}")


def load_transcript(filepath: str) -> str:
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


def generate_account_id(filepath: str) -> str:
    """Generate a stable account ID from filename if not provided."""
    name = Path(filepath).stem
    # Try to extract acct_NNN pattern
    import re
    m = re.match(r"(acct_\d+)", name)
    if m:
        return m.group(1)
    # Hash-based fallback
    h = hashlib.md5(name.encode()).hexdigest()[:6]
    return f"acct_{h}"


# ─── TASK TRACKER (GitHub Issues mock — replace with Asana/Linear if desired) ─
def create_task_item(account_id: str, company_name: str, version: str = "v1") -> dict:
    """
    Creates a tracking item. In free mode, writes to a local tasks.json file.
    Swap this function body for Asana API calls if/when available.
    """
    task_file = BASE_DIR / "outputs" / "tasks.json"
    tasks = []
    if task_file.exists():
        with open(task_file, encoding="utf-8") as f:
            try:
                tasks = json.load(f)
            except Exception:
                tasks = []

    task_id = f"TASK-{len(tasks)+1:04d}"
    task = {
        "task_id":    task_id,
        "account_id": account_id,
        "company_name": company_name,
        "title":      f"[{version.upper()}] Review agent config for {company_name}",
        "status":     "pending_review",
        "created_at": datetime.utcnow().isoformat() + "Z",
        "assignee":   "onboarding-team",
        "priority":   "high",
        "notes":      f"Auto-generated by Pipeline A. Review memo and agent spec in outputs/accounts/{account_id}/{version}/"
    }
    tasks.append(task)
    task_file.parent.mkdir(parents=True, exist_ok=True)
    with open(task_file, "w", encoding="utf-8") as f:
        json.dump(tasks, f, indent=2)

    log(f"Task created: {task_id} for {company_name}")
    return task


# ─── PIPELINE A MAIN ──────────────────────────────────────────────────────────
def run_pipeline_a(input_file: str, account_id: str = None) -> dict:
    """
    Full Pipeline A execution:
    1. Load transcript
    2. Extract account memo
    3. Build agent spec
    4. Save outputs
    5. Create task item
    6. Log to DB
    Returns: dict with paths to generated files
    """
    started_at = datetime.utcnow().isoformat() + "Z"
    run_id     = hashlib.md5(f"{input_file}{started_at}".encode()).hexdigest()[:12]

    init_db()

    if not account_id:
        account_id = generate_account_id(input_file)

    log(f"=== Pipeline A START | account={account_id} | file={input_file} ===")
    log_run(run_id, account_id, "A", input_file, "running", started_at)

    try:
        # 1. Load
        transcript = load_transcript(input_file)
        log(f"Loaded transcript: {len(transcript)} chars")

        # 2. Extract memo
        memo = extract_demo_memo(transcript, account_id)
        log(f"Memo extracted for: {memo.get('company_name')}")

        # 3. Build agent spec
        agent_spec = build_agent_spec(memo)
        log(f"Agent spec built: {agent_spec['agent_name']}")

        # 4. Save outputs
        out_dir       = OUTPUTS_DIR / account_id / "v1"
        memo_path     = out_dir / "memo.json"
        agent_path    = out_dir / "agent_spec.json"
        transcript_path = out_dir / "transcript.txt"

        save_json(memo,       memo_path)
        save_json(agent_spec, agent_path)
        # Save transcript copy
        transcript_path.parent.mkdir(parents=True, exist_ok=True)
        transcript_path.write_text(transcript, encoding="utf-8")

        # 5. Task item
        task = create_task_item(account_id, memo.get("company_name", account_id), "v1")

        # 6. DB log
        upsert_account(account_id, {
            "company_name":  memo.get("company_name", ""),
            "status":        "v1_ready",
            "v1_created":    datetime.utcnow().isoformat() + "Z",
            "memo_v1_path":  str(memo_path),
            "agent_v1_path": str(agent_path),
        })
        log_run(run_id, account_id, "A", input_file,
                "success", started_at, datetime.utcnow().isoformat() + "Z")

        log(f"=== Pipeline A COMPLETE | account={account_id} ===")

        return {
            "status":      "success",
            "account_id":  account_id,
            "company_name": memo.get("company_name"),
            "memo_path":   str(memo_path),
            "agent_path":  str(agent_path),
            "task_id":     task["task_id"],
        }

    except Exception as e:
        log(f"Pipeline A FAILED: {e}", "ERROR")
        log_run(run_id, account_id, "A", input_file,
                "failed", started_at, datetime.utcnow().isoformat() + "Z", str(e))
        raise


# ─── CLI ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pipeline A: Demo → Agent v1")
    parser.add_argument("--input",      required=True, help="Path to transcript file")
    parser.add_argument("--account-id", default=None,  help="Account ID (auto-generated if omitted)")
    args = parser.parse_args()

    result = run_pipeline_a(args.input, args.account_id)
    print("\n=== OUTPUT ===")
    print(json.dumps(result, indent=2))
