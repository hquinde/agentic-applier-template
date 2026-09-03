#!/usr/bin/env python3
"""
fetch.py — pull job listings from tracking repos into tracker/ny-internships.json,
tracker/ny-fulltime.json, tracker/other-internships.json, and tracker/other-fulltime.json

Run:
    python fetch.py
"""

import re
from datetime import date, datetime
from urllib.request import Request, urlopen
from urllib.error import URLError

from state import (
    INTERNSHIPS_FILE,
    FULLTIME_FILE,
    APPLIED_FILE,
    UNMATCHED_FILE,
    OTHER_INTERNSHIPS_FILE,
    OTHER_FULLTIME_FILE,
    NYC_NY_FILES,
    normalize_link,
    upsert_jobs,
    load_jobs,
    urls_in,
)

REPOS = [
    {
        "name": "vanshb03/New-Grad-2027",
        "url": "https://raw.githubusercontent.com/vanshb03/New-Grad-2027/main/README.md",
        "type": "vansh",
        "category": "new-grad",
    },
    {
        "name": "vanshb03/Summer2027-Internships",
        "url": "https://raw.githubusercontent.com/vanshb03/Summer2027-Internships/main/README.md",
        "type": "vansh",
        "category": "internship",
    },
    {
        "name": "zapplyjobs/New-Grad-Jobs-2027",
        "url": "https://raw.githubusercontent.com/zapplyjobs/New-Grad-Jobs-2027/main/README.md",
        "type": "zapply",
        "category": "new-grad",
    },
    {
        "name": "zapplyjobs/Internships-2027",
        "url": "https://raw.githubusercontent.com/zapplyjobs/Internships-2027/main/README.md",
        "type": "zapply",
        "category": "internship",
    },
    {
        "name": "speedyapply/2027-SWE-College-Jobs (Internships)",
        "url": "https://raw.githubusercontent.com/speedyapply/2027-SWE-College-Jobs/main/README.md",
        "type": "speedy",
        "category": "internship",
    },
    {
        "name": "speedyapply/2027-SWE-College-Jobs (New Grad)",
        "url": "https://raw.githubusercontent.com/speedyapply/2027-SWE-College-Jobs/main/NEW_GRAD_USA.md",
        "type": "speedy",
        "category": "new-grad",
    },
    {
        "name": "speedyapply/2027-AI-College-Jobs (Internships)",
        "url": "https://raw.githubusercontent.com/speedyapply/2027-AI-College-Jobs/main/README.md",
        "type": "speedy",
        "category": "internship",
    },
    {
        "name": "speedyapply/2027-AI-College-Jobs (New Grad)",
        "url": "https://raw.githubusercontent.com/speedyapply/2027-AI-College-Jobs/main/NEW_GRAD_USA.md",
        "type": "speedy",
        "category": "new-grad",
    },
]


# ── helpers ──────────────────────────────────────────────────────────────────

def fetch_readme(url: str) -> str:
    req = Request(url, headers={"User-Agent": "job-applier/1.0"})
    try:
        with urlopen(req, timeout=15) as r:
            return r.read().decode("utf-8")
    except URLError as e:
        print(f"  Warning: could not fetch {url}: {e}")
        return ""


def strip_tags(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html).strip()


def first_href(html: str) -> str:
    m = re.search(r'href="([^"]+)"', html)
    return m.group(1) if m else ""


def parse_md_table_rows(content: str) -> list[list[str]]:
    """
    Extract data rows from all markdown tables in content.
    A separator row (|---|---) signals that subsequent rows are data, not headers.
    Resets when a non-table line is encountered between tables.
    """
    rows = []
    collecting = False

    for line in content.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            collecting = False
            continue

        cells = [c.strip() for c in stripped.split("|")[1:-1]]
        if not cells:
            continue

        if all(re.match(r"^[-: ]*$", c) for c in cells):
            collecting = True
            continue

        if collecting:
            rows.append(cells)

    return rows


