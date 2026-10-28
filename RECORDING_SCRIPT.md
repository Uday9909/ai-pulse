# Recording script (5 minutes, no slides)

Setup before recording: backend venv active, `python -m app.seed`, API on :8000,
Vite on :5173, two terminal tabs (backend, shell), `AUDIT.md` open in an editor.
Do not clean the mock fixtures.

## 0:00–0:30 — Claim and the "half-trusted" note

Say: "AI Pulse tells a company how well its teams use AI. The previous developer left it
unfinished; I treated it as only half-trusted. I reproduced every problem before changing
anything."

Show: the README's product claim and the baseline line
`1 failed, 7 passed` from `baseline_pytest.txt`.

## 0:30–1:30 — The misnamed leak test

1. `git show 5e3713c:backend/tests/test_api.py` — point at
   `test_admin_cannot_see_other_org` calling `?org_id=1` (Asha's own org).
2. Show the original behavior: `curl -H "Authorization: Bearer $ASHA_NW"
   'localhost:8000/dashboard?org_id=2'` → 200 on the pre-fix code (screen recording or
   the transcript line in `AUDIT.md`).
3. Show the current test: it calls `?org_id=2` and asserts 403.
4. Run `python -m pytest tests/test_api.py -q -k other_org` → green.
5. One sentence: "I rewrote a test that asserted the wrong thing; the commit message says
   so."

## 1:30–2:15 — select-org

1. Show the membership check in `auth_routes.py`.
2. Run `python -m pytest tests/test_api.py -q -k select_org` → green (Priya 403, Ravi 200).
3. Say: "A token for an org you do not belong to should not exist, even though
   downstream endpoints already rejected it."

## 2:15–3:15 — Malformed model output

1. Open `backend/data/mock_ai_responses.json`; point at score 7, `"four"`, fenced JSON,
   unknown flags.
2. Show the earlier failure evidence from `AUDIT.md` rows 5–7: stored `7.0`, HTTP 500 for
   `"four"` and the fenced block.
3. Run `python -m pytest tests/test_scoring.py -q` → 14 passed.
4. Say: "one parametrized test, all ten fixtures, score is 1–5 or None, flags are
   allow-listed."

## 3:15–4:00 — Client request

1. As Asha, `GET /dashboard?org_id=1` → department list contains only "Other teams".
   Say: "Support is three people; it is not separately visible."
2. `top_risks` is empty: Priya's `customer_data_shared` flag is suppressed.
3. Show a visible department via `test_large_department_flags_still_appear`; its flags
   still appear.
4. Delete: login Priya, click "Delete my answers", confirm; report shows answered 0.
   Asha's dashboard count for the aggregate drops
   (`test_delete_is_reflected_on_the_dashboard`).
5. One sentence on per-org scope for multi-org users.

## 4:00–4:30 — My feature

Login Priya → Northwind → report. Point at:
`common-open: 3.0 — Useful summary but shared customer data.`
Say: "This reason was stored when the answer was scored. The page does not invent it."

## 4:30–5:00 — Deliberately left + weakest part

Say: "I left SHA-256 password hashing, wildcard CORS, the JSON dashboard, and no rate
limiting. The weakest part is the AI guard: it validates shape and ranges, not prompt
injection. And the leaked JWT key is still in git history — rotate it."

Stop. Do not add a conclusion slide.
