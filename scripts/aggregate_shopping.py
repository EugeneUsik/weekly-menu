#!/usr/bin/env python3
"""
aggregate_shopping.py — Recompute shopping list from menu + recipe data.

Usage:
  python scripts/aggregate_shopping.py --week 2026-W15 [--output data/menus/2026-W15.json]

Reads the menu file, resolves all recipe ingredients, scales to family servings (3),
deduplicates, sorts by neededByDate then category, and writes the shoppingList back
into the menu JSON file (or prints to stdout with --dry-run).

Exit codes:
  0  Success
  1  Validation or resolution error
  2  Fatal error (file not found, JSON parse error)
"""

import json
import sys
import argparse
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).parent.parent
FAMILY_SERVINGS = 3

VALID_UNITS = {"g", "ml", "pcs", "tbsp", "tsp", "cup"}

# Unit normalisation for summing: convert tbsp/tsp to ml only when the same
# ingredient also appears measured in ml. Done at aggregation time.
UNIT_TO_ML = {"tbsp": 15, "tsp": 5}

CATEGORY_ORDER = ["produce", "dairy", "meat", "fish", "legumes", "grains", "frozen", "pantry", "other"]


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


def aggregate(week_id: str):
    menu_path = ROOT / "data" / "menus" / f"{week_id}.json"
    menu = load_json(menu_path)
    recipes_list = load_json(ROOT / "data" / "recipes.json")
    ingredient_map_raw = load_json(ROOT / "data" / "catalog" / "ingredient-map.json")
    ingredient_map = ingredient_map_raw.get("ingredients", {})

    recipes_by_id = {r["id"]: r for r in recipes_list}
    all_warnings = []

    # ingredient_id -> { (unit) -> { amount, neededByDate (earliest) } }
    buckets = defaultdict(lambda: defaultdict(lambda: {"amount": 0, "neededByDate": None}))

    for day in menu.get("days", []):
        date = day.get("date", "")
        for mt, meal in day.get("meals", {}).items():
            if not meal:
                continue
            rid = meal.get("recipeId")
            recipe = recipes_by_id.get(rid)
            if not recipe:
                print(f"WARN: Recipe '{rid}' not found, skipping.", file=sys.stderr)
                all_warnings.append(f"Recipe '{rid}' not found in library")
                continue

            # Scale factor: we always want FAMILY_SERVINGS portions
            base_servings = recipe.get("servings", FAMILY_SERVINGS)
            scale = FAMILY_SERVINGS / base_servings if base_servings else 1

            for ing in recipe.get("ingredients", []):
                iid = ing.get("ingredientId")
                amount = ing.get("amount", 0) * scale
                unit = ing.get("unit", "g")
                bucket = buckets[iid][unit]
                bucket["amount"] += amount
                # Track earliest needed date
                if bucket["neededByDate"] is None or date < bucket["neededByDate"]:
                    bucket["neededByDate"] = date

    # Build shopping list items
    shopping_list = []
    unresolved = []

    for iid, unit_map in buckets.items():
        entry = ingredient_map.get(iid)
        if not entry:
            unresolved.append(iid)
            all_warnings.append(f"ingredientId '{iid}' not found in ingredient-map — skipped in shopping list")
            print(f"WARN: ingredientId '{iid}' not in ingredient-map, skipped.", file=sys.stderr)
            continue

        name_ru = entry.get("nameRu", iid)
        name_lt = entry.get("nameLt", "")
        category = entry.get("category", "other")

        # Try to consolidate tbsp/tsp into ml if ml bucket also exists
        consolidated = dict(unit_map)
        for small_unit, ml_factor in UNIT_TO_ML.items():
            if small_unit in consolidated and "ml" in consolidated:
                ml_amount = consolidated.pop(small_unit)["amount"] * ml_factor
                consolidated["ml"]["amount"] += ml_amount
                if consolidated["ml"]["neededByDate"] is None or \
                   unit_map[small_unit]["neededByDate"] < consolidated["ml"]["neededByDate"]:
                    consolidated["ml"]["neededByDate"] = unit_map[small_unit]["neededByDate"]

        for unit, data in consolidated.items():
            raw_amount = data["amount"]
            # Round sensibly
            if unit in ("g", "ml"):
                amount = round(raw_amount)
            else:
                amount = round(raw_amount, 1)

            checkbox_key = f"{week_id}:{category}|{name_ru}|{unit}"
            shopping_list.append({
                "ingredientId": iid,
                "nameRu": name_ru,
                "nameLt": name_lt,
                "category": category,
                "amount": amount,
                "unit": unit,
                "neededByDate": data["neededByDate"] or "",
                "checkboxKey": checkbox_key,
            })

    # Sort: neededByDate ascending, then category order, then name
    cat_rank = {cat: i for i, cat in enumerate(CATEGORY_ORDER)}
    shopping_list.sort(key=lambda x: (
        x["neededByDate"],
        cat_rank.get(x["category"], 99),
        x["nameRu"],
    ))

    return shopping_list, all_warnings, unresolved


def main():
    parser = argparse.ArgumentParser(description="Aggregate shopping list from menu data.")
    parser.add_argument("--week", required=True, help="Week ID (e.g. 2026-W15)")
    parser.add_argument("--dry-run", action="store_true", help="Print result to stdout instead of writing")
    args = parser.parse_args()

    shopping_list, warnings, unresolved = aggregate(args.week)

    menu_path = ROOT / "data" / "menus" / f"{args.week}.json"
    menu = load_json(menu_path)

    menu["shoppingList"] = shopping_list

    if args.dry_run:
        print(json.dumps(shopping_list, ensure_ascii=False, indent=2))
    else:
        with open(menu_path, "w", encoding="utf-8") as f:
            json.dump(menu, f, ensure_ascii=False, indent=2)
        print(f"OK Shopping list written: {len(shopping_list)} items for week {args.week}")

    if warnings:
        print(f"\n⚠ {len(warnings)} warning(s):")
        for w in warnings:
            print(f"  - {w}")

    if unresolved:
        print(f"\nFAIL {len(unresolved)} unresolved ingredient(s) — add to ingredient-map.json:")
        for u in unresolved:
            print(f"  - {u}")
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
