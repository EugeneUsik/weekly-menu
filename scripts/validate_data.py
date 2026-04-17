#!/usr/bin/env python3
"""
validate_data.py — Full data validation pipeline.

Usage:
  python scripts/validate_data.py [--week 2026-W15] [--recipes-only] [--json]

Exit codes:
  0  All validators passed
  1  One or more validation failures
  2  Fatal error (missing file, JSON parse error)
"""

import json
import sys
import os
import re
import argparse
from pathlib import Path

ROOT = Path(__file__).parent.parent

# ── Allergy forbidden terms ───────────────────────────────────────────────────
# Child allergies: apples, pears, cherries, apricots, peaches, prunes/plums.
# Word-boundary patterns prevent false positives (e.g. "pineapple" ≠ "apple",
# "cherry_tomatoes" ingredientId contains "cherry" but cherry tomatoes are safe
# as a produce item — guard by checking full IDs containing "_tomato" suffix).
import re

FORBIDDEN_PATTERNS = [
    re.compile(r'\bapple\b', re.IGNORECASE),
    re.compile(r'\bapples\b', re.IGNORECASE),
    re.compile(r'\bяблоко\b', re.IGNORECASE),
    re.compile(r'\bяблоки\b', re.IGNORECASE),
    re.compile(r'\bяблочн', re.IGNORECASE),
    re.compile(r'\bpear\b', re.IGNORECASE),
    re.compile(r'\bpears\b', re.IGNORECASE),
    re.compile(r'\bгруша\b', re.IGNORECASE),
    re.compile(r'\bгруши\b', re.IGNORECASE),
    re.compile(r'\bгрушев', re.IGNORECASE),
    re.compile(r'\bcherry\b', re.IGNORECASE),
    re.compile(r'\bcherries\b', re.IGNORECASE),
    re.compile(r'\bвишня\b', re.IGNORECASE),
    re.compile(r'\bвишни\b', re.IGNORECASE),
    re.compile(r'\bчерешня\b', re.IGNORECASE),
    re.compile(r'\bprune\b', re.IGNORECASE),
    re.compile(r'\bprunes\b', re.IGNORECASE),
    re.compile(r'\bplum\b', re.IGNORECASE),
    re.compile(r'\bplums\b', re.IGNORECASE),
    re.compile(r'\bчернослив', re.IGNORECASE),
    re.compile(r'\bслива\b', re.IGNORECASE),
    re.compile(r'\bсливы\b', re.IGNORECASE),
    re.compile(r'\bapricot\b', re.IGNORECASE),
    re.compile(r'\bapricots\b', re.IGNORECASE),
    re.compile(r'\bабрикос', re.IGNORECASE),
    re.compile(r'\bpeach\b', re.IGNORECASE),
    re.compile(r'\bpeaches\b', re.IGNORECASE),
    re.compile(r'\bперсик', re.IGNORECASE),
]

# Ingredient IDs that match a forbidden pattern but are actually safe (e.g. cherry tomatoes).
_FORBIDDEN_SAFE_IDS = {"cherry_tomatoes", "помидоры_черри"}

def _is_forbidden(term: str, ingredient_id: str = "") -> str | None:
    """Return the matched forbidden pattern string, or None if safe.
    ingredient_id is checked against the safe-ID allowlist first."""
    if ingredient_id in _FORBIDDEN_SAFE_IDS:
        return None
    for pat in FORBIDDEN_PATTERNS:
        if pat.search(term):
            return pat.pattern
    return None

VALID_UNITS = {"g", "ml", "pcs", "tbsp", "tsp", "cup"}

# ── Per-recipe nutrition bounds (warnings only — values are estimates) ────────
# Ranges represent reasonable per-serving targets for one family member.
NUTRITION_BOUNDS: dict[str, dict] = {
    "breakfast": {"kcal": (220, 560), "protein": (8, None),  "fiber": (2, None)},
    "lunch":     {"kcal": (260, 640), "protein": (15, None), "fiber": (2, None)},
    "dinner":    {"kcal": (320, 720), "protein": (18, None), "fiber": (2, None)},
    "snack":     {"kcal": (70,  400)},
}
VALID_MEAL_TYPES = {"breakfast", "lunch", "dinner", "snack"}
VALID_CATEGORIES = {"produce", "dairy", "meat", "fish", "grains", "legumes", "frozen", "pantry", "other"}
VALID_DAYS_RU = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
REQUIRED_RECIPE_FLAGS = [
    "weekdayFriendly", "leftoversFriendly", "childSafe",
    "containsFish", "containsOmega3Fish", "containsLegumes", "containsRedMeat",
    "containsSoy", "containsEggs", "containsDairy", "highProtein", "highFiber",
]

