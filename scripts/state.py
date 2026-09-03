#!/usr/bin/env python3
"""
state.py — concurrency-safe access to the tracker/*.json files.

ny-internships.json, ny-fulltime.json, other-internships.json, and
other-fulltime.json each hold a flat list of job records. The NY pair drops
"location"/"category"/"region" — that info is redundant with which file the
record lives in — so their records are just:
    {"url": str, "company": str, "role": str}
The "other" pair keeps "location" (there's no NYC/NY bucketing to redundantly
encode it), so their records are:
    {"url": str, "company": str, "role": str, "location": str}

applied.json and unmatched.json are simpler: once a job leaves the active
pool, its metadata is no longer useful, so they're just flat lists of URL
strings — nothing to look up a company/role for, just "already handled."
unmatched.json is shared across regions (see below); applied.json stays
NY-only, since the applier workflow itself is NY-only.

A job lives in exactly one of these six files at a time, and its file *is*
its status:
    - ny-internships.json    — NYC/NY internships, unprocessed (active pool, full records)
    - ny-fulltime.json       — NYC/NY new-grad/full-time, unprocessed (active pool, full records)
    - applied.json           — NYC/NY, applied (URL strings only)
    - unmatched.json         — not a fit (AI/SWE role review), skip permanently, NY or non-NY (URL strings only)
    - other-internships.json — everywhere else, internships, gets the same fit review as the NY files but never enters the applier pipeline (full records)
    - other-fulltime.json    — everywhere else, new-grad/full-time, same as above (full records)

`mark_applied.py` moves a record out of ny-internships.json or
ny-fulltime.json (whichever has it), dropping everything but its URL, into
applied.json. `mark_unmatched.py` does the same but also searches
other-internships.json/other-fulltime.json, since non-NY roles get the same
AI/SWE fit review and share unmatched.json. `fetch.py` only ever adds *new*
records to ny-internships.json/ny-fulltime.json — it checks all four NYC/NY
files first so a job already moved to applied.json or unmatched.json doesn't
get re-added to the active pool; for other-internships.json/other-fulltime.json
it additionally checks unmatched.json so a non-NY job marked unmatched doesn't
get re-fetched.

Several processes touch these files at once (fetch.py, plus mark_applied.py /
mark_unmatched.py run from more than one Claude Code session at a time). A plain
read-modify-write loses updates: whoever writes last wins and silently drops the
other's entry. Every mutation here runs under one process-wide lock (covering
ny-internships.json/ny-fulltime.json/applied.json/unmatched.json together,
since moving a record between them has to be atomic across both files) and
lands via an atomic replace per file.

The lock lives in a separate file (state.lock) rather than on any of the state
files themselves. flock() is tied to an inode, and an atomic replace swaps a
state file's inode out, so a waiter blocked on the old inode would wake holding
a lock on an unlinked file and clobber the winner. The lock file is never replaced.
"""

import fcntl
import json
import os
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

TRACKER_DIR = Path(__file__).parent.parent / "tracker"
INTERNSHIPS_FILE = TRACKER_DIR / "ny-internships.json"
FULLTIME_FILE = TRACKER_DIR / "ny-fulltime.json"
APPLIED_FILE = TRACKER_DIR / "applied.json"
UNMATCHED_FILE = TRACKER_DIR / "unmatched.json"
OTHER_INTERNSHIPS_FILE = TRACKER_DIR / "other-internships.json"
OTHER_FULLTIME_FILE = TRACKER_DIR / "other-fulltime.json"

JOB_FILES = (INTERNSHIPS_FILE, FULLTIME_FILE)  # NYC/NY active pool, full records
NYC_NY_FILES = (INTERNSHIPS_FILE, FULLTIME_FILE, APPLIED_FILE, UNMATCHED_FILE)
OTHER_FILES = (OTHER_INTERNSHIPS_FILE, OTHER_FULLTIME_FILE)  # everywhere-else, full records
UNMATCHED_SEARCH_FILES = JOB_FILES + OTHER_FILES  # set_status("unmatched") looks across all of these
URL_LIST_FILES = (APPLIED_FILE, UNMATCHED_FILE)  # flat list[str], not list[dict]

LOCK_FILE = TRACKER_DIR / "state.lock"


def normalize_link(url: str) -> str:
    """Canonicalize a URL for dedup comparison: drop query/fragment/trailing slash, lowercase host."""
    parts = urlsplit(url)
    path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, "", ""))


@contextmanager
def _lock():
    """Hold an exclusive lock for the whole read-modify-write. Blocks if another holds it."""
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOCK_FILE.open("w") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def _read(path: Path) -> list:
    if not path.exists():
        return []
    return json.loads(path.read_text())


