# AI Pulse

AI Pulse helps a company see how well its people use AI at work, team by team. Employees
take a short diagnostic that adapts to their role and seniority; leadership sees
team-level results under a privacy rule that prevents individuals from being identified.

[![test](https://github.com/Uday9909/ai-pulse/actions/workflows/test.yml/badge.svg)](https://github.com/Uday9909/ai-pulse/actions/workflows/test.yml)

**Walkthrough:** _add the recording link here before submitting._

## Quick start

Backend (Python 3.12 or 3.13; 3.14 fails to build `pydantic-core` at these pins):

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"   # paste into SECRET_KEY in .env
python -m app.seed
uvicorn app.main:app --reload
```

Frontend, in a second terminal:

```bash
cd frontend
npm install
npm run dev                 # http://localhost:5173
```

Tests:

```bash
cd backend && .venv/bin/python -m pytest -q     # 60 passed
cd frontend && npm test                         # 3 passed
cd frontend && npm run build
```

### Demo accounts

Password for every account: `pulse123`.

| Account | What to look at |
|---|---|
| asha@northwind.test | Northwind admin. The dashboard is **empty by design**: every seeded team is under five responders. |
| meera@bluepeak.test | Bluepeak admin. Same hidden dashboard. |
| ravi@consult.test | Member of both orgs. Admin at Bluepeak, employee at Northwind; the token is scoped to the org you pick. |
| priya@northwind.test | Support employee. Her seeded report shows the stored reason per answer; use "Delete my answers". |
| dev@northwind.test | Engineering lead. Gets the senior engineering questions. |
| neha@northwind.test | No seeded answers. Use this account to submit a fresh open answer. |

### See a visible team

Seeded teams are all below the five-responder threshold, so the dashboard is empty. To add
a visible team:

```bash
cd backend && source .venv/bin/activate
python -m app.scripts.demo_large_org   # idempotent; does not touch app/seed.py
```

Refresh Asha's dashboard: Sales appears with six responders. Support stays hidden, and its
`customer_data_shared` flag is not in top risks.

## In three minutes

- **Found:** the dashboard trusted `?org_id` (`routes/dashboard.py:24`); `select-org` minted
  tokens without a membership (`auth_routes.py:33`); a production-looking JWT key was
  committed (`backend/.env`); model output was unvalidated (`services/scoring.py:8-9`);
  department averages divided by headcount (`dashboard.py:48`); two maturity scales
  disagreed; seniority was compared as a string (`services/questions.py:18`); the
  small-group aggregate could identify a team; repeat submissions inflated averages; the
  frontend swallowed API errors.
- **Fixed:** tenant scoping, membership-checked tokens, output validation, correct averages,
  one maturity scale, seniority ranking, JWT `exp`/`sub`, input size caps, an anonymity-safe
  small-group rule, per-org delete, salted PBKDF2 passwords with a legacy upgrade, a 32-byte
  secret, a CORS allow-list, role-scoped submissions, model input separation with
  email/phone redaction, a dashboard table, and frontend error states. Baseline was
  `1 failed, 7 passed`; now `60 passed` plus 3 frontend tests.
- **Deliberately left:** live-model rate limiting, a token-level injection classifier,
  per-org delete scope, retakes as 409 rather than replace, no docker-compose.
- **Client request:** small groups are hidden, their flags suppressed, and employees can
  delete their answers per organization.
- **Own feature:** "explain my score" shows the stored per-answer reason.
- **AI usage:** Claude Code for reading, running, and fixing; the mistakes it made are
  documented below.

## What I found

Tenant isolation and auth:

- `backend/app/routes/dashboard.py:24` trusted `?org_id`. Asha's Northwind token read
  Bluepeak (`?org_id=2` → 200), and Ravi's Bluepeak admin token read Northwind.
- `backend/app/routes/auth_routes.py:33` issued a token for any `org_id`, with no
  Membership lookup.
- `backend/.env:1` was tracked with a production-looking JWT `SECRET_KEY`. I minted a
  token with it and read `/dashboard` and `/reports/me` as Asha. The key is still in git
  history (`930dd6e`); **rotate it**. It is no longer tracked and the local copy was
  regenerated.
- `backend/tests/test_api.py:25` (`test_admin_cannot_see_other_org`) called `?org_id=1`,
  Asha's own org, and asserted 200. The leak was green.
- `backend/app/auth.py` accepted tokens without `exp` or `sub`; a missing `sub` raised
  `KeyError`.

Numbers and questions:

- `backend/app/routes/dashboard.py:48` divided by department members, not scored answers:
  Support showed 1.67 instead of 2.5, Bluepeak Customer Care 7.0, and one five-answer
  engineer's department 4.5 instead of 1.8.
- Departments with zero responses showed `0.0 / Beginner`.
- `dashboard.py:11` and `utils.py:4` used different maturity thresholds (1.5/2.5/3.5 vs
  2/3/4): 1.8 was Beginner on the report and Exploring on the dashboard.
- `services/questions.py:18` compared seniority as strings; `"lead" < "senior"`, so leads
  lost every senior question. This was the one failing baseline test.

AI output:

- `services/scoring.py:8` called `json.loads` unguarded; line 9 stored score and flags
  unchecked. Score `7` was stored, `"four"` and the fenced block returned 500, and
  `probably_lying` / `made_up_flag` reached top risks. A normal demo answer selected the
  fenced entry and hung the diagnostic page.

Privacy and lifecycle:

- The first small-group implementation showed an "Other teams" row for two responders,
  and a single hidden department would have been identifiable. Repeat submissions let one
  person inflate the average and the responder count (3.25 → 3.57 in a live repro).
- `POST /diagnostic/submit` accepted any question id, duplicates, and had no size caps.
- `frontend/src/api.js` parsed the body before checking `res.ok`, so non-JSON errors became
  "Unexpected token" and pages hung without a message.

Other: `backend/Dockerfile:6` started `main:app` (no such module), and there was no CI.

## What I fixed

| Fix | Tests |
|---|---|
| Dashboard scoped to the token's org; multi-org token cannot cross | `test_admin_cannot_see_other_org`, `test_multi_org_admin_token_is_scoped_to_selected_org`, `test_admin_can_see_own_org` |
| `select-org` requires a membership | `test_select_org_rejects_non_member`, `test_select_org_allows_multi_org_member` |
| Model output: fences stripped, guarded parse, score 1–5 or None, flag allow-list, `scoring_failed` fallback | `test_malformed_mock_entries_do_not_break_submit` (all 10 fixtures), `test_fenced_json_is_parsed`, `test_out_of_range_and_non_numeric_scores_become_none`, `test_unknown_flags_are_dropped`, `test_flags_as_a_string_are_normalized` |
| Correct department average; null when nothing is scored | `test_department_average_divides_by_scored_responses`, `test_department_with_only_unscored_responses_is_not_assessed` |
| One maturity scale; seniority rank map | `test_report_and_dashboard_use_the_same_maturity_scale`, `test_lead_manager_gets_policy_questions`, `test_lead_engineer_gets_senior_questions` |
| Small groups: hidden under five, anonymous aggregate only with five across two teams, flags suppressed | `test_seeded_dashboard_hides_all_small_groups`, `test_other_teams_shown_when_anonymous_and_five_responded`, `test_small_department_flags_are_not_in_top_risks`, `test_large_department_flags_still_appear` |
| Delete per organization, reflected immediately | `test_employee_can_delete_own_answers`, `test_delete_is_reflected_on_the_dashboard`, `test_delete_is_per_organization` |
| Repeat submissions: 409; legacy duplicates deduped | `test_resubmitting_answered_question_is_rejected`, `test_duplicate_question_in_one_payload_is_rejected`, `test_dashboard_does_not_double_count_legacy_duplicates` |
| Size caps: 20 answers, 5000 characters | `test_submit_rejects_more_than_twenty_answers`, `test_submit_rejects_an_oversized_answer` |
| Auth: salted PBKDF2 with legacy upgrade; `exp`/`sub` required; 32-byte secret; old key rejected | `test_password_hash_is_salted_and_verifies`, `test_legacy_sha256_login_is_upgraded`, `test_token_without_exp_is_rejected`, `test_token_without_sub_is_rejected`, `test_old_committed_secret_is_not_trusted`, `test_short_secret_key_is_rejected` |
| CORS allow-list; live AI config validated; role-scoped questions | config tests, `test_cannot_submit_a_question_for_another_role` |
| Model input: system rules, tag stripping, email/phone redaction | `test_prepare_answer_strips_forged_tags`, `test_prepare_answer_redacts_email_and_phone`, `test_instructions_stay_in_the_user_message` |
| Frontend: error states, dashboard table, delete button, API tests | `api.test.js` (3), manual browser check |
| Env examples, `.gitignore`, CI, Docker entrypoint | `.github/workflows/test.yml` |

`test_admin_cannot_see_other_org` was rewritten to call `?org_id=2` and assert 403; it
failed 200 vs 403 on the old code. Three tests changed with the small-group rule:
`test_admin_dashboard` (now expects no seeded rows), the org test above, and the seeded
small-group test (renamed to `test_seeded_dashboard_hides_all_small_groups`). The
assertions are stricter, not weaker.

## What I deliberately left, and why

- No rate limiting on the live model path. That needs an infrastructure decision.
- No token-level prompt-injection classifier. The live call separates rules into a system
  message, wraps and strips the answer tags, and redacts emails/phones (tested), but a
  hostile answer can still try to steer the score. The live path is not exercised here.
- Per-organization delete. "All their answers" is ambiguous for a multi-org user; the
  questions below name it.
- Retakes return 409 instead of replacing the previous submission. That keeps the
  responder count honest, but it is a product decision.
- No docker-compose. The Dockerfile entrypoint is fixed (`app.main:app`), but the image was
  not built or run here because Docker is not installed. **NOT RUN.**
- No migrations: this change adds no tables or columns, so `create_all` is enough.

## The client request

Quoted from `CLIENT_REQUEST.md`:

> 1. **No small groups on the dashboard.** If a department has fewer than 5 people who
>    completed the diagnostic, leadership must not see that department's scores or risks
>    on their own. Group them under "Other teams" or hide them, but individuals must
>    never be identifiable.
> 2. **Right to delete.** Any employee must be able to delete all their answers and
>    their report themselves, and it must disappear from every dashboard immediately.

Implemented:

- Departments with fewer than five responders are removed from `departments`. Their
  members and scores are folded into one non-attributable `"Other teams"` row, which is
  only shown when it holds at least five responders from at least two hidden departments.
  Their flags never reach `top_risks`; a visible department's flags do.
- `DELETE /reports/me` deletes the `Response` rows for the selected membership only. The
  report page exposes it behind a confirmation prompt, and the dashboard reflects it on the
  next read.
- Tests: hidden Support, suppressed Support-only flag, visible Sales flag, per-org delete
  (Ravi's Bluepeak data survives a Northwind delete), dashboard drop after delete.

Delete scope: The request says "all their answers." For multi-org users this is ambiguous.
I scoped delete per-organization because deleting another tenant's data from one session
would be a cross-tenant action. Ravi deleting in Northwind leaves his Bluepeak answers
intact (`test_delete_is_per_organization`).

### Questions for Northwind HR

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

Demo: Priya's seeded report shows `common-open: 3.0 — Useful summary but shared customer
data.` Submitting a new open answer as Neha shows the same path with a fresh score.

Why this one: it makes stored AI output visible and auditable, and it is the smallest
feature that answers "why is my score what it is?". Test:
`test_report_includes_stored_reason_per_answer`.

## Can the AI parts be trusted?

- **Output is validated.** Fenced JSON is stripped, parsing is guarded, the score is an
  integer from 1 to 5 or `None`, flags are allow-listed, and an unparseable payload is
  stored as `scoring_failed` — not a 500. Ten malformed fixtures are tested end to end.
- **Input is separated.** The live call puts the rules in a system message and the answer
  in a tagged user message; forged tags are stripped and emails/phones are redacted before
  the request (`backend/app/services/llm.py`).
- **The demo is deterministic.** `AI_MODE=mock` selects a canned response by
  `md5(answer) % 10`. No live model is called in seeded flows.
- **Limit:** there is no token-level injection classifier, and the live path is untested
  here. Validation cannot prove a reason is true; it only bounds the shape.

## How to change it safely

| Area | Where |
|---|---|
| Add or edit a question | `backend/data/questions.json` (`roles`, `min_seniority`, `type`); tests in `tests/test_questions.py` |
| Privacy rule | `SMALL_GROUP_MIN_RESPONDENTS` and the `Other teams` gate in `backend/app/routes/dashboard.py` |
| Scoring / model input | `backend/app/services/scoring.py`, `backend/app/services/llm.py` |
| Auth | `backend/app/auth.py`, `backend/app/routes/auth_routes.py` |
| UI | `frontend/src/pages/` |

Run one test:

```bash
cd backend && .venv/bin/python -m pytest tests/test_api.py -q -k other_org
```

Schema: no new tables or columns; `python -m app.seed` rebuilds demo data. There is no
migration step.

### Decisions and tradeoffs

- **Average:** over scored answers. Mean-of-per-person-means would weight each employee
  equally; scored-answers weights people who answered more. On the seeded Support data both
  agree (2.5). I chose scored answers because the dashboard is a department-level view of
  answers.
- **Small groups:** hidden rows rather than banded counts. Simpler to explain, but less
  informative than a banded "fewer than 5" display.
- **Delete:** per organization, not global.

## Verification

- Backend: `60 passed`; frontend: `3 passed`; `npm run build` succeeds.
- CI runs `pytest`, `npm test`, and the production build on every push.
- Fresh clone: follow Quick start in a temp directory; the suite and server start from a
  clean checkout with no committed `.env`.
- Baseline: `1 failed, 7 passed`; the one failure was the seniority comparison.

## How I used AI

Claude Code for reading the repository, running the app and tests, drafting fixes, and
writing documentation. Tests were written and run against the old code before each fix.

**One place it was wrong:** its first small-group test expected "Other teams" to hold 7
employees. The run showed 10 — Sales was also below the threshold, and Ravi is a Northwind
member in HR. The test caught the miscount before the assertion was accepted. The same
failure mode appeared while applying frontend error states: part of an edit batch did not
apply, and the partial result was only caught because both edits were checked before
building.

## Known limitations

- The AI guard validates output and separates input, but it is not a full injection
  classifier; a hostile model can still produce a plausible reason.
- Delete is per-organization; "all their answers" for a multi-org user is unresolved.
- No rate limiting on the live model path.
- Retakes return 409; they do not replace the previous submission.
- The leaked JWT key remains in git history; rotate it.
- Docker image not built or run here.
- The small-group aggregate is hidden rather than shown with banded counts.
