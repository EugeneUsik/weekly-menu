#!/usr/bin/env python3
"""
sync_index.py — Rebuild data/index.json by scanning data/menus/*.json.

Usage:
  python scripts/sync_index.py [--dry-run]

Scans all menu files, extracts weekId and startDate, rebuilds the weeks array
while preserving existing metadata (labelRu, published flag). Sets defaultWeekId
to the most recent published week.

Exit codes:
  0  Success
  2  Fatal error
"""

import json
import sys
import argparse
from pathlib import Path
from datetime import datetime, timedelta

ROOT = Path(__file__).parent.parent

MONTHS_RU = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля",
    5: "мая", 6: "июня", 7: "июля", 8: "августа",
    9: "сентября", 10: "октября", 11: "ноября", 12: "декабря",
}


def load_json(path: Path):
    if not path.exists():
        print(f"FATAL: File not found: {path}", file=sys.stderr)
        sys.exit(2)
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"FATAL: JSON parse error in {path}: {e}", file=sys.stderr)
        sys.exit(2)


def week_start_from_id(week_id: str):
    """Return Monday date from ISO week ID like '2026-W15'."""
    year, week = week_id.split("-W")
    # ISO week Monday: use %G-W%V-%u format
    return datetime.strptime(f"{year}-W{int(week):02d}-1", "%G-W%V-%u").date()


def make_label_ru(start_date, end_date) -> str:
    """Generate Russian date range label like '6–12 апреля'."""
    if start_date.month == end_date.month:
        return f"{start_date.day}–{end_date.day} {MONTHS_RU[start_date.month]}"
    return f"{start_date.day} {MONTHS_RU[start_date.month]} – {end_date.day} {MONTHS_RU[end_date.month]}"


def main():
    parser = argparse.ArgumentParser(description="Rebuild data/index.json from menu files.")
    parser.add_argument("--dry-run", action="store_true", help="Print result instead of writing")
    args = parser.parse_args()

    menus_dir = ROOT / "data" / "menus"
    index_path = ROOT / "data" / "index.json"

    # Load existing index to preserve metadata
    existing_index = load_json(index_path) if index_path.exists() else {"weeks": [], "defaultWeekId": None}
    existing_by_id = {w["weekId"]: w for w in existing_index.get("weeks", [])}

    menu_files = sorted(menus_dir.glob("*.json"))
    if not menu_files:
        print("No menu files found in data/menus/", file=sys.stderr)
        sys.exit(0)

    weeks = []
    for menu_path in menu_files:
        try:
            menu = load_json(menu_path)
        except SystemExit:
            print(f"Skipping unparseable file: {menu_path.name}", file=sys.stderr)
            continue

        week_id = menu.get("weekId")
        if not week_id:
            print(f"WARN: {menu_path.name} has no weekId, skipping.", file=sys.stderr)
            continue

        try:
            start = week_start_from_id(week_id)
            end = start + timedelta(days=6)
        except (ValueError, AttributeError):
            print(f"WARN: Cannot parse weekId '{week_id}', skipping.", file=sys.stderr)
            continue

        # Preserve existing metadata; generate defaults for new weeks
        existing = existing_by_id.get(week_id, {})
        week_entry = {
            "weekId": week_id,
            "labelRu": existing.get("labelRu") or make_label_ru(start, end),
            "startDate": str(start),
            "endDate": str(end),
            "published": existing.get("published", True),
        }
        weeks.append(week_entry)

    # Sort by startDate descending (newest first)
    weeks.sort(key=lambda w: w["startDate"], reverse=True)

    # defaultWeekId = most recent published week
    published = [w for w in weeks if w["published"]]
    default_id = published[0]["weekId"] if published else (weeks[0]["weekId"] if weeks else None)

    new_index = {"weeks": weeks, "defaultWeekId": default_id}

    if args.dry_run:
        print(json.dumps(new_index, ensure_ascii=False, indent=2))
    else:
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(new_index, f, ensure_ascii=False, indent=2)
        print(f"OK index.json updated: {len(weeks)} week(s), default: {default_id}")

    sys.exit(0)


if __name__ == "__main__":
    main()