def _write(path: Path, items: list):
    """Write via temp file + os.replace so a reader never sees a half-written file."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(items, indent=2))
    os.replace(tmp, path)


def _urls_in(path: Path) -> set[str]:
    """Normalized URLs present in `path`, whether it holds records or bare URL strings."""
    items = _read(path)
    urls = [item if isinstance(item, str) else item["url"] for item in items]
    return {normalize_link(u) for u in urls}


def load_jobs(path: Path) -> list:
    """Read a consistent snapshot. Read-only — don't write this list back."""
    with _lock():
        return _read(path)


def urls_in(path: Path) -> set[str]:
    """Normalized URLs present in `path` (public wrapper over `_urls_in`, locked)."""
    with _lock():
        return _urls_in(path)


def upsert_jobs(path: Path, incoming: list[dict]):
    """
    Add freshly-fetched records to `path` (one of the four "active pool"/"other"
    files), skipping any URL already present in *any* NYC/NY file when `path`
    is one of ny-internships.json/ny-fulltime.json (so a job already applied to
    or marked unmatched doesn't get re-added to the active pool, and it doesn't
    end up in both internship and fulltime files). For the other-*.json files,
    also checks unmatched.json (shared across NY and non-NY since
    `set_status("unmatched")` now draws from both) plus its sibling other-*.json
    file, so a non-NY job marked unmatched doesn't get re-fetched.
    """
    with _lock():
        already_known: set[str] = set()
        if path in JOB_FILES:
            sibling_files = NYC_NY_FILES
        elif path in OTHER_FILES:
            sibling_files = OTHER_FILES + (UNMATCHED_FILE,)
        else:
            sibling_files = (path,)
        for f in sibling_files:
            already_known |= _urls_in(f)

        existing = _read(path)
        existing_links = {normalize_link(r["url"]) for r in existing}

        added = list(existing)
        for record in incoming:
            key = normalize_link(record["url"])
            if key in already_known or key in existing_links:
                continue
            added.append(record)
            existing_links.add(key)

        _write(path, added)


def set_status(url: str, status: str) -> bool:
    """
    Move the record matching `url` (by normalized link) out of whichever
    job file has it, appending just its URL to applied.json or unmatched.json
    depending on `status`. "applied" only searches ny-internships.json/
    ny-fulltime.json, since the applier workflow is NY-only; "unmatched" also
    searches other-internships.json/other-fulltime.json, since non-NY roles
    get the same AI/SWE fit review and share unmatched.json.

    Returns False if no matching record exists in any searched file. If
    the URL has already been moved to the target file (e.g. this was already
    run once), treats that as success too.
    """
    dest_file = APPLIED_FILE if status == "applied" else UNMATCHED_FILE
    search_files = JOB_FILES if status == "applied" else UNMATCHED_SEARCH_FILES
    key = normalize_link(url)

    with _lock():
        for jobs_file in search_files:
            jobs = _read(jobs_file)
            match = next((r for r in jobs if normalize_link(r["url"]) == key), None)
            if match is None:
                continue

            _write(jobs_file, [r for r in jobs if normalize_link(r["url"]) != key])
            dest = _read(dest_file)
            dest.append(match["url"])
            _write(dest_file, dest)
            return True

        return key in _urls_in(dest_file)


def set_status_bulk(urls: list[str], status: str) -> int:
    """
    Batch version of `set_status`: moves every matching record in one lock
    acquisition and one read/write pass per file, instead of one full
    read-modify-write cycle per URL. Meant for reviewing a whole fetch batch
    (potentially hundreds of other-*.json records) at once.

    Returns the count of URLs actually moved (URLs with no matching record,
    or already in the destination file, aren't counted).
    """
    dest_file = APPLIED_FILE if status == "applied" else UNMATCHED_FILE
    search_files = JOB_FILES if status == "applied" else UNMATCHED_SEARCH_FILES
    keys = {normalize_link(u) for u in urls}
    moved = 0

    with _lock():
        moved_urls = []
        for jobs_file in search_files:
            jobs = _read(jobs_file)
            remaining = []
            for r in jobs:
                if normalize_link(r["url"]) in keys:
                    moved_urls.append(r["url"])
                else:
                    remaining.append(r)
            if len(remaining) != len(jobs):
                _write(jobs_file, remaining)

        if moved_urls:
            dest = _read(dest_file)
            dest_keys = {normalize_link(u) for u in dest}
            for u in moved_urls:
                if normalize_link(u) not in dest_keys:
                    dest.append(u)
                    dest_keys.add(normalize_link(u))
                    moved += 1
            _write(dest_file, dest)

    return moved
