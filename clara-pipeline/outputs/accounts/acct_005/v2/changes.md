# Changelog: acct_005 (`acct_005`)
**Date:** 2026-03-04  |  **Transition:** v1 → v2
**Summary:** 6 change(s) — 0 added, 6 updated, 0 removed

---

## 🔄 Updated
- **`emergency_routing_rules.contacts[0].phone`**
  - Old: `800-555-1000`
  - New: `404-555-0502`
  _New on-call number provided in onboarding_
- **`business_hours.tuesday_end`**
  - Old: `5 PM`
  - New: `6 PM`
  _Extended hours on Tuesday_
- **`integration_constraints`**
  - Old: `["Do not create jobs/tickets in Jobber"]`
  - New: `["Do not create jobs/tickets in ServiceTrade"]`
  _Software switched from Jobber to ServiceTrade_
- **`emergency_routing_rules.contacts`**
  - Old: `None`
  - New: `{"name": "Contact 1", "order": 1, "phone": "404-555-0502"}`
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