def parse_days_ago(raw: str) -> float:
    """Normalize any age/date string to approximate days ago. Lower = more recent."""
    raw = raw.strip().lower()
    # "12m" / "12min" = minutes
    m = re.match(r"(\d+)\s*m(?:in)?$", raw)
    if m:
        return int(m.group(1)) / 1440
    # "3h" / "3hr" = hours
    m = re.match(r"(\d+)\s*h(?:r|our)?s?$", raw)
    if m:
        return int(m.group(1)) / 24
    # "5d" = days
    m = re.match(r"(\d+)\s*d(?:ay)?s?$", raw)
    if m:
        return float(m.group(1))
    # "2w" = weeks
    m = re.match(r"(\d+)\s*w(?:eek)?s?$", raw)
    if m:
        return int(m.group(1)) * 7.0
    # "3mo" / "3month" = months
    m = re.match(r"(\d+)\s*mo(?:nth)?s?$", raw)
    if m:
        return int(m.group(1)) * 30.0
    # "May 22" / "Jan 5" = calendar date, infer year
    today = date.today()
    for fmt in ("%b %d %Y", "%B %d %Y"):
        try:
            candidate = datetime.strptime(f"{raw.title()} {today.year}", fmt).date()
            if candidate > today:
                candidate = datetime.strptime(f"{raw.title()} {today.year - 1}", fmt).date()
            return float((today - candidate).days)
        except ValueError:
            continue
    return 9999.0  # unknown — sort to end


# ── per-repo parsers ──────────────────────────────────────────────────────────

def parse_simplify(content: str) -> list[dict]:
    """
    SimplifyJobs repos use raw HTML tables:
      <tr><td>Company</td><td>Role</td><td>Location</td><td>Apply buttons</td><td>Age</td></tr>
    """
    jobs = []
    rows = re.findall(r"<tr>(.*?)</tr>", content, re.DOTALL)
    for row in rows:
        # Skip closed listings
        if "🔒" in row:
            continue
        cells = re.findall(r"<td>(.*?)</td>", row, re.DOTALL)
        if len(cells) < 4:
            continue

        company_m = re.search(r">([^<]+)</a>", cells[0])
        company = company_m.group(1).strip() if company_m else strip_tags(cells[0])

        role = strip_tags(cells[1])

        location = re.sub(r"</br>|<br\s*/?>", ", ", cells[2])
        location = strip_tags(location).strip(", ")

        # First href in the application cell is the direct apply link
        hrefs = re.findall(r'href="([^"]+)"', cells[3])
        link = hrefs[0] if hrefs else ""
        age = strip_tags(cells[4]) if len(cells) > 4 else ""

        if not company or not link:
            continue

        jobs.append({"company": company, "role": role, "location": location, "link": link, "days_ago": parse_days_ago(age)})

    return jobs


def parse_vansh(content: str) -> list[dict]:
    """
    vanshb03 repos: Company | Role | Location | Application/Link | Date Posted
    ↳ rows inherit the company from the row above.
    """
    jobs = []
    last_company = ""

    for cells in parse_md_table_rows(content):
        if len(cells) < 4:
            continue
        if "🔒" in cells[3]:
            continue

        if cells[0].strip().startswith("↳"):
            company = last_company
        else:
            company = strip_tags(cells[0]).replace("↳", "").strip()
            if company:
                last_company = company

        role = strip_tags(cells[1])
        location = re.sub(r"<details>.*?</details>", "Multiple", cells[2], flags=re.DOTALL)
        location = strip_tags(location).strip()
        link = first_href(cells[3])
        age = strip_tags(cells[4]) if len(cells) > 4 else ""

        if not company or not link:
            continue

        jobs.append({"company": company, "role": role, "location": location, "link": link, "days_ago": parse_days_ago(age)})

    return jobs


def parse_speedy(content: str) -> list[dict]:
    """
    speedyapply: Company | Position | Location | [Salary |] Posting | Age
    Salary column is present in FAANG+/Quant sections but not Others.
    We find the link in whichever cell has one from index 3 onward.
    """
    jobs = []

    for cells in parse_md_table_rows(content):
        if len(cells) < 4:
            continue

        company = strip_tags(cells[0])
        role = strip_tags(cells[1])
        location = strip_tags(cells[2])

        link = ""
        age = strip_tags(cells[-1])  # last column is always Age
        for cell in cells[3:-1]:
            h = first_href(cell)
            if h:
                link = h
                break

        if not company or not link:
            continue

        jobs.append({"company": company, "role": role, "location": location, "link": link, "days_ago": parse_days_ago(age)})

    return jobs


def parse_zapply(content: str) -> list[dict]:
    """
    zapplyjobs: tables wrapped in <details> blocks.
    Company | Role | Location | Posted | Visa | Apply
    Apply column uses [<img>](URL) markdown link syntax.
    """
    content = re.sub(r"</?details>|<summary>.*?</summary>", "", content, flags=re.DOTALL)
    jobs = []

    for cells in parse_md_table_rows(content):
        if len(cells) < 5:
            continue

        company = re.sub(r"\*\*([^*]+)\*\*", r"\1", cells[0]).strip()
        company = strip_tags(company)
        role = strip_tags(cells[1])
        location = strip_tags(cells[2])

        apply_cell = cells[-1]
        # [<img ...>](URL) or href="URL"
        m = re.search(r"\]\(([^)]+)\)", apply_cell) or re.search(r'href="([^"]+)"', apply_cell)
        link = m.group(1) if m else ""
        age = strip_tags(cells[3]) if len(cells) > 3 else ""  # Posted column

        if not company or not link:
            continue

        jobs.append({"company": company, "role": role, "location": location, "link": link, "days_ago": parse_days_ago(age)})

    return jobs


