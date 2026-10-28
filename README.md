# AI Pulse

AI Pulse helps a company understand how well its people use AI at work, team by team.

This branch (`safety-hardening`) fixes the highest-impact defects in the handed-over
codebase, implements the two Northwind HR requests, and adds "explain my score".

## What I found

Tenant isolation and auth:

- `backend/app/routes/dashboard.py:24` trusted the `?org_id` query parameter. Asha
  (Northwind admin) read Bluepeak with `?org_id=2` (200), and Ravi's Bluepeak-scoped
  token read Northwind.
- `backend/app/routes/auth_routes.py:33` minted a token for any `org_id` the caller
  asked for, with no Membership check.
- `backend/.env:1` was tracked with a production-looking JWT `SECRET_KEY`. I minted a
  token for user 1 with it and read `/dashboard` and `/reports/me` as Asha. The key is
  still in git history (`930dd6e`); **rotate it**. Rotation is out of scope for this
  submission; it is no longer tracked and the local copy was regenerated.
- `backend/tests/test_api.py:25` (`test_admin_cannot_see_other_org`) called `?org_id=1`
  — Asha's own org — and asserted 200. The leak was green.

Numbers and questions:

- `backend/app/routes/dashboard.py:48` divided by department members instead of scored
  answers: Support 1.67 instead of 2.5, Bluepeak Customer Care 7.0, and a department
  with one 5-answer engineer 4.5 instead of 1.8.
- `backend/app/routes/dashboard.py:48-54` gave departments with zero responses
  `0.0 / Beginner`.
- `backend/app/routes/dashboard.py:11` and `backend/app/utils.py:4` used different
  maturity thresholds (1.5/2.5/3.5 vs 2/3/4): an average of 1.8 was Beginner on the
  report and Exploring on the dashboard.
- `backend/app/services/questions.py:18` compared seniority as strings; `"lead" <
  "senior"` is true, so leads lost every senior question. This was the single failing
  baseline test.

AI output:

