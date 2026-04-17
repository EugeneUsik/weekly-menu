#!/usr/bin/env python3
"""
check_library.py — Report recipe library sufficiency for a given week.

Usage:
  python scripts/check_library.py [--week 2026-W18]

If --week is omitted, reports raw pool sizes with no exclusions applied.

Exit codes:
  0  Library is sufficient (all pools at or above minimum)
  1  Library is insufficient — one or more pools below minimum
  2  Fatal error (missing file)
"""

import json
import sys
import argparse
from pathlib import Path

ROOT = Path(__file__).parent.parent

# Hard minimum to generate a valid week
MINIMUMS = {
    "breakfast": {"total": 7},
    "dinner":    {"total": 7, "omega3": 2, "legumes": 3},
    "lunch":     {"total": 3},
    "snack":     {"total": 3},
}

# Comfortable buffer — warn when below this even if above minimum
TARGETS = {
    "breakfast": {"total": 10},
    "dinner":    {"total": 10, "omega3": 4, "legumes": 5},
    "lunch":     {"total": 5},
    "snack":     {"total": 5},
}


def load_json(path: Path):
    if not path.exists():
        print(f"FATAL: {path} not found", file=sys.stderr)
        sys.exit(2)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_exclusion(week_id: str, window: int = 2) -> dict:
    """Return hard-excluded recipe IDs per meal type from the `window` most recent weeks."""
    menus_dir = ROOT / "data" / "menus"
    files = sorted(menus_dir.glob("*.json"), reverse=True)
    hard_exclude = {mt: set() for mt in ["breakfast", "dinner", "lunch", "snack"]}
    count = 0
    for f in files:
        if f.stem >= week_id:
            continue
        if count >= window:
            break
        try:
            menu = load_json(f)
        except SystemExit:
            continue
        for day in menu.get("days", []):
            for mt, meal in day.get("meals", {}).items():
                if isinstance(meal, dict) and mt in hard_exclude:
                    rid = meal.get("recipeId")
                    if rid:
                        hard_exclude[mt].add(rid)
        count += 1
    return hard_exclude


def check(week_id: str | None = None) -> tuple[bool, list[str]]:
    """
    Run the check. Returns (sufficient: bool, need_recipe_signals: list[str]).
    """
    recipes = load_json(ROOT / "data" / "recipes.json")
    hard_exclude = build_exclusion(week_id) if week_id else {mt: set() for mt in ["breakfast", "dinner", "lunch", "snack"]}

    insufficient = False
    signals: list[str] = []

    label = f" for {week_id}" if week_id else " (no exclusions)"
    print(f"Library sufficiency check{label}")
    print("=" * 52)

    for mt in ["breakfast", "dinner", "lunch", "snack"]:
        excluded_ids = hard_exclude[mt]
        pool = [
            r for r in recipes
            if r.get("mealType") == mt
            and r["id"] not in excluded_ids
            and r.get("flags", {}).get("childSafe", True)
        ]
        total = len(pool)
        min_total = MINIMUMS[mt]["total"]
        tgt_total = TARGETS[mt]["total"]

        if total < min_total:
            insufficient = True
            icon = "✗"
            signals.append(f"NEED_RECIPE: {mt} (have {total}, need {min_total})")
        elif total < tgt_total:
            icon = "⚠"
        else:
            icon = "✓"

        print(f"\n  {mt.upper()}")
        print(f"    Total : {icon} {total} available  ({len(excluded_ids)} excluded)  min={min_total}  target={tgt_total}")

        if mt == "dinner":
            omega3 = [r for r in pool if r.get("flags", {}).get("containsOmega3Fish")]
            legumes = [r for r in pool if r.get("flags", {}).get("containsLegumes")]
            other   = [r for r in pool if not r.get("flags", {}).get("containsOmega3Fish") and not r.get("flags", {}).get("containsLegumes")]

            min_o3  = MINIMUMS["dinner"]["omega3"]
            min_lg  = MINIMUMS["dinner"]["legumes"]
            tgt_o3  = TARGETS["dinner"]["omega3"]
            tgt_lg  = TARGETS["dinner"]["legumes"]

            if len(omega3) < min_o3:
                insufficient = True
                o3_icon = "✗"
                signals.append(f"NEED_RECIPE: dinner, containsOmega3Fish=true (have {len(omega3)}, need {min_o3})")
            elif len(omega3) < tgt_o3:
                o3_icon = "⚠"
            else:
                o3_icon = "✓"

            if len(legumes) < min_lg:
                insufficient = True
                lg_icon = "✗"
                signals.append(f"NEED_RECIPE: dinner, containsLegumes=true (have {len(legumes)}, need {min_lg})")
            elif len(legumes) < tgt_lg:
                lg_icon = "⚠"
            else:
                lg_icon = "✓"

            print(f"    Omega3: {o3_icon} {len(omega3)}  (min={min_o3}  target={tgt_o3})")
            print(f"    Legumes:{lg_icon} {len(legumes)}  (min={min_lg}  target={tgt_lg})")
            print(f"    Other : ✓ {len(other)}")

    print()
    if insufficient:
        print("RESULT: INSUFFICIENT — run /expand-library before generating")
        for s in signals:
            print(f"  {s}")
    else:
        print("RESULT: OK — library is sufficient")

    return not insufficient, signals


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Check recipe library sufficiency.")
    parser.add_argument("--week", default=None, help="ISO week ID, e.g. 2026-W18")
    args = parser.parse_args()
    ok, _ = check(args.week)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
