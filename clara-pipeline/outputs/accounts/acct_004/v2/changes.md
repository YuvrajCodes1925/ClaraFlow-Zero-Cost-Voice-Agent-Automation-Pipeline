# Changelog: acct_004 (`acct_004`)
**Date:** 2026-03-04  |  **Transition:** v1 → v2
**Summary:** 6 change(s) — 0 added, 6 updated, 0 removed

---

## 🔄 Updated
- **`emergency_routing_rules.contacts[0].phone`**
  - Old: `800-555-1000`
  - New: `312-555-0402`
  _New on-call number provided in onboarding_
- **`business_hours.saturday`**
  - Old: `9 AM - 12 PM`
  - New: `None`
  _Saturday hours removed per onboarding_
- **`integration_constraints`**
  - Old: `["Do not create jobs/tickets in FieldEdge"]`
  - New: `["Do not create jobs/tickets in ServiceTitan"]`
  _Software switched from FieldEdge to ServiceTitan_
- **`emergency_routing_rules.contacts`**
  - Old: `None`
  - New: `{"name": "Contact 1", "order": 1, "phone": "312-555-0402"}`
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