errors = []
warnings = []


def error(validator, message, target=""):
    errors.append({"validator": validator, "message": message, "target": target})


def warn(validator, message, target=""):
    warnings.append({"validator": validator, "message": message, "target": target})


# ── File loaders ─────────────────────────────────────────────────────────────
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


# ── Validator 1: index.json ───────────────────────────────────────────────────
def validate_index(index):
    v = "validate_index"
    if "weeks" not in index:
        error(v, "Missing 'weeks' array"); return
    if "defaultWeekId" not in index:
        error(v, "Missing 'defaultWeekId'")
    week_ids = set()
    for i, week in enumerate(index["weeks"]):
        for field in ["weekId", "labelRu", "startDate", "endDate", "published"]:
            if field not in week:
                error(v, f"Week[{i}] missing field '{field}'", week.get("weekId", f"[{i}]"))
        wid = week.get("weekId", "")
        if wid:
            if not re.match(r"^\d{4}-W\d{2}$", wid):
                error(v, f"weekId '{wid}' does not match format YYYY-Wnn", wid)
            if wid in week_ids:
                error(v, f"Duplicate weekId '{wid}'", wid)
            week_ids.add(wid)
    default = index.get("defaultWeekId")
    if default and default not in week_ids:
        error(v, f"defaultWeekId '{default}' not found in weeks array", default)


# ── Validator 2: recipes.json ─────────────────────────────────────────────────
def validate_recipes(recipes):
    v = "validate_recipes"
    if not isinstance(recipes, list):
        error(v, "recipes.json must be a JSON array"); return
    seen_ids = set()
    for i, r in enumerate(recipes):
        rid = r.get("id", f"[{i}]")
        if rid in seen_ids:
            error(v, f"Duplicate recipe id '{rid}'", rid)
        seen_ids.add(rid)
        for field in ["id", "nameRu", "mealType", "activeMinutes", "totalMinutes", "servings",
                      "ingredients", "stepsRu", "storageNote", "substitutionsNote", "tags",
                      "nutrition", "flags", "createdAt", "version"]:
            if field not in r:
                error(v, f"Recipe '{rid}' missing field '{field}'", rid)
        if r.get("mealType") not in VALID_MEAL_TYPES:
            error(v, f"Recipe '{rid}' has invalid mealType '{r.get('mealType')}'", rid)
        if not isinstance(r.get("activeMinutes"), int):
            error(v, f"Recipe '{rid}' activeMinutes must be integer", rid)
        if r.get("activeMinutes", 0) > 30 and r.get("flags", {}).get("weekdayFriendly"):
            warn(v, f"Recipe '{rid}' flagged weekdayFriendly but activeMinutes={r['activeMinutes']} > 30", rid)
        for fi, ing in enumerate(r.get("ingredients", [])):
            for f in ["ingredientId", "amount", "unit"]:
                if f not in ing:
                    error(v, f"Recipe '{rid}' ingredient[{fi}] missing '{f}'", rid)
            if ing.get("unit") not in VALID_UNITS:
                error(v, f"Recipe '{rid}' ingredient[{fi}] has invalid unit '{ing.get('unit')}'", rid)
        flags = r.get("flags", {})
        for flag in REQUIRED_RECIPE_FLAGS:
            if flag not in flags:
                error(v, f"Recipe '{rid}' missing flag '{flag}'", rid)
        nutrition = r.get("nutrition", {})
        for nf in ["kcalPerServing", "proteinG", "fatG", "carbsG", "fiberG"]:
            if nf not in nutrition:
                error(v, f"Recipe '{rid}' missing nutrition field '{nf}'", rid)
        if not isinstance(r.get("stepsRu"), list) or len(r.get("stepsRu", [])) == 0:
            error(v, f"Recipe '{rid}' stepsRu must be a non-empty array", rid)
        # Nutrition bounds — warn only, values are estimates
        mt = r.get("mealType", "")
        bounds = NUTRITION_BOUNDS.get(mt, {})
        nutr = r.get("nutrition", {})
        if "kcal" in bounds:
            lo, hi = bounds["kcal"]
            kcal = nutr.get("kcalPerServing", 0)
            if kcal < lo or kcal > hi:
                warn(v, f"Recipe '{rid}' kcalPerServing={kcal} outside expected {lo}–{hi} for {mt}", rid)
        if "protein" in bounds:
            lo, _ = bounds["protein"]
            protein = nutr.get("proteinG", 0)
            if lo and protein < lo:
                warn(v, f"Recipe '{rid}' proteinG={protein} below floor {lo}g for {mt}", rid)
        if "fiber" in bounds:
            lo, _ = bounds["fiber"]
            fiber = nutr.get("fiberG", 0)
            if lo and fiber < lo:
                warn(v, f"Recipe '{rid}' fiberG={fiber} below floor {lo}g for {mt}", rid)
    return seen_ids


