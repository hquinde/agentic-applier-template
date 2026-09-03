# tracker/

# Purpose

- State for the job pipeline in [scripts/](../scripts/CLAUDE.md). Not hand-edited — written by [../scripts/fetch.py](../scripts/fetch.py), [../scripts/mark_applied.py](../scripts/mark_applied.py), and [../scripts/mark_unmatched.py](../scripts/mark_unmatched.py). A job lives in exactly one of the six files below at a time — its file *is* its status/category/region, there's no field to filter on.

# State

- [ny-internships.json](ny-internships.json) — the active pool of unprocessed internship listings in New York City or New York State (excl. NYC), as records `{url, company, role}`. `fetch.py` upserts new listings here on every run; `mark_applied.py`/`mark_unmatched.py` remove a record from here when marking it.
- [ny-fulltime.json](ny-fulltime.json) — same as above, for new-grad/full-time listings.
- [applied.json](applied.json) — flat list of applied job URLs (strings, not records — once applied, the metadata isn't needed anymore). NY-only, since the applier workflow itself is NY-only.
- [unmatched.json](unmatched.json) — flat list of URLs for roles judged not a fit, skipped permanently (also bare strings). Shared across regions — both NY and `other-*` non-fits land here, since both get the same AI/SWE fit review.
- [other-internships.json](other-internships.json) — records `{url, company, role, location}` for internship listings outside New York. Gets the same AI/SWE fit review as the NY files (non-fits move to `unmatched.json` via `mark_unmatched.py`), but never feeds the applier pipeline itself (no fit-beyond-screen review, no form-filling, no `mark_applied.py`) — that stays NY-only.
- [other-fulltime.json](other-fulltime.json) — same as above, for new-grad/full-time listings outside New York.
- All six files are guarded by one shared `state.lock` — see [../scripts/state.py](../scripts/state.py)'s module docstring for why moving a record between files has to be atomic across both, and why the lock lives in its own file rather than on any state file itself.

# Last Updated

- 2026-09-01 — update this date whenever this file is edited.
