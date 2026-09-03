# scripts/

# Purpose

- Python scripts for pulling and tracking job listings. No dependencies beyond the standard library.

# Scripts

- [fetch.py](fetch.py) — pulls README tables from the tracking repos listed below (vanshb03, speedyapply, zapplyjobs), parses each repo's table format (each has its own parser under `PARSERS`), dedupes across repos on two keys — a normalized link (query string/fragment/trailing-slash/case stripped, via `normalize_link` in `state.py`) and a normalized (company, role, NYC/NY/other location bucket) triple (via `normalize_text`) — to catch both same-URL-different-tracking-param mirrors and same-job-different-portal mirrors (e.g. a role cross-posted from two different Workday/Oracle instances), classifies each listing's location as `nyc`/`ny`/`other`, and adds any genuinely new NYC/NY internship records to [../tracker/ny-internships.json](../tracker/ny-internships.json), NYC/NY new-grad/full-time records to [../tracker/ny-fulltime.json](../tracker/ny-fulltime.json), and the `other`-bucket equivalents to [../tracker/other-internships.json](../tracker/other-internships.json)/[../tracker/other-fulltime.json](../tracker/other-fulltime.json) via `state.py`'s `upsert_jobs` — a URL already present in `ny-internships.json`, `ny-fulltime.json`, `applied.json`, or `unmatched.json` is skipped rather than re-added. Run with `python fetch.py`.
- [state.py](state.py) — concurrency-safe read/write access to the six `../tracker/*.json` files. `upsert_jobs` adds new records while skipping URLs already tracked anywhere in the NYC/NY file set (or, for the `other-*.json` files, already in that file's sibling or in `unmatched.json`); `set_status` is how `mark_applied.py`/`mark_unmatched.py` move a record into `applied.json`/`unmatched.json` (dropping everything but its URL, since those two files are flat URL lists, not records) — `"applied"` only searches `ny-internships.json`/`ny-fulltime.json` (the applier workflow is NY-only), `"unmatched"` also searches `other-internships.json`/`other-fulltime.json` (non-NY roles get the same fit review and share `unmatched.json`). Every mutation runs under one shared lock (`state.lock`) and lands via an atomic replace per file, since `fetch.py`'s long-running network I/O can overlap with a `mark_applied.py`/`mark_unmatched.py` call from another session, and moving a record between files has to be atomic across both.
- [mark_applied.py](mark_applied.py) — moves a job from `../tracker/ny-internships.json` or `../tracker/ny-fulltime.json` into `../tracker/applied.json` by URL. Run with `python mark_applied.py <apply-url>`.
- [mark_unmatched.py](mark_unmatched.py) — moves a job from `../tracker/ny-internships.json`, `../tracker/ny-fulltime.json`, `../tracker/other-internships.json`, or `../tracker/other-fulltime.json` into `../tracker/unmatched.json` (role isn't a fit — skip permanently) by URL. Run with `python mark_unmatched.py <apply-url>`.
- [mark_unmatched_bulk.py](mark_unmatched_bulk.py) — like `mark_unmatched.py` but takes a JSON list of URLs and moves them all in one lock pass via `state.py`'s `set_status_bulk`, for reviewing a whole fetch batch (esp. the `other-*.json` files) at once instead of one subprocess per URL. Run with `python mark_unmatched_bulk.py urls.json` (or pipe the JSON list via stdin).

# Review Process

- `fetch.py` pulls everything the tracked repos publish — it does not filter by role. Fit is judged by an agent, not a hardcoded keyword/regex filter (tried once, rejected — too brittle).
- After every `fetch.py` run, review the records in `../tracker/ny-internships.json`, `../tracker/ny-fulltime.json`, `../tracker/other-internships.json`, and `../tracker/other-fulltime.json` — every one is unprocessed by definition, since applied/unmatched jobs have already been moved out of them. Make sure each aligns to AI/SWE-related roles, using judgment on borderline titles rather than exact keyword matching. Mark non-fits with `python mark_unmatched.py <url>` so they're moved out permanently.
- The `other-*.json` files still never feed the actual applier pipeline (fit review beyond this AI/SWE screen, form-filling, `mark_applied.py`) — that stays NY-only. Reviewing them here is only about keeping `unmatched.json` clean of non-fits regardless of region, not about widening what gets applied to.

# Tracked GitHub Repositories

Scoped to the **2027 grad cycle only** (school-year internships starting after Aug 2026, plus new-grad roles for 2027 graduates) — 2026-cycle repos were dropped, see [../CLAUDE.md](../CLAUDE.md) for the reasoning.

- **[vanshb03/New-Grad-2027](https://github.com/vanshb03/New-Grad-2027)** — new grad SWE, Quant, PM
- **[vanshb03/Summer2027-Internships](https://github.com/vanshb03/Summer2027-Internships)** — community-maintained internship list
- **[zapplyjobs/New-Grad-Jobs-2027](https://github.com/zapplyjobs/New-Grad-Jobs-2027)** — broad entry-level tech, finance, and more
- **[zapplyjobs/Internships-2027](https://github.com/zapplyjobs/Internships-2027)** — broad internship list across tech, business, healthcare
- **[speedyapply/2027-SWE-College-Jobs](https://github.com/speedyapply/2027-SWE-College-Jobs)** — SWE internships (`README.md`) + new grad (`NEW_GRAD_USA.md`), FAANG+/Quant tiers; each page tracked as a separate `REPOS` entry in `fetch.py`
- **[speedyapply/2027-AI-College-Jobs](https://github.com/speedyapply/2027-AI-College-Jobs)** — AI/ML & data science internships (`README.md`) + new grad (`NEW_GRAD_USA.md`), same split-page structure

Not yet wired into `fetch.py` (listed for future consideration):
- Zapply's category-specific 2027 repos (Data-Science, Hardware, Healthcare, Software-Engineering, Canada) — likely redundant with `New-Grad-Jobs-2027`'s aggregate, since that repo appears to roll them up
- **[jobright-ai/2026-Software-Engineer-New-Grad](https://github.com/jobright-ai/2026-Software-Engineer-New-Grad)** — new grad SWE roles (2026 cycle, out of current scope)

# Last Updated

- 2026-09-01 — update this date whenever this file is edited.