# ── Validator 3: allergy safety ───────────────────────────────────────────────
def validate_allergy_safety(recipes, ingredient_map):
    v = "validate_allergy_safety"
    for r in recipes:
        rid = r.get("id", "?")
        for ing in r.get("ingredients", []):
            iid = ing.get("ingredientId", "")
            terms_to_check = [iid]
            if iid in ingredient_map:
                entry = ingredient_map[iid]
                terms_to_check.extend([
                    entry.get("nameEn", ""),
                    entry.get("nameRu", ""),
                    entry.get("nameLt", ""),
                ] + entry.get("aliases", []))
            for term in terms_to_check:
                matched = _is_forbidden(term, ingredient_id=iid)
                if matched:
                    error(v,
                          f"Recipe '{rid}' contains forbidden ingredient '{iid}' (matched '{matched}' in '{term}')",
                          rid)
                    break


# ── Validator 4: ingredient map completeness ──────────────────────────────────
def validate_ingredient_map(recipes, ingredient_map):
    v = "validate_ingredient_map"
    for r in recipes:
        rid = r.get("id", "?")
        for ing in r.get("ingredients", []):
            iid = ing.get("ingredientId", "")
            if iid and iid not in ingredient_map:
                error(v, f"Recipe '{rid}' references unknown ingredientId '{iid}'", rid)


# ── Validator 5: menu week schema and integrity ───────────────────────────────
def validate_menu_week(menu, recipe_ids, ingredient_map):
    v = "validate_menu_week"
    wid = menu.get("weekId", "?")
    if "weekId" not in menu: error(v, "Menu missing 'weekId'")
    if "generatedAt" not in menu: error(v, "Menu missing 'generatedAt'", wid)
    days = menu.get("days", [])
    if len(days) != 7:
        error(v, f"Menu '{wid}' must have exactly 7 days, found {len(days)}", wid)

    for i, day in enumerate(days):
        for field in ["date", "dayNameRu", "meals"]:
            if field not in day:
                error(v, f"Day[{i}] missing field '{field}'", wid)
        if day.get("dayNameRu") not in VALID_DAYS_RU:
            warn(v, f"Day[{i}] dayNameRu '{day.get('dayNameRu')}' is unexpected", wid)
        meals = day.get("meals", {})
        for mt in ["breakfast", "lunch", "dinner"]:
            if mt not in meals:
                error(v, f"Day[{i}] ({day.get('date','?')}) missing meal type '{mt}'", wid)
            meal = meals.get(mt)
            if meal is None:
                error(v, f"Day[{i}] meal '{mt}' is null (only snack may be null)", wid)
                continue
            rid = meal.get("recipeId")
            if not rid:
                error(v, f"Day[{i}] meal '{mt}' missing recipeId", wid)
            elif rid not in recipe_ids:
                error(v, f"Day[{i}] meal '{mt}' references unknown recipeId '{rid}'", wid)
            if meal.get("isLeftover") and not meal.get("sourceDay"):
                error(v, f"Day[{i}] meal '{mt}' isLeftover=true but sourceDay is null", wid)
        # snack may be null
        snack = meals.get("snack")
        if snack is not None:
            rid = snack.get("recipeId")
            if rid and rid not in recipe_ids:
                error(v, f"Day[{i}] snack references unknown recipeId '{rid}'", wid)

    for item in menu.get("shoppingList", []):
        for field in ["ingredientId", "nameRu", "nameLt", "category", "amount", "unit", "neededByDate", "checkboxKey"]:
            if field not in item:
                error(v, f"Shopping item missing field '{field}'", wid)
        if item.get("category") not in VALID_CATEGORIES:
            error(v, f"Shopping item '{item.get('nameRu')}' has invalid category '{item.get('category')}'", wid)
        expected_key = f"{wid}:{item.get('category')}|{item.get('nameRu')}|{item.get('unit')}"
        if item.get("checkboxKey") != expected_key:
            error(v, f"Shopping item checkboxKey mismatch. Expected '{expected_key}', got '{item.get('checkboxKey')}'", wid)


