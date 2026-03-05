# Changelog: acct_001 (`acct_001`)
**Date:** 2026-03-05  |  **Transition:** v1 → v2
**Summary:** 5 change(s) — 0 added, 5 updated, 0 removed

---

## 🔄 Updated
- **`emergency_routing_rules.contacts[0].phone`**
  - Old: `800-555-1000`
  - New: `214-555-0102`
  _New on-call number provided in onboarding_
- **`integration_constraints`**
  - Old: `["Do not create jobs/tickets in ServiceTitan"]`
  - New: `["Do not create jobs/tickets in FieldEdge"]`
  _Software switched from ServiceTitan to FieldEdge_
- **`source_type`**
  - Old: `demo_call`
  - New: `onboarding_call`
  _Value changed_
- **`emergency_routing_rules.contacts`**
  - Old: `None`
  - New: `{"name": "Contact 1", "order": 1, "phone": "214-555-0102"}`
  _Item added to list_
- **`emergency_routing_rules.contacts`**
  - Old: `{"name": "Contact 1", "order": 1, "phone": "800-555-1000"}`
  - New: `None`
  _Item removed from list_

---
_Generated automatically by Clara Answers Pipeline_