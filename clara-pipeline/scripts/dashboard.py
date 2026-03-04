"""
dashboard.py
Simple Flask dashboard for viewing pipeline outputs, diffs, and account status.
Zero-cost: runs locally.

Usage:
    pip install flask --break-system-packages
    python scripts/dashboard.py
    → Open http://localhost:5000
"""

import json
import sqlite3
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template_string, jsonify, abort

BASE_DIR    = Path(__file__).parent.parent
OUTPUTS_DIR = BASE_DIR / "outputs" / "accounts"
DB_PATH     = BASE_DIR / "outputs" / "pipeline.db"
TASK_FILE   = BASE_DIR / "outputs" / "tasks.json"

app = Flask(__name__)

# ─── HTML TEMPLATE ────────────────────────────────────────────────────────────
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Clara Answers — Pipeline Dashboard</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
           background: #f4f6fa; color: #1a1a2e; }
    header { background: #1a1a2e; color: white; padding: 20px 32px;
             display: flex; align-items: center; gap: 16px; }
    header h1 { font-size: 1.4rem; font-weight: 600; }
    header span { background: #4ade80; color: #052e16; padding: 3px 10px;
                  border-radius: 12px; font-size: 0.75rem; font-weight: 700; }
    .container { max-width: 1200px; margin: 0 auto; padding: 32px 24px; }
    .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
             gap: 16px; margin-bottom: 32px; }
    .stat { background: white; border-radius: 12px; padding: 20px 24px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.08); }
    .stat .label { font-size: 0.78rem; color: #6b7280; text-transform: uppercase;
                   letter-spacing: 0.05em; margin-bottom: 6px; }
    .stat .value { font-size: 2rem; font-weight: 700; color: #1a1a2e; }
    .stat.green .value { color: #16a34a; }
    .stat.yellow .value { color: #ca8a04; }
    .stat.red .value { color: #dc2626; }
    h2 { font-size: 1.1rem; font-weight: 600; margin-bottom: 16px; color: #374151; }
    .accounts-grid { display: grid; gap: 20px; }
    .account-card { background: white; border-radius: 12px;
                    box-shadow: 0 1px 4px rgba(0,0,0,0.08); overflow: hidden; }
    .account-header { padding: 16px 20px; background: #1a1a2e; color: white;
                      display: flex; justify-content: space-between; align-items: center; }
    .account-header h3 { font-size: 1rem; font-weight: 600; }
    .account-id { font-size: 0.75rem; color: #9ca3af; font-family: monospace; }
    .badge { padding: 3px 10px; border-radius: 10px; font-size: 0.72rem; font-weight: 700; }
    .badge.v2 { background: #4ade80; color: #052e16; }
    .badge.v1 { background: #fbbf24; color: #451a03; }
    .badge.pending { background: #e5e7eb; color: #374151; }
    .account-body { padding: 20px; display: grid;
                    grid-template-columns: 1fr 1fr; gap: 20px; }
    .section h4 { font-size: 0.8rem; font-weight: 600; color: #6b7280;
                  text-transform: uppercase; margin-bottom: 10px; }
    .field { margin-bottom: 8px; }
    .field .key { font-size: 0.78rem; color: #9ca3af; }
    .field .val { font-size: 0.88rem; color: #1a1a2e; font-weight: 500; }
    .chip { display: inline-block; background: #eff6ff; color: #1d4ed8;
            border-radius: 8px; padding: 2px 8px; font-size: 0.72rem; margin: 2px; }
    .chip.red { background: #fef2f2; color: #dc2626; }
    .changes { margin-top: 12px; }
    .change-row { display: flex; align-items: flex-start; gap: 10px;
                  padding: 8px 0; border-bottom: 1px solid #f3f4f6; font-size: 0.82rem; }
    .change-action { padding: 2px 8px; border-radius: 6px; font-size: 0.7rem;
                     font-weight: 700; white-space: nowrap; }
    .add { background: #dcfce7; color: #16a34a; }
    .update { background: #dbeafe; color: #1d4ed8; }
    .remove { background: #fee2e2; color: #dc2626; }
    .change-field { font-family: monospace; color: #6b7280; font-size: 0.75rem; }
    .change-val { color: #1a1a2e; }
    .tasks { background: white; border-radius: 12px; padding: 20px 24px;
             box-shadow: 0 1px 4px rgba(0,0,0,0.08); margin-top: 24px; }
    .task-row { display: flex; gap: 16px; align-items: center;
                padding: 10px 0; border-bottom: 1px solid #f3f4f6; font-size: 0.85rem; }
    .task-status { padding: 2px 10px; border-radius: 8px; font-size: 0.72rem; font-weight: 600; }
    .v2_ready { background: #dcfce7; color: #16a34a; }
    .pending_review { background: #fef3c7; color: #92400e; }
    footer { text-align: center; padding: 24px; color: #9ca3af; font-size: 0.78rem; }
  </style>
</head>
<body>
  <header>
    <h1>🎙️ Clara Answers — Pipeline Dashboard</h1>
    <span>LIVE</span>
  </header>

  <div class="container">
    <!-- Stats -->
    <div class="stats">
      <div class="stat green">
        <div class="label">Accounts Total</div>
        <div class="value">{{ accounts|length }}</div>
      </div>
      <div class="stat green">
        <div class="label">V2 Complete</div>
        <div class="value">{{ accounts|selectattr('status','eq','v2_ready')|list|length }}</div>
      </div>
      <div class="stat yellow">
        <div class="label">V1 Only</div>
        <div class="value">{{ accounts|selectattr('status','eq','v1_ready')|list|length }}</div>
      </div>
      <div class="stat">
        <div class="label">Pending Tasks</div>
        <div class="value">{{ tasks|selectattr('status','eq','pending_review')|list|length }}</div>
      </div>
    </div>

    <!-- Account Cards -->
    <h2>📁 Account Configurations</h2>
    <div class="accounts-grid">
      {% for a in accounts %}
      <div class="account-card">
        <div class="account-header">
          <div>
            <h3>{{ a.company_name or a.account_id }}</h3>
            <div class="account-id">{{ a.account_id }}</div>
          </div>
          <span class="badge {{ 'v2' if a.status == 'v2_ready' else ('v1' if a.status == 'v1_ready' else 'pending') }}">
            {{ a.status|upper|replace('_', ' ') }}
          </span>
        </div>
        <div class="account-body">
          <!-- V1 Info -->
          <div class="section">
            <h4>V1 — Demo Config</h4>
            {% if a.memo_v1 %}
              <div class="field">
                <div class="key">Business Hours</div>
                <div class="val">{{ a.memo_v1.business_hours.days or '—' }}
                  {{ a.memo_v1.business_hours.start or '' }}–{{ a.memo_v1.business_hours.end or '' }}
                  <small>{{ a.memo_v1.business_hours.timezone or '' }}</small>
                </div>
              </div>
              <div class="field">
                <div class="key">Address</div>
                <div class="val">{{ a.memo_v1.office_address or 'N/A' }}</div>
              </div>
              <div class="field">
                <div class="key">Services</div>
                <div class="val">
                  {% for s in (a.memo_v1.services_supported or [])[:4] %}
                    <span class="chip">{{ s }}</span>
                  {% endfor %}
                </div>
              </div>
              <div class="field">
                <div class="key">Emergency Triggers</div>
                <div class="val">
                  {% for e in (a.memo_v1.emergency_definition or [])[:3] %}
                    <span class="chip red">{{ e }}</span>
                  {% endfor %}
                </div>
              </div>
            {% else %}
              <p style="color:#9ca3af; font-size:0.85rem;">Not yet generated</p>
            {% endif %}
          </div>

          <!-- V2 Changes -->
          <div class="section">
            <h4>V2 — Onboarding Updates</h4>
            {% if a.changelog %}
              <div style="font-size:0.78rem; color:#6b7280; margin-bottom:8px;">
                {{ a.changelog.summary.total_changes }} change(s) detected
              </div>
              <div class="changes">
                {% for c in (a.changelog.changes or [])[:5] %}
                <div class="change-row">
                  <span class="change-action {{ c.action }}">{{ c.action }}</span>
                  <div>
                    <div class="change-field">{{ c.field }}</div>
                    <div class="change-val">
                      {% if c.action == 'update' %}
                        {{ c.old_value }} → {{ c.new_value }}
                      {% elif c.action == 'add' %}
                        + {{ c.new_value }}
                      {% else %}
                        - {{ c.old_value }}
                      {% endif %}
                    </div>
                  </div>
                </div>
                {% endfor %}
              </div>
            {% elif a.status == 'v2_ready' %}
              <p style="color:#16a34a; font-size:0.85rem;">✓ Updated (no changes logged)</p>
            {% else %}
              <p style="color:#9ca3af; font-size:0.85rem;">Onboarding not yet processed</p>
            {% endif %}
          </div>
        </div>
      </div>
      {% endfor %}
    </div>

    <!-- Task Tracker -->
    <div class="tasks">
      <h2>📌 Task Tracker</h2>
      {% for t in tasks %}
      <div class="task-row">
        <span class="task-status {{ t.status }}">{{ t.status|replace('_', ' ') }}</span>
        <strong>{{ t.task_id }}</strong>
        <span>{{ t.title }}</span>
        <span style="margin-left:auto; color:#9ca3af; font-size:0.75rem;">{{ t.created_at[:10] }}</span>
      </div>
      {% endfor %}
      {% if not tasks %}
      <p style="color:#9ca3af;">No tasks yet. Run the pipeline first.</p>
      {% endif %}
    </div>
  </div>

  <footer>Clara Answers Pipeline Dashboard · Generated {{ now }}</footer>

  <script>
    // Auto-refresh every 30 seconds
    setTimeout(() => location.reload(), 30000);
  </script>
</body>
</html>
"""


# ─── DATA LOADER ──────────────────────────────────────────────────────────────
def load_accounts():
    accounts = []
    if not OUTPUTS_DIR.exists():
        return accounts

    for acct_dir in sorted(OUTPUTS_DIR.iterdir()):
        if not acct_dir.is_dir():
            continue
        acct_id = acct_dir.name
        row = {"account_id": acct_id, "status": "pending",
               "company_name": acct_id, "memo_v1": None, "memo_v2": None, "changelog": None}

        # Load v1 memo
        v1_memo_path = acct_dir / "v1" / "memo.json"
        if v1_memo_path.exists():
            with open(v1_memo_path) as f:
                row["memo_v1"] = json.load(f)
            row["company_name"] = row["memo_v1"].get("company_name", acct_id)
            row["status"] = "v1_ready"

        # Load v2 memo + changelog
        v2_memo_path = acct_dir / "v2" / "memo.json"
        if v2_memo_path.exists():
            with open(v2_memo_path) as f:
                row["memo_v2"] = json.load(f)
            row["status"] = "v2_ready"

        changelog_path = acct_dir / "v2" / "changes.json"
        if changelog_path.exists():
            with open(changelog_path) as f:
                row["changelog"] = json.load(f)

        accounts.append(row)
    return accounts


def load_tasks():
    if not TASK_FILE.exists():
        return []
    with open(TASK_FILE) as f:
        return json.load(f)


# ─── ROUTES ───────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    accounts = load_accounts()
    tasks    = load_tasks()
    return render_template_string(
        DASHBOARD_HTML,
        accounts=accounts,
        tasks=tasks,
        now=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    )


@app.route("/api/accounts")
def api_accounts():
    return jsonify(load_accounts())


@app.route("/api/account/<account_id>")
def api_account(account_id):
    acct_dir = OUTPUTS_DIR / account_id
    if not acct_dir.exists():
        abort(404)
    data = {"account_id": account_id}
    for version in ["v1", "v2"]:
        memo_path = acct_dir / version / "memo.json"
        agent_path = acct_dir / version / "agent_spec.json"
        if memo_path.exists():
            data[f"memo_{version}"] = json.loads(memo_path.read_text())
        if agent_path.exists():
            data[f"agent_{version}"] = json.loads(agent_path.read_text())
    cl = acct_dir / "v2" / "changes.json"
    if cl.exists():
        data["changelog"] = json.loads(cl.read_text())
    return jsonify(data)


@app.route("/api/tasks")
def api_tasks():
    return jsonify(load_tasks())


if __name__ == "__main__":
    print("🚀 Starting Clara Pipeline Dashboard at http://localhost:5000")
    app.run(debug=True, port=5000)
