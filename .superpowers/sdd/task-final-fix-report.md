# Final Review Fix Report

## 2026-08-05

- Fixed exact duplicate lookup to prefer `active`, then `pending_review`, then other statuses, with newest rows first and a one-row limit. Inactive duplicates remain intentionally allowed so regenerated rejected/disabled AI questions can create a reviewable replacement.
- Added repeat find/create/assemble coverage for two rows sharing a normalized stem.
- Hardened image upload with a 5 MiB streaming cap, JPEG/PNG/WebP allowlist, magic-byte validation, partial-file cleanup, and an opaque relative `storage_key` response.
- Released the bank-selection transaction before the LLM call.
- AI ingest now prefers staff attribution but falls back to the student, then another organization user; the machine-actor bypass is explicit and restricted to same-org AI items.
- Added Alembic revision `c2d3e4f5a6b7` with selection and normalized-stem lookup indexes. No unique index was added because inactive same-stem rows are intentional; lookup is deterministic and never assumes uniqueness.

Verification:

- `/Users/bytedance/cursor/AITeacher/backend/.venv/bin/python -m pytest tests/test_question_bank_service.py tests/test_self_test_assembler.py tests/test_question_ocr.py tests/test_question_bank_api.py -q --tb=short`
  - `21 passed, 2 warnings in 3.01s`
- New regression subset: `5 passed, 2 warnings in 1.42s`
- `/Users/bytedance/cursor/AITeacher/backend/.venv/bin/alembic heads`
  - `c2d3e4f5a6b7 (head)`
- `git diff --check`
  - passed
- Frontend OCR test was attempted, but this worktree lacked `node_modules`; `npm ci` failed in npm itself with `Exit handler never called`.

## Final review follow-up

- Weak-node and weekly-focus resolution now roll back the session and log the exception before falling back to an empty targeting set.
- Added a regression test proving bank selection still returns an organization L3 item after weak-node resolution leaves the simulated transaction requiring rollback.
- `/Users/bytedance/cursor/AITeacher/backend/.venv/bin/python -m pytest tests/test_self_test_assembler.py -q`
  - `12 passed, 2 warnings in 0.90s`
