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
- Weekly team meeting: Saturdays at 4:00pm ET.
- Post a work update in-channel whenever work moves state (started/blocked/ready for review) or whenever
  a PR needs review.

**Open questions for the team:**
- What counts as "moves" for an update — every commit, every status change, or just start/blocked/done?
- Is the Saturday meeting mandatory for everyone, and what happens if someone can't make it?
- What's the expected response time to an in-channel review request or blocker post (same day? within
  24 hours?) — Sprint 1 asks the team to define this explicitly.

## 2. Dividing roles and responsibilities

Two starting options to choose between (or adapt):

- **Option A — by pipeline stage:** each student owns a stage (extract / transform / load / dashboard)
  consistently across sprints.
- **Option B — by ticket, self-selected per sprint:** students pick up `AIR-###` tickets each sprint
  regardless of stage, so everyone touches multiple areas over time.

**Open questions for the team:**
- Which option (or hybrid) does the team want, and why?
- Who decides ticket/stage assignment each sprint — self-signup, team lead, or mentor input?
- How does the team handle uneven workload if one stage/ticket set turns out bigger than another?

## 3. Raising and handling blockers

**Open questions for the team:**
- Where do blockers get posted — same Slack channel, a dedicated thread, or something else?
- What information should a blocker post include (what's blocked, what's been tried, who's needed)?
- At what point does a blocker escalate to the mentor, and how?
- Should blockers also get flagged at the Saturday meeting even if already posted in Slack?

## 4. Code review

- Minimum reviewers before merge: **1 teammate approval**, plus a **mentor acting as merge master** —
  the mentor gives a final sign-off before work lands on `main` in addition to the teammate review.
- Required CI checks: see `.github/workflows/` (`python-quality-gates.yml` for tests/compile,
  `air-ticket-check.yml` for PR title format). `lint-checks.yml` (ruff/pyright) is advisory-only and does
  not gate merging.

**Open questions for the team:**
- Should CI passing (`python-quality-gates`, `air-ticket-check`) be a hard requirement before requesting
  the mentor's merge sign-off, or just before requesting teammate review?
- How is the mentor merge-master step actually triggered — a Slack ping, a GitHub review request, a
  label?
- How quickly should a teammate respond to a review request (Sprint 1 asks the team to set this
  explicitly)?
- What happens if a PR gets requested changes — does the same reviewer re-review, or can anyone?

## 5. Rotating roles and learning opportunities

**Open questions for the team:**
- Should roles (e.g. PR reviewer, note-taker, pipeline-stage owner) rotate on a fixed cadence (e.g. every
  sprint), or organically as interests/gaps come up?
- How does the team make sure less-familiar members get exposure to unfamiliar parts of the stack
  (e.g. PostgreSQL/SQLAlchemy vs. the React dashboard) rather than the same people always taking the same
  work?
- Who tracks whether rotation is actually happening?

## 6. Keeping work moving

**Open questions for the team:**
- How does the team avoid PRs sitting unreviewed — a max time-in-review target, a round-robin reviewer
  assignment, something else?
- What's the process when a ticket stalls mid-sprint (reassign, pair up, flag to mentor)?
- How does the team keep this document itself up to date as the practicum progresses (per the Sprint 2
  checkpoint guidance to revisit working agreements each sprint)?
