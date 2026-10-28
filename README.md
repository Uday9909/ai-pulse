# AI Pulse

AI Pulse helps a company understand how well its people use AI at work, team by team.

This branch (`safety-hardening`) fixes the highest-impact defects in the handed-over
codebase, implements the two Northwind HR requests, and adds "explain my score".

## In three minutes

- **Found:** dashboard trusted `?org_id` (`routes/dashboard.py:24`) and any admin could
  read another tenant; `select-org` minted tokens without a membership
  (`auth_routes.py:33`); a production-looking JWT key was committed (`backend/.env`);
  model output was unvalidated (`services/scoring.py:8-9`); department averages divided
  by headcount (`dashboard.py:48`); two maturity scales disagreed; seniority was compared
  as a string (`questions.py:18`).
- **Fixed:** tenant scoping, membership-checked tokens, output validation, averages,
  one maturity scale, seniority ranking, JWT claim requirements, input size caps, an
  anonymity-safe small-group rule, per-org delete, salted PBKDF2 passwords with a legacy
  upgrade, a 32-byte secret requirement, a CORS allow-list, role-scoped submissions,
  model input separation with email/phone redaction, a dashboard table, and frontend error
  states. Tests went from 1 failed / 7 passed to 60 passed.
- **Deliberately left:** no live-model rate limiting, no token-level prompt-injection
  classifier (separation and redaction only), per-org delete scope, no docker-compose.
- **Client request:** small groups are hidden and their flags suppressed; employees can
  delete their answers per organization.
- **Own feature:** "explain my score" shows the stored per-answer reason.
- **AI usage:** Claude Code for reading, running, and fixing; the mistake it made is below.

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

**SECRET_KEY.** A production-looking `SECRET_KEY` was committed in `backend/.env` at
`930dd6e`. It is in git history and, if the repo is public, effectively public. Anyone
can forge a JWT for any user. I untracked it, added it to `.gitignore`, and require it to
be set from `.env`; the app refuses to start with no value. **I did not rewrite history.**
The key must be revoked by whoever owns the deployment. I generated a fresh local key for
my environment. `test_auth.py::test_old_committed_secret_is_not_trusted` proves the old
value is rejected.

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
| Salted PBKDF2 passwords, legacy upgrade, 32-byte secret, CORS allow-list, role-scoped submits, model input separation/redaction, dashboard table | 2d72285 | `test_password_hash_is_salted_and_verifies`, `test_legacy_sha256_login_is_upgraded`, `test_short_secret_key_is_rejected`, `test_cannot_submit_a_question_for_another_role`, `test_prepare_answer_strips_forged_tags`, `test_prepare_answer_redacts_email_and_phone`, `test_instructions_stay_in_the_user_message` |

`test_admin_cannot_see_other_org` was rewritten to call `?org_id=2` and assert 403; the
commit message says so. It failed on the old code (200) before the fix.

Baseline: `1 failed, 7 passed`. Now: `60 passed`.

Three tests were rewritten because the small-group rule changed expected department
lists: `test_admin_dashboard` (now expects no rows on seeded data),
`test_admin_cannot_see_other_org` (now calls `?org_id=2` and asserts 403), and the seeded
small-group test (renamed to `test_seeded_dashboard_hides_all_small_groups`). The
assertions are stricter, not weaker. Inspect with
`git show 9765d86 -- backend/tests/` and `git show d2597fc -- backend/tests/`.

## What I deliberately left, and why

- No rate limiting on the live model path. That needs an infrastructure decision, not a
  small diff.
- No token-level prompt-injection classifier. The live call separates rules into a system
  message, wraps and strips the answer tags, and redacts emails/phones, but a hostile
  answer can still try to steer the score. The live path is not exercised in the demo.
- Per-organization delete. "All their answers" for a multi-org user is ambiguous; the
  client questions below name it.
- No docker-compose. Dockerfile entrypoint fixed (`app.main:app`); the image was not
  built or run here because Docker is not installed. **NOT RUN.**
- Retakes: a second submission is 409 rather than replacing the previous one. That keeps
  the five-responder count honest, but it is a product decision worth confirming.

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
The test caught the miscount before it was accepted. The same thing happened while
applying frontend error states: part of an edit batch did not apply, and the partial
result was only visible because both edits were checked before building.

## How to run and test

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

### How to see a visible department

All seeded departments are below the client's five-responder threshold, so the seeded
dashboard is **empty by design**. To populate one, run:

```bash
python -m app.scripts.demo_large_org   # from backend, venv active
```

It adds five responders to Northwind Sales (idempotent, does not modify `app/seed.py`).
Then log in as `asha@northwind.test` → Northwind: Sales appears with six responders.
The script prints the demo logins it creates.

Demo accounts (password `pulse123`):

| Email | Organization(s) | Role |
|---|---|---|
| asha@northwind.test | Northwind Logistics | Admin |
| meera@bluepeak.test | Bluepeak Retail | Admin |
| ravi@consult.test | Both | Employee at Northwind, admin at Bluepeak |
| priya@northwind.test | Northwind Logistics | Employee (Support) |
| dev@northwind.test | Northwind Logistics | Employee (Engineering, lead) |

## Change guide

- **Add a question:** `backend/data/questions.json` — `roles`, `min_seniority`, `type`; the
  tests live in `backend/tests/test_questions.py`.
- **Privacy rule:** `SMALL_GROUP_MIN_RESPONDENTS` and the `Other teams` gate in
  `backend/app/routes/dashboard.py`.
- **Scoring rules:** `backend/app/services/scoring.py` (parse, clamp, allow-list) and
  `backend/app/services/llm.py` (prompt, tag handling, redaction).
- **Auth:** `backend/app/auth.py` (PBKDF2, JWT) and `backend/app/routes/auth_routes.py`
  (login, organization selection).
- **Run one test:**
  `cd backend && .venv/bin/python -m pytest tests/test_api.py -q -k other_org`.
- **Schema:** this branch adds no tables or columns, so `create_all` is enough;
  `python -m app.seed` rebuilds the demo data.

## Evidence

- CI runs `pytest`, `npm test`, and `npm run build` on every push:
  see the Actions tab of the repository.
- Local final state: backend `60 passed`, frontend `3 passed`, production build succeeds.
- Fresh clone: follow the run instructions below in a temp directory; tests and the
  server start from a clean checkout (no committed `.env`).
- Deliberate gaps are listed above and in [AUDIT.md](AUDIT.md).

## Averages

I average over scored answers. Mean-of-per-person-means would weight each employee
equally; scored-answers weights employees who answered more questions more. I chose
scored-answers because the dashboard is a department-level view of answers. On the
seeded Support data both methods agree (2.5). Tradeoff noted.

## AI mode

The demo runs in `AI_MODE=mock`: scores come from `backend/data/mock_ai_responses.json`
selected by `md5(answer) % 10`. There is no live model call in the seeded flows. The live
path has output validation (fences, clamp 1–5, flag allow-list, parse-failure fallback)
and input separation (system rules, tagged answer, email/phone redaction). It does not
have a token-level injection classifier, and the live call is not exercised in the demo.

## Known weak spots

- The AI guard validates output and separates input, but it is not a full injection
  classifier. A hostile model can still produce a plausible reason string that is stored.
- Delete is per-organization by design; "all their answers" for a multi-org user is
  unresolved pending the client answer.
- No rate limiting on the live model path.
- The leaked JWT key remains in git history; rotate it.
- There is no automated test for the Docker image (Docker unavailable here).
