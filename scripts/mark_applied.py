#!/usr/bin/env python3
"""
mark_applied.py — mark a job as applied by its URL

Usage:
    python mark_applied.py <apply-url>
"""

import sys

from state import set_status


def main():
    if len(sys.argv) < 2:
        print("Usage: python mark_applied.py <apply-url>")
        sys.exit(1)

    url = sys.argv[1]
    if not set_status(url, "applied"):
        print(f"No matching record in ny-internships.json or ny-fulltime.json for: {url}")
        sys.exit(1)

    print(f"Marked as applied: {url}")


if __name__ == "__main__":
    main()
