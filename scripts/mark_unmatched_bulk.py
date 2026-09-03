#!/usr/bin/env python3
"""
mark_unmatched_bulk.py — mark many jobs as unmatched at once, in a single lock pass.

Reads a JSON list of URLs (from a file argument, or stdin if no argument is
given) and moves each into unmatched.json via state.set_status_bulk. Meant
for reviewing a whole fetch batch at once, since ../tracker/other-internships.json
and ../tracker/other-fulltime.json can add hundreds of records per run.

Usage:
    python mark_unmatched_bulk.py urls.json
    echo '["https://...", "https://..."]' | python mark_unmatched_bulk.py
"""

import json
import sys

from state import set_status_bulk


def main():
    if len(sys.argv) > 1:
        text = open(sys.argv[1]).read()
    else:
        text = sys.stdin.read()

    urls = json.loads(text)
    if not isinstance(urls, list):
        print("Expected a JSON list of URL strings")
        sys.exit(1)

    moved = set_status_bulk(urls, "unmatched")
    print(f"Marked {moved} of {len(urls)} as unmatched")


if __name__ == "__main__":
    main()
