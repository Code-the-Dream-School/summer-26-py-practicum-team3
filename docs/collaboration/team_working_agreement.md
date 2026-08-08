# Team Working Agreement — DRAFT

> **Status:** Mentor rough draft. This is a starting point, not a final answer — a student should read
> through it, resolve the **Open questions** in each section with the team, and turn this into the team's
> actual Sprint 1 working agreement deliverable. Delete this status note once the doc is finalized.

This agreement covers how Team 3 divides roles, communicates blockers, reviews code, rotates
responsibilities, and keeps work moving during the practicum. See
[`github_feature_branch_pr_guide.md`](./github_feature_branch_pr_guide.md) and
[`pr_review_best_practices.md`](./pr_review_best_practices.md) for the mechanics referenced below.

## 1. Communication

- Primary channel: Slack, `#summer26-python-practicum-team3`.
- Weekly team meeting: Saturdays at 4:30pm ET.
- Post a work update in-channel whenever work moves state (started/blocked/ready for review) or whenever
  a PR needs review.
- Keep an eye on your GH inbox
- the Saturday meeting mandatory for everyone. Let us know ahead of time if you cannot make it.


## 2. Dividing roles and responsibilities

-  by ticket, self-selected per sprint:** students pick up `AIR-###` tickets each sprint
  regardless of stage, so everyone touches multiple areas over time.
- assignments are set during weekly sprint planning
  
## 3. Raising and handling blockers

- in the team slack channel and tag team members individually or @everyone
- if students internally are unable to resolve blocker by Weds, escalate to mentors


## 4. Code review

- Minimum reviewers before merge: **1 teammate approval**, plus a **mentor acting as merge master** —
  the mentor gives a final sign-off before work lands on `main` in addition to the teammate review.
- Required CI checks: see `.github/workflows/` (`python-quality-gates.yml` for tests/compile,
  `air-ticket-check.yml` for PR title format). `lint-checks.yml` (ruff/pyright) is advisory-only and does
  not gate merging.
- Ticket moving to review status deadline is Weds
- Slack ping when PR is ready for student or mentor review
- give 24 hrs for a student to start review then inform mentor


## 5. Keeping work moving

- if you will be slow in developing your work before Weds deadline, please speak up in slack channel and team can support you
-  review progress at team weekly meeting and update this document's process as necessary
