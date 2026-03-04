# Changelog: acct_002 (`acct_002`)
**Date:** 2026-03-04  |  **Transition:** v1 → v2
**Summary:** 5 change(s) — 0 added, 5 updated, 0 removed

---

## 🔄 Updated
- **`emergency_routing_rules.contacts[0].phone`**
  - Old: `800-555-1000`
  - New: `303-555-0202`
  _New on-call number provided in onboarding_
- **`integration_constraints`**
  - Old: `["Do not create jobs/tickets in ServiceTrade"]`
  - New: `["Do not create jobs/tickets in Housecall Pro"]`
  _Software switched from ServiceTrade to Housecall Pro_
- **`emergency_routing_rules.contacts`**
  - Old: `None`
  - New: `{"name": "Contact 1", "order": 1, "phone": "303-555-0202"}`
  _Item added to list_
- **`emergency_routing_rules.contacts`**
  - Old: `{"name": "Contact 1", "order": 1, "phone": "800-555-1000"}`
  - New: `None`
  _Item removed from list_
- **`source_type`**
  - Old: `demo_call`
  - New: `onboarding_call`
  _Value changed_

---
_Generated automatically by Clara Answers Pipeline_