# ── Validator 6: weekly nutrition rules ───────────────────────────────────────
def validate_weekly_rules(menu, recipes_by_id):
    v = "validate_weekly_rules"
    wid = menu.get("weekId", "?")
    fish_meals = 0
    omega3_meals = 0
    legume_meals = 0
    red_meat_meals = 0
    snack_days = 0

    for day in menu.get("days", []):
        has_snack = day.get("meals", {}).get("snack") is not None
        if has_snack:
            snack_days += 1
        for mt, meal in day.get("meals", {}).items():
            if not meal:
                continue
            rid = meal.get("recipeId")
            r = recipes_by_id.get(rid)
            if not r:
                continue
            flags = r.get("flags", {})
            if flags.get("containsFish"):
                fish_meals += 1
            if flags.get("containsOmega3Fish"):
                omega3_meals += 1
            if flags.get("containsLegumes"):
                legume_meals += 1
            if flags.get("containsRedMeat"):
                red_meat_meals += 1

    if omega3_meals < 2:
        error(v, f"Week '{wid}' has {omega3_meals} omega-3 fish meals, minimum is 2", wid)
    if fish_meals < 2:
        error(v, f"Week '{wid}' has {fish_meals} fish meals, minimum is 2", wid)
    if legume_meals < 3:
        error(v, f"Week '{wid}' has {legume_meals} legume meals, minimum is 3", wid)
    if red_meat_meals > 2:
        warn(v, f"Week '{wid}' has {red_meat_meals} red meat meals (cap is 2)", wid)
    if snack_days < 4:
        error(v, f"Week '{wid}' has snacks on {snack_days} days, minimum is 4", wid)


# ── Validator 7: shopping list deduplication ──────────────────────────────────
def validate_shopping_list(menu):
    v = "validate_shopping_list"
    wid = menu.get("weekId", "?")
    seen_keys = set()
    for item in menu.get("shoppingList", []):
        key = item.get("checkboxKey", "")
        if key in seen_keys:
            error(v, f"Duplicate checkboxKey '{key}' in shopping list", wid)
        seen_keys.add(key)


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Validate weekly menu data.")
    parser.add_argument("--week", help="Specific week ID to validate (e.g. 2026-W15)")
    parser.add_argument("--recipes-only", action="store_true", help="Only validate recipes.json")
    parser.add_argument("--json", action="store_true", help="Output JSON report instead of human-readable")
    args = parser.parse_args()

    # Load shared data
    index = load_json(ROOT / "data" / "index.json")
    recipes = load_json(ROOT / "data" / "recipes.json")
    ingredient_map_raw = load_json(ROOT / "data" / "catalog" / "ingredient-map.json")
    ingredient_map = ingredient_map_raw.get("ingredients", {})

    validate_index(index)
    recipe_ids = validate_recipes(recipes) or set()
    validate_allergy_safety(recipes, ingredient_map)
    validate_ingredient_map(recipes, ingredient_map)

    if not args.recipes_only:
        recipes_by_id = {r["id"]: r for r in recipes if "id" in r}
        # Determine which weeks to validate
        weeks_to_check = []
        if args.week:
            weeks_to_check = [args.week]
        else:
            weeks_to_check = [w["weekId"] for w in index.get("weeks", [])]

        for wid in weeks_to_check:
            menu_path = ROOT / "data" / "menus" / f"{wid}.json"
            if not menu_path.exists():
                error("validate_menu_week", f"Menu file not found: {menu_path}", wid)
                continue
            menu = load_json(menu_path)
            validate_menu_week(menu, recipe_ids, ingredient_map)
            validate_weekly_rules(menu, recipes_by_id)
            validate_shopping_list(menu)

    passed = len(errors) == 0
    report = {"passed": passed, "errors": errors, "warnings": warnings}

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        if passed:
            print(f"PASS All validators passed ({len(warnings)} warning(s))")
        else:
            print(f"FAIL {len(errors)} error(s), {len(warnings)} warning(s)")
        for e in errors:
            print(f"  ERROR [{e['validator']}] {e['message']}" + (f" (target: {e['target']})" if e['target'] else ""))
        for w in warnings:
            print(f"  WARN  [{w['validator']}] {w['message']}" + (f" (target: {w['target']})" if w['target'] else ""))

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
