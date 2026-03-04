"""
batch_run.py
Batch processor: runs Pipeline A + B across all accounts.
Idempotent — safe to run multiple times.

Usage:
    python batch_run.py                           # uses data/ folder
    python batch_run.py --demo-dir path/to/demos --onboard-dir path/to/onboarding
    python batch_run.py --dry-run                 # just validate inputs
"""

import os
import sys
import json
import argparse
import re
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from pipeline_a import run_pipeline_a
from pipeline_b import run_pipeline_b

BASE_DIR   = Path(__file__).parent.parent
DEMO_DIR   = BASE_DIR / "data" / "demo_calls"
ONBRD_DIR  = BASE_DIR / "data" / "onboarding_calls"
OUTPUT_DIR = BASE_DIR / "outputs"

# ─── ACCOUNT-FILE MAPPING ─────────────────────────────────────────────────────
# Maps an account prefix found in filename to account_id
# Handles multi-account files like acct_004_005_demo.txt

DEMO_MANIFEST = [
    {"account_id": "acct_001", "file": "acct_001_demo.txt",       "company": "Pinnacle HVAC Services"},
    {"account_id": "acct_002", "file": "acct_002_demo.txt",       "company": "BlueSky Plumbing & Drain"},
    {"account_id": "acct_003", "file": "acct_003_demo.txt",       "company": "Summit Electrical Contractors"},
    {"account_id": "acct_004", "file": "acct_004_demo.txt",       "company": "Glacier Refrigeration & HVAC"},
    {"account_id": "acct_005", "file": "acct_005_demo.txt",       "company": "Clearwater Fire Protection"},
]

ONBOARDING_MANIFEST = [
    {"account_id": "acct_001", "file": "acct_001_onboarding.txt", "company": "Pinnacle HVAC Services"},
    {"account_id": "acct_002", "file": "acct_002_onboarding.txt", "company": "BlueSky Plumbing & Drain"},
    {"account_id": "acct_003", "file": "acct_003_onboarding.txt", "company": "Summit Electrical Contractors"},
    {"account_id": "acct_004", "file": "acct_004_onboarding.txt", "company": "Glacier Refrigeration & HVAC"},
    {"account_id": "acct_005", "file": "acct_005_onboarding.txt", "company": "Clearwater Fire Protection"},
]


# ─── TRANSCRIPT SPLITTER ──────────────────────────────────────────────────────
def extract_section(transcript: str, section_keyword: str) -> str:
    """
    Extract a specific account's section from a multi-account transcript file.
    Splits on the --- separator between accounts.
    """
    parts = re.split(r"\n---+\n", transcript)
    for part in parts:
        if section_keyword.lower() in part.lower():
            return part.strip()
    # If no section found, return whole transcript
    return transcript


def write_temp_transcript(content: str, account_id: str, pipeline: str) -> str:
    """Write a section to a temp file for pipeline processing."""
    tmp_dir  = BASE_DIR / "outputs" / "_tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_dir / f"{account_id}_{pipeline}_temp.txt"
    tmp_path.write_text(content)
    return str(tmp_path)


