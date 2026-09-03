# Agentic Applier

A job applier that pulls listings from tracked GitHub repos, tracks what's been applied to vs. not, and separates New York location roles from everywhere else. Built to run with Claude Code driving the browser via the `claude-in-chrome` extension.

## Structure

- `scripts/` — Python scripts that fetch listings from tracked GitHub repos and move jobs between tracker files (`fetch.py`, `mark_applied.py`, `mark_unmatched.py`, `mark_unmatched_bulk.py`, `state.py`). No dependencies beyond the standard library.
- `tracker/` — the JSON state files the scripts read/write. Ships empty — running `fetch.py` populates it.
- `applier/` — the batch job-application workflow (`CONTEXT.md`) and the personal source files it needs, which you provide yourself (see below).

Each directory has its own `CLAUDE.md` with more detail — read those before running anything.

## Setup

1. Clone this repo and open it in your IDE of choice. You'll need an agentic coding tool that can drive a browser — this was built and tested with Claude Code (via the `claude-in-chrome` extension), but similar tools (e.g. Claude Cowork) should work too.
2. Add your own personal context to `applier/` (none of this is included in this template):
   - `resume-context.md` — full-detail record of your background: education, experience, projects, leadership.
   - `questions-context.md` — raw material for essay/short-answer questions: references, motivation themes, talking points, work authorization/location facts.
   - `workday-fields.md` — canonical field values for Workday-based applications, so they don't get re-derived every time.
   - Your resume PDF (and optionally a transcript PDF) for uploading to applications and cross-checking factual claims.
3. Run `python scripts/fetch.py` to pull the first batch of listings into `tracker/`.
4. Read `applier/CONTEXT.md` for the actual batch-application workflow, then run a batch with Claude Code.

## Make this yours

This template reflects my own job search — treat it as a starting point, not a fixed pipeline:

- **NY/non-NY split** — I was targeting New York roles specifically. Swap that filter logic in `scripts/fetch.py`/`scripts/state.py` and the fit criteria in `applier/CONTEXT.md` for whatever split or criteria actually match what you're optimizing for.
- **Tracked source repos** — `scripts/fetch.py`'s `REPOS` list (documented in `scripts/CLAUDE.md`) points at the repos I was tracking. Swap in whichever repos actually list the roles you care about.

## Notes

- The tracked source repos and the NY/non-NY split logic are documented in `scripts/CLAUDE.md`.
- `applier/CONTEXT.md` documents the fit-review criteria and the browser-automation workflow (single agent, multiple tabs) — read it before running a batch, since it also covers when to stop and ask instead of guessing.

## Inspiration

- **[Interpretable Context Methodology: Folder Structure as Agentic Architecture](https://arxiv.org/abs/2603.16021)** — Van Clief & McDermott's paper on replacing framework-level orchestration with filesystem structure; the model behind this project's `CLAUDE.md`-per-directory, filesystem-as-context design.
- **[How the Open Knowledge Format can improve data sharing](https://cloud.google.com/blog/products/data-analytics/how-the-open-knowledge-format-can-improve-data-sharing)** (Google Cloud) — the idea of a shared, portable schema for describing data that any system can read/write, echoed here in the tracker's plain-JSON, no-framework state files.