PARSERS = {
    "simplify": parse_simplify,
    "vansh": parse_vansh,
    "speedy": parse_speedy,
    "zapply": parse_zapply,
}


# ── classification ────────────────────────────────────────────────────────────

def classify_location(location: str) -> str:
    """Classify a location string as "nyc", "ny" (rest of NY State), or "other"."""
    loc = location.upper()
    boroughs = ("NEW YORK CITY", "NYC", "MANHATTAN", "BROOKLYN", "QUEENS", "BRONX", "STATEN ISLAND")
    if any(b in loc for b in boroughs):
        return "nyc"
    if re.search(r"NEW YORK,\s*(NY\b|NEW YORK\b)", loc) or loc.strip() == "NEW YORK":
        return "nyc"
    if "NEW YORK" in loc or ", NY" in loc or loc.endswith(" NY"):
        return "ny"
    return "other"


def normalize_text(s: str) -> str:
    """Canonicalize company/role text for dedup comparison: strip case, punctuation, whitespace, truncation."""
    s = s.strip()
    if s.endswith("..."):
        s = s[:-3]
    return re.sub(r"[^a-z0-9]", "", s.lower())


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    already_seen: set[str] = set()
    for f in (*NYC_NY_FILES, OTHER_INTERNSHIPS_FILE, OTHER_FULLTIME_FILE):
        already_seen |= urls_in(f)

    internship_records: list[dict] = []
    fulltime_records: list[dict] = []
    other_internship_records: list[dict] = []
    other_fulltime_records: list[dict] = []
    seen_links: set[str] = set()
    seen_content: set[tuple[str, str, str]] = set()
    total_fetched = 0

    for repo in REPOS:
        print(f"Fetching {repo['name']}...")
        content = fetch_readme(repo["url"])
        if not content:
            continue

        jobs = PARSERS[repo["type"]](content)
        new_count = sum(1 for j in jobs if normalize_link(j["link"]) not in already_seen)
        jobs.sort(key=lambda j: j.get("days_ago", 9999))

        kept = 0
        for j in jobs:
            nlink = normalize_link(j["link"])
            region = classify_location(j["location"])
            ckey = (normalize_text(j["company"]), normalize_text(j["role"]), region)
            if nlink in seen_links or ckey in seen_content:
                continue
            seen_links.add(nlink)
            seen_content.add(ckey)

            is_internship = repo["category"] == "internship"
            if region == "other":
                record = {
                    "url": j["link"],
                    "company": j["company"],
                    "role": j["role"],
                    "location": j["location"],
                }
                (other_internship_records if is_internship else other_fulltime_records).append(record)
            else:
                record = {"url": j["link"], "company": j["company"], "role": j["role"]}
                (internship_records if is_internship else fulltime_records).append(record)
            kept += 1

        total_fetched += len(jobs)
        print(f"  {new_count} new / {len(jobs)} total")

    before_intern = len(load_jobs(INTERNSHIPS_FILE))
    before_fulltime = len(load_jobs(FULLTIME_FILE))
    upsert_jobs(INTERNSHIPS_FILE, internship_records)
    upsert_jobs(FULLTIME_FILE, fulltime_records)
    upsert_jobs(OTHER_INTERNSHIPS_FILE, other_internship_records)
    upsert_jobs(OTHER_FULLTIME_FILE, other_fulltime_records)
    added_intern = len(load_jobs(INTERNSHIPS_FILE)) - before_intern
    added_fulltime = len(load_jobs(FULLTIME_FILE)) - before_fulltime

    print(f"\n{total_fetched} listings fetched")
    print(f"  {len(internship_records)} NYC/NY internships, {added_intern} new → {INTERNSHIPS_FILE}")
    print(f"  {len(fulltime_records)} NYC/NY new-grad/full-time, {added_fulltime} new → {FULLTIME_FILE}")
    print(f"  {len(other_internship_records)} everywhere-else internships → {OTHER_INTERNSHIPS_FILE}")
    print(f"  {len(other_fulltime_records)} everywhere-else new-grad/full-time → {OTHER_FULLTIME_FILE}")
    print("Apply to what you want, then: python mark_applied.py <url>")


if __name__ == "__main__":
    main()