# ─── BATCH RUNNER ─────────────────────────────────────────────────────────────
def run_batch(demo_dir: Path = DEMO_DIR, onboard_dir: Path = ONBRD_DIR,
              dry_run: bool = False, accounts_filter: list = None):
    """
    Run all Pipeline A + B jobs.
    accounts_filter: list of account_ids to process (None = all)
    """
    results = {
        "started_at": datetime.utcnow().isoformat() + "Z",
        "pipeline_a": [],
        "pipeline_b": [],
        "summary": {}
    }

    print("\n" + "="*60)
    print("  CLARA ANSWERS — BATCH PIPELINE RUNNER")
    print("="*60)

    # ── PIPELINE A ────────────────────────────────────────────────
    print("\n[*] Phase 1: Demo Calls -> V1 Agent Specs")
    print("-" * 40)

    for entry in DEMO_MANIFEST:
        acct_id = entry["account_id"]
        if accounts_filter and acct_id not in accounts_filter:
            continue

        file_path = demo_dir / entry["file"]
        if not file_path.exists():
            print(f"  [!] SKIP {acct_id}: file not found -> {file_path}")
            results["pipeline_a"].append({"account_id": acct_id, "status": "skipped", "reason": "file_not_found"})
            continue

        # Check idempotency — skip if already done
        v1_memo_exists = (BASE_DIR / "outputs" / "accounts" / acct_id / "v1" / "memo.json").exists()
        if v1_memo_exists:
            print(f"  [+] SKIP {acct_id}: v1 already exists (idempotent)")
            results["pipeline_a"].append({"account_id": acct_id, "status": "skipped", "reason": "already_exists"})
            continue

        # Extract section for multi-account files
        full_transcript = file_path.read_text()
        section_kw = entry.get("transcript_section")
        if section_kw:
            transcript = extract_section(full_transcript, section_kw)
        else:
            transcript = full_transcript

        tmp_path = write_temp_transcript(transcript, acct_id, "demo")

        print(f"  > Running Pipeline A for {acct_id} ({entry.get('company', '')})")
        if dry_run:
            print(f"    [DRY RUN] Would process: {tmp_path}")
            results["pipeline_a"].append({"account_id": acct_id, "status": "dry_run"})
            continue

        try:
            result = run_pipeline_a(tmp_path, acct_id)
            print(f"  [+] {acct_id}: {result['company_name']} -> {result['memo_path']}")
            results["pipeline_a"].append({**result, "account_id": acct_id})
        except Exception as e:
            print(f"  ❌ {acct_id} FAILED: {e}")
            results["pipeline_a"].append({"account_id": acct_id, "status": "failed", "error": str(e)})

        time.sleep(0.5)  # Rate limit / courtesy delay

    # ── PIPELINE B ────────────────────────────────────────────────
    print("\n[*] Phase 2: Onboarding Calls -> V2 Agent Updates")
    print("-" * 40)

    for entry in ONBOARDING_MANIFEST:
        acct_id = entry["account_id"]
        if accounts_filter and acct_id not in accounts_filter:
            continue

        file_path = onboard_dir / entry["file"]
        if not file_path.exists():
            print(f"  [!] SKIP {acct_id}: onboarding file not found -> {file_path}")
            results["pipeline_b"].append({"account_id": acct_id, "status": "skipped", "reason": "file_not_found"})
            continue

        # Idempotency check
        v2_memo_exists = (BASE_DIR / "outputs" / "accounts" / acct_id / "v2" / "memo.json").exists()
        if v2_memo_exists:
            print(f"  [+] SKIP {acct_id}: v2 already exists (idempotent)")
            results["pipeline_b"].append({"account_id": acct_id, "status": "skipped", "reason": "already_exists"})
            continue

        # Check v1 exists
        v1_memo_exists = (BASE_DIR / "outputs" / "accounts" / acct_id / "v1" / "memo.json").exists()
        if not v1_memo_exists:
            print(f"  [!] SKIP {acct_id}: no v1 memo found (run Pipeline A first)")
            results["pipeline_b"].append({"account_id": acct_id, "status": "skipped", "reason": "no_v1"})
            continue

        # Extract section
        full_transcript = file_path.read_text()
        section_kw = entry.get("transcript_section")
        if section_kw:
            transcript = extract_section(full_transcript, section_kw)
        else:
            transcript = full_transcript

        tmp_path = write_temp_transcript(transcript, acct_id, "onboarding")

        print(f"  > Running Pipeline B for {acct_id}")
        if dry_run:
            print(f"    [DRY RUN] Would process: {tmp_path}")
            results["pipeline_b"].append({"account_id": acct_id, "status": "dry_run"})
            continue

        try:
            result = run_pipeline_b(tmp_path, acct_id)
            print(f"  [+] {acct_id}: {result['company_name']} -> {result['total_changes']} changes")
            results["pipeline_b"].append({**result, "account_id": acct_id})
        except Exception as e:
            print(f"  [X] {acct_id} FAILED: {e}")
            results["pipeline_b"].append({"account_id": acct_id, "status": "failed", "error": str(e)})

        time.sleep(0.5)

    # ── SUMMARY ───────────────────────────────────────────────────
    results["finished_at"] = datetime.utcnow().isoformat() + "Z"
    a_success = sum(1 for r in results["pipeline_a"] if r.get("status") == "success")
    b_success = sum(1 for r in results["pipeline_b"] if r.get("status") == "success")
    a_skip    = sum(1 for r in results["pipeline_a"] if r.get("status") == "skipped")
    b_skip    = sum(1 for r in results["pipeline_b"] if r.get("status") == "skipped")
    a_fail    = sum(1 for r in results["pipeline_a"] if r.get("status") == "failed")
    b_fail    = sum(1 for r in results["pipeline_b"] if r.get("status") == "failed")

    results["summary"] = {
        "pipeline_a": {"success": a_success, "skipped": a_skip, "failed": a_fail},
        "pipeline_b": {"success": b_success, "skipped": b_skip, "failed": b_fail},
    }

    # Save batch report
    report_path = OUTPUT_DIR / "batch_report.json"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("\n" + "="*60)
    print("  BATCH COMPLETE")
    print(f"  Pipeline A: {a_success} ok / {a_skip} skipped / {a_fail} failed")
    print(f"  Pipeline B: {b_success} ok / {b_skip} skipped / {b_fail} failed")
    print(f"  Report saved: {report_path}")
    print("="*60 + "\n")

    return results


# ─── CLI ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Batch run all pipelines")
    parser.add_argument("--demo-dir",    default=str(DEMO_DIR))
    parser.add_argument("--onboard-dir", default=str(ONBRD_DIR))
    parser.add_argument("--dry-run",     action="store_true")
    parser.add_argument("--accounts",    nargs="*", help="Filter to specific account IDs")
    args = parser.parse_args()

    run_batch(
        demo_dir        = Path(args.demo_dir),
        onboard_dir     = Path(args.onboard_dir),
        dry_run         = args.dry_run,
        accounts_filter = args.accounts,
    )
