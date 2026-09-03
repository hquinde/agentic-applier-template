#!/usr/bin/env python3
"""
mark_unmatched.py — mark a job as unmatched (not a fit, skip permanently) by its URL

Searches ny-internships.json, ny-fulltime.json, other-internships.json, and
other-fulltime.json (in that order) for a matching record.

Usage:
    python mark_unmatched.py <apply-url>
"""

import sys

from state import set_status


def main():
    if len(sys.argv) < 2:
        print("Usage: python mark_unmatched.py <apply-url>")
        sys.exit(1)

    url = sys.argv[1]
    if not set_status(url, "unmatched"):
        print(f"No matching record in ny-internships.json, ny-fulltime.json, other-internships.json, or other-fulltime.json for: {url}")
        sys.exit(1)

    print(f"Marked as unmatched: {url}")


if __name__ == "__main__":
    main()
