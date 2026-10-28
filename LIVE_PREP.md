# Live prep

Rule: name the weak spot before the interviewer finishes the question.

Weak spots I name first:

- The AI guard validates shape, type, range, and flag labels. It is not injection-proof.
- Delete is per-organization, by design; global delete for multi-org users is an open
  client question.
- Password hashing is unchanged (unsalted SHA-256).
- The admin dashboard is still a JSON dump.
- No rate limiting on the live model path.
- The old JWT signing key is in git history; rotate it.

## 1. What was the most serious bug?

Dashboard tenant isolation. `GET /dashboard` trusted `?org_id`; Asha's Northwind token
read Bluepeak, and Ravi's Bluepeak-admin token read Northwind. Fixed in `d2597fc`, tested
by `test_admin_cannot_see_other_org` and `test_multi_org_admin_token_is_scoped_to_selected_org`.

## 2. Why did the original test not catch it?

`test_admin_cannot_see_other_org` called `?org_id=1`, which is Asha's own org, and
asserted 200. It tested the happy path under a misleading name. I rewrote it to call
`?org_id=2` and assert 403; it failed on the old code. The commit message records the
rewrite.

## 3. What did the malformed AI data do?

Four distinct failures: score `7` stored, `"four"` caused a 500 at DB insert, the fenced
block caused a 500 at `json.loads`, and unknown flags (`probably_lying`) reached
`top_risks`. Now: fenced blocks are stripped, parse is guarded, score is coerced to an
int in 1–5 or None, flags are allow-listed, and an unparseable payload is stored as
`scoring_failed`. One parametrized test covers all ten fixtures.

## 4. How did you compute the dashboard average?

Over scored answers, not department headcount. Seeded Support: Priya scored 2 and 3, so
2.5. The old code divided 5 by 3 members and showed 1.67; Bluepeak Customer Care showed
7.0. Departments with no scored answers return null / Not assessed, not 0.0 / Beginner.

## 5. Why two maturity scales before, and what now?

`dashboard.py` used 1.5/2.5/3.5, `utils.py` used 2/3/4. An average of 1.8 was Beginner on
the report and Exploring on the dashboard. I deleted the duplicate and both call
`utils.maturity_level`; the test makes both endpoints agree at 1.8.

## 6. What was the string-comparison bug?

`questions.py` did `seniority < min_seniority`. In string order `"lead" < "senior"`, so
leads were treated as juniors and lost every senior question. Replaced with an explicit
rank map. The baseline already had a failing test for it; I added the engineering case.

## 7. How does the small-group rule work?

A department is shown only if at least five people responded. Smaller departments are
folded into one "Other teams" row (members, responder count, combined average), and their
flags are excluded from `top_risks`. A department that passes the threshold keeps full
attribution. Tests: hidden Support, suppressed Support-only flag, visible Sales flag.

## 8. Why is delete per-organization?

The request says "all their answers." For a consultant in two orgs that is ambiguous.
Deleting another tenant's rows from one session would be a cross-tenant action, so
`DELETE /reports/me` deletes only the selected membership's rows. Test:
`test_delete_is_per_organization`. I listed this as a question for the client.

## 9. What did you add, and why that?

"Explain my score": `/reports/me` returns per-answer score and the stored reason, shown
on the report page. It uses data already written at submit time, adds no model call, and
lets a user audit the number they are shown. Demo: Priya's `common-open` reason.

## 10. What would you do next?

In order: fix submit's missing role/dedupe rules (needs a product decision), replace
SHA-256 with a salted KDF while keeping demo logins working, pin CORS origins, add rate
limiting around the live model, build a real dashboard, and rotate the leaked JWT key.
