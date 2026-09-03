# Applier Workflow

The actual runbook for running a batch of NYC job applications from this folder. `CLAUDE.md` here is just the index — this file is what to follow when running a batch.

## Batch workflow

1. Read `../tracker/ny-internships.json` and `../tracker/ny-fulltime.json` — every record in them is unprocessed by definition (each file is already narrowed to one category). Anything already applied or unmatched has already been moved out into `../tracker/applied.json` / `../tracker/unmatched.json`, so it won't show up here.
2. Take the next N unprocessed listings (batch size is set by the user each run — 10 has been used). N is a target count of candidates fully processed (applied, marked unmatched, or explicitly handed to the user as blocked) — if a listing turns out unmatched, pull in another unprocessed listing to replace it rather than letting the batch shrink.
3. Open each candidate in its own browser tab via Claude in Chrome, driven by **one agent**, not parallel subagents. The browser extension is a single shared session — concurrent agents clicking/typing on it can collide (wrong tab, crossed form fields, a duplicate Submit). Multi-tab batching (one agent, several tabs open at once, work interleaved across them) gets most of the speed without that risk.
   - You sometimes fill in fields yourself in parallel tabs while Claude works others. Before writing into any field (especially essay/short-answer questions), re-read its actual current value with a fresh accessibility-tree read — not just a `get_page_text` scrape, which can miss textarea contents — rather than assuming it's empty. If it already has substantive content, ask whether to keep it, replace it, or combine; don't overwrite silently.
   - Never close more than one tab per `tabs_close_mcp` call in the same turn — closing tabs in parallel has destroyed the entire tab group (losing every other open tab) rather than just the targeted one.
4. Read each job description (`get_page_text`). Judge fit against the criteria below.
5. Non-fit → `python ../scripts/mark_unmatched.py <apply-url>` immediately. Don't open the application form for it.
6. Fit → open the application page, fill it from `resume-context.md` / `questions-context.md`, attach your resume PDF, draft any essay questions (see "Essay / short-answer style" below).
7. Submit, then confirm it actually went through before touching the tracker:
   - Take a screenshot of the resulting page (`computer` action `screenshot`, `save_to_disk: true`) and save/move it into `confirmations/` as `<company>-<role-slug>.png`.
   - Run `get_page_text` on the same page and check for actual confirmation language (e.g. "application submitted," "thank you for applying," a reference/confirmation number) or a URL change to a confirmation route — not just "the form no longer shows errors."
   - If confirmation is ambiguous (no success message, an error banner, or the form still looks unsubmitted), stop and ask the user before marking it applied. Don't guess.
8. Only after confirmation passes: `python ../scripts/mark_applied.py <apply-url>`.
9. Close tabs once done with them.

## Blocked applications

If an application hits something Claude can't do (creating an account/password, a CAPTCHA, a stuck form that won't accept input after a couple of retries) — don't stall the batch waiting on it. Flag it to the user with the specific blocker and the apply URL, leave the tab open if useful, and move on to the next candidate immediately. The user can clear the blocker manually (e.g. create the account, solve the CAPTCHA) in parallel while Claude keeps working the rest of the batch, then tell Claude to resume that one.

## Fit criteria — mark unmatched if any apply

- Listed location doesn't actually match NYC despite being in `ny-internships.json`/`ny-fulltime.json` (tracker categorization bugs happen — check the location on the actual posting, not just which file the record was filed under; those files no longer carry a location field, so this has to be verified on the live listing).
- Explicit experience requirement beyond entry-level (e.g. "3+ years," "5+ years," "Senior").
- PhD or Master's required as a hard requirement.
- A core required skill you don't have and aren't close to — check `resume-context.md`'s Technical Skills section before assuming a gap *or* a match (e.g. no React/TypeScript listed anywhere → a frontend-framework-ownership role is a real mismatch, not a stretch).
- A graduation-date window that excludes May 2027 — his expected graduation (see `questions-context.md`'s Availability & Logistics).
- Role-function mismatch — e.g. a "Data Scientist" title that's actually a business/consulting-analytics function requiring a consulting or banking background, when the target is AI/software engineering.
- Listing is dead/expired, or redirects straight to a bare application form with no visible job description (common on staffing-agency boards) — skip rather than submit personal data with no way to verify fit.
- An application's own logistics don't fit reality (e.g. a start-date dropdown with no valid future option) and `questions-context.md` has no documented fallback — ask the user rather than pick one.

## When to ask vs. proceed autonomously

- **Ask** when a field is a personal/factual claim about you that isn't already documented in `resume-context.md` or `questions-context.md` — most importantly: never default to a "privacy-preserving decline" for a factual self-identification question (disability status, veteran status, etc.). Those are answers only you can give, not generic consent toggles like a cookie banner. Get the real answer once, then record it in `questions-context.md` so it's never asked again.
- **Ask** when an application's logistics contradict known facts (impossible dates, program timelines that don't fit) and there's no fallback documented here.
- **Don't ask** for anything already answered in `questions-context.md`'s Work Authorization & Location block, or derivable from `resume-context.md`.
- **Don't ask** before drafting an essay/short-answer response — draft it grounded in the Motivation Themes / Background Talking Points in `questions-context.md`, re-tailored to the specific company and role.
- Confirm the drafted essay answer and the final Submit with the user for the first application of a session. Once they've said to proceed without checking in, keep going through the rest of that batch without re-confirming — unless something about a later one is genuinely ambiguous (see the two "Ask" rules above).

## Essay / short-answer style

- No em dashes (—) — use commas or periods instead.
- Every claim must trace back to `resume-context.md` or `questions-context.md`. Never invent a detail to make an answer sound better.
- "Why this company" answers are drawn from the Motivation Themes section — re-tailor per company, never reuse verbatim.

## Tracker interaction

- `../tracker/ny-internships.json` / `../tracker/ny-fulltime.json` — read directly to find unprocessed candidates. Don't hand-edit; they're upserted by `../scripts/fetch.py`.
- `../scripts/mark_applied.py <url>` / `../scripts/mark_unmatched.py <url>` — the only two mutations this workflow makes, both moving a record out of whichever of `../tracker/ny-internships.json` / `../tracker/ny-fulltime.json` has it, into `../tracker/applied.json` / `../tracker/unmatched.json`.