- `backend/app/services/scoring.py:8` called `json.loads` unguarded; line 9 stored
  score and flags unchecked. Of the 10 canned responses, score `7` was stored, `"four"`
  and the fenced block returned 500, and `probably_lying` / `made_up_flag` were stored
  and shown in top risks. A normal demo answer ("Used ChatGPT to draft a refund reply,
  then edited it.") selects the fenced mock and hung the diagnostic page.

Other: `backend/Dockerfile:6` started `main:app` (no such module), and there was no CI.

Full table with exact reproduction commands: [AUDIT.md](AUDIT.md).

## What I fixed

| Fix | Commit | Tests |
|---|---|---|
| Dashboard scoped to the token's org | d2597fc | `test_admin_cannot_see_other_org`, `test_multi_org_admin_token_is_scoped_to_selected_org`, `test_admin_can_see_own_org` |
| select-org requires a membership | 93590f0 | `test_select_org_rejects_non_member`, `test_select_org_allows_multi_org_member` |
| Model output validated before storage | 3acdbe0 | `test_malformed_mock_entries_do_not_break_submit` (all 10 entries), `test_unparseable_output_returns_scoring_failed`, `test_fenced_json_is_parsed`, `test_out_of_range_and_non_numeric_scores_become_none`, `test_unknown_flags_are_dropped` |
| Department average denominator | 4f17fc1 | `test_department_average_divides_by_scored_responses`, `test_department_with_only_unscored_responses_is_not_assessed` |
| One maturity scale | 1f3c6ae | `test_report_and_dashboard_use_the_same_maturity_scale` |
| Seniority rank map | be1195c | `test_lead_manager_gets_policy_questions`, `test_lead_engineer_gets_senior_questions` |
| Stop committing `.env`, warn on unset secret | 35dcc19 | suite runs with no committed secret |
| Container entrypoint, CI | a92b238 | `.github/workflows/test.yml` |

`test_admin_cannot_see_other_org` was rewritten to call `?org_id=2` and assert 403; the
commit message says so. It failed on the old code (200) before the fix.

Baseline: `1 failed, 7 passed`. Now: `37 passed`.

## What I deliberately left, and why

- Unsalted SHA-256 password hashing (`backend/app/auth.py:13`). Changing it invalidates
  the seeded passwords, and the demo accounts must keep `pulse123`.
- `allow_origins=["*"]` (`backend/app/main.py:12`). Needed for the Vite dev origin
  today; should be pinned per environment.
- No rate limiting on the live model path. That needs an infrastructure decision, not a
  small diff.
- `frontend/src/pages/Dashboard.jsx:15` still renders JSON. A real dashboard is a UI
  redesign, which this task forbids.
- No docker-compose. The Dockerfile entrypoint is fixed, but the image was not built
  here because Docker is not available in this environment. **NOT RUN.**
- `POST /diagnostic/submit` still accepts any question id and duplicate submissions
  (`backend/app/routes/diagnostic.py:37`). The product rules are unclear (can a user
  retake a question?), so this is deferred with a reason in `AUDIT.md`.
- The frontend has no error UI for failed requests. The 500s that reached the browser
  are fixed; the demo path no longer hits it.

## Client request

Quoted from `CLIENT_REQUEST.md`:

> 1. **No small groups on the dashboard.** If a department has fewer than 5 people who
>    completed the diagnostic, leadership must not see that department's scores or risks
>    on their own. Group them under "Other teams" or hide them, but individuals must
>    never be identifiable.
> 2. **Right to delete.** Any employee must be able to delete all their answers and
>    their report themselves, and it must disappear from every dashboard immediately.

Implemented:

- Departments with `responded < 5` are removed from `departments`. Their members and
  scores are folded into one non-attributable `"Other teams"` row, and their risk flags
  do not reach `top_risks`. A visible department's flags still appear.
- `DELETE /reports/me` deletes the `Response` rows for the selected membership only.
  The report page exposes it behind a confirmation prompt.

Delete scope: The request says "all their answers." For multi-org users this is
ambiguous. I scoped delete per-organization because deleting another tenant's data from
one session would be a cross-tenant action. Ravi deleting in Northwind leaves his
Bluepeak answers intact (`test_delete_is_per_organization`).

Questions to ask the client:

1. Per-organization or global delete? What does a multi-org consultant expect?
2. Hard delete, or soft delete for audit and recovery?
3. Does "completed" mean at least one answer, or the whole question set?
4. Should "Other teams" show a combined score, or only counts?
5. Should small-group risk flags stay suppressed entirely (current behavior), or appear
   in a separate unattributed list?

## My feature: explain my score

Problem: the report said "average 2.5, Exploring" with no way to see why. Users cannot
trust a score they cannot inspect.

`GET /reports/me` now returns `answers: [{question_id, score, reason}]` from stored
`Response` rows, and the report page lists them. No new query, model, or model call: the
reason was already written for open answers.

Demo (30 seconds): login `priya@northwind.test` → Northwind. The report shows
`common-open: 3.0 — Useful summary but shared customer data.`

Why this one: it makes stored AI output visible and auditable, and it is the smallest
feature that answers "why is my score what it is?".
Test: `test_report_includes_stored_reason_per_answer`.

## How I used AI

Claude Code (this session) for reading the repo, running the app and tests, drafting
fixes, and writing these docs. Tests were written first and run against the old code.

One place the AI was wrong: its first small-group test expected "Other teams" to hold 7
employees. The run showed 10 — Sales was also below the threshold, and Ravi is in HR.
The test caught the miscount before it was accepted. More in [AI_USAGE.md](AI_USAGE.md).

## How to run and test

Backend (Python 3.12 or 3.13; 3.14 fails to build `pydantic-core` at these pins):

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env       # optional locally; set SECRET_KEY for anything shared
python -m app.seed
uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev                 # http://localhost:5173
```

Tests:

```bash
cd backend
source .venv/bin/activate
python -m pytest -q
```

Demo accounts (password `pulse123`):

| Email | Organization(s) | Role |
|---|---|---|
| asha@northwind.test | Northwind Logistics | Admin |
| meera@bluepeak.test | Bluepeak Retail | Admin |
| ravi@consult.test | Both | Employee at Northwind, admin at Bluepeak |
| priya@northwind.test | Northwind Logistics | Employee (Support) |
| dev@northwind.test | Northwind Logistics | Employee (Engineering, lead) |

## Known weak spots

- The AI guard validates output; it is not injection-proof. A hostile model can still
  produce a plausible reason string that is stored and displayed.
- Delete is per-organization by design; "all their answers" for a multi-org user is
  unresolved pending the client answer.
- Password hashing is unchanged (unsalted SHA-256).
- The admin dashboard is still a JSON dump in the UI.
- No rate limiting on the live model path.
- The leaked JWT key remains in git history; rotate it.
- There is no automated test for the Docker image (Docker unavailable here).
