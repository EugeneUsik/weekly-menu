#!/usr/bin/env python3
"""
score_plan.py — Score a candidate weekly plan against hard and soft rules.

Usage (as a module):
  from scripts.score_plan import score_plan

Or standalone:
  python scripts/score_plan.py --plan candidate.json --week 2026-W15

Returns a report dict:
  {
    "hardRejects": [{"rule": str, "message": str}],
    "softPenalties": {rule_name: int},
    "totalScore": int,   # 100 - sum of penalties (hard reject = -999)
    "passed": bool,      # True only when hardRejects is empty
  }
"""

import json
import sys
import argparse
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).parent.parent

# Protein category mapping (by ingredient category in ingredient-map)
# Used to detect consecutive same-protein dinners
PROTEIN_CATEGORY_MAP = {
    "fish":    "fish",
    "meat":    None,   # resolved per-ingredient below
    "legumes": "legume",
    "dairy":   "dairy",
}

RED_MEAT_INGREDIENT_KEYWORDS = {"beef", "pork", "lamb", "veal", "говядина", "свинина", "баранина", "телятина"}
CHICKEN_INGREDIENT_KEYWORDS  = {"chicken", "курица", "куриц", "chicken_breast", "chicken_thigh", "chicken_drum"}

# Child allergies: apples, prunes/plums, peaches, apricots.
# Word-boundary patterns prevent false positives (e.g. "pineapple" ≠ "apple").
import re as _re

_FORBIDDEN_PATTERNS = [
    _re.compile(r'\bapple\b', _re.IGNORECASE),
    _re.compile(r'\bapples\b', _re.IGNORECASE),
    _re.compile(r'\bяблоко\b', _re.IGNORECASE),
    _re.compile(r'\bяблоки\b', _re.IGNORECASE),
    _re.compile(r'\bяблочн', _re.IGNORECASE),
    _re.compile(r'\bprune\b', _re.IGNORECASE),
    _re.compile(r'\bprunes\b', _re.IGNORECASE),
    _re.compile(r'\bplum\b', _re.IGNORECASE),
    _re.compile(r'\bplums\b', _re.IGNORECASE),
    _re.compile(r'\bчернослив', _re.IGNORECASE),
    _re.compile(r'\bслива\b', _re.IGNORECASE),
    _re.compile(r'\bсливы\b', _re.IGNORECASE),
    _re.compile(r'\bapricot\b', _re.IGNORECASE),
    _re.compile(r'\bapricots\b', _re.IGNORECASE),
    _re.compile(r'\bабрикос', _re.IGNORECASE),
    _re.compile(r'\bpeach\b', _re.IGNORECASE),
    _re.compile(r'\bpeaches\b', _re.IGNORECASE),
    _re.compile(r'\bперсик', _re.IGNORECASE),
]

def _is_forbidden(term: str) -> bool:
    return any(p.search(term) for p in _FORBIDDEN_PATTERNS)

SOFT_PENALTY_WEIGHTS = {
    "protein_below_target":        10,
    "fish_count_below_2":          15,
    "omega3_count_below_2":        15,
    "legume_count_below_3":        15,
    "red_meat_above_2":            10,
    "low_snack_coverage":          10,
    "dinner_repeated_week3_4":     20,
    "breakfast_repeated_week3_4":  10,
    "consecutive_same_protein":    12,
    "same_breakfast_consecutive":   8,
    "low_lunch_variety":           10,
    "low_breakfast_variety":       10,
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


def ingredient_protein_category(iid: str, ingredient_map: dict) -> str:
    """Return a protein category label for an ingredient ID."""
    entry = ingredient_map.get(iid, {})
    cat = entry.get("category", "other")
    if cat == "fish":
        return "fish"
    if cat == "legumes":
        return "legume"
    if cat == "dairy":
        return "dairy"
    if cat == "meat":
        lower = iid.lower()
        for kw in CHICKEN_INGREDIENT_KEYWORDS:
            if kw in lower:
                return "chicken"
        for kw in RED_MEAT_INGREDIENT_KEYWORDS:
            if kw in lower:
                return "redmeat"
        return "other_meat"
    return "other"


def dominant_protein(recipe: dict, ingredient_map: dict) -> str:
    """Return the dominant protein category of a recipe."""
    flags = recipe.get("flags", {})
    if flags.get("containsFish"):
        return "fish"
    if flags.get("containsLegumes") and not flags.get("containsRedMeat"):
        return "legume"
    # Fall back to ingredient scanning
    categories = [ingredient_protein_category(i["ingredientId"], ingredient_map)
                  for i in recipe.get("ingredients", [])]
    for priority in ["redmeat", "chicken", "other_meat", "legume", "dairy", "other"]:
        if priority in categories:
            return priority
    return "other"


def score_plan(candidate: dict, recipes_by_id: dict, ingredient_map: dict,
               recent_menus: list) -> dict:
    """
    Score a candidate plan object (intermediate schema §18.1).

    candidate = {
      "weekId": str,
      "breakfasts": [{"day": date_str, "recipeId": str}],
      "lunches":    [{"day": date_str, "recipeId": str, "isLeftover": bool, "sourceDay": str|None}],
      "dinners":    [{"day": date_str, "recipeId": str}],
      "snacks":     [{"day": date_str, "recipeId": str}],
    }

    recent_menus: list of menu dicts from previous weeks (most recent first)
    """
    hard_rejects = []
    soft_penalties = defaultdict(int)

    def hard(rule, msg):
        hard_rejects.append({"rule": rule, "message": msg})

    def soft(rule):
        soft_penalties[rule] += SOFT_PENALTY_WEIGHTS.get(rule, 5)

    week_id = candidate.get("weekId", "?")
    all_days_sorted = sorted(set(
        [e["day"] for e in candidate.get("breakfasts", [])] +
        [e["day"] for e in candidate.get("dinners", [])]
    ))

    # Build lookup: day -> recipeId per meal type
    breakfasts = {e["day"]: e["recipeId"] for e in candidate.get("breakfasts", [])}
    dinners    = {e["day"]: e["recipeId"] for e in candidate.get("dinners", [])}
    lunches    = {e["day"]: e for e in candidate.get("lunches", [])}
    snacks     = {e["day"]: e["recipeId"] for e in candidate.get("snacks", [])}

    # History: collect recipeIds from recent menus by week offset
    history_by_week = []  # [week-1 ids, week-2 ids, week-3 ids, week-4 ids]
    for menu in recent_menus[:4]:
        ids = set()
        for day in menu.get("days", []):
            for mt, meal in day.get("meals", {}).items():
                if meal and meal.get("recipeId"):
                    ids.add(meal["recipeId"])
        history_by_week.append(ids)

    hard_exclude = set()
    for ids in history_by_week[:2]:
        hard_exclude |= ids
    soft_exclude = set()
    for ids in history_by_week[2:4]:
        soft_exclude |= ids

    # ── All recipe IDs used this week ─────────────────────────────────────────
    # Leftover lunches intentionally repeat a dinner recipe — exclude from repeat checks.
    non_leftover_lunches = [v["recipeId"] for v in lunches.values()
                            if "recipeId" in v and not v.get("isLeftover")]
    all_this_week = (
        list(breakfasts.values()) + list(dinners.values()) +
        non_leftover_lunches + list(snacks.values())
    )

    # 1. Hard: allergy violations
    for rid in all_this_week:
        recipe = recipes_by_id.get(rid)
        if not recipe:
            hard("missing_recipe_reference", f"recipeId '{rid}' not found in library")
            continue
        for ing in recipe.get("ingredients", []):
            iid = ing.get("ingredientId", "")
            entry = ingredient_map.get(iid, {})
            terms = [iid, entry.get("nameEn", ""), entry.get("nameRu", "")] + entry.get("aliases", [])
            for term in terms:
                if _is_forbidden(term):
                    hard("allergy_violation",
                         f"Recipe '{rid}' contains forbidden ingredient '{iid}' (matched in '{term}')")

    # 2. Hard: missing ingredient mapping
    for rid in all_this_week:
        recipe = recipes_by_id.get(rid)
        if not recipe:
            continue
        for ing in recipe.get("ingredients", []):
            iid = ing.get("ingredientId", "")
            if iid and iid not in ingredient_map:
                hard("missing_ingredient_mapping",
                     f"Recipe '{rid}' ingredient '{iid}' not in ingredient-map.json")

    # 3. Hard: weekday prep time limit (Mon–Fri)
    WEEKDAY_DATES = set(all_days_sorted[:5]) if len(all_days_sorted) >= 5 else set(all_days_sorted)
    for day, rid in dinners.items():
        recipe = recipes_by_id.get(rid)
        if recipe and day in WEEKDAY_DATES:
            if recipe.get("activeMinutes", 0) > 30 and not recipe.get("flags", {}).get("weekdayFriendly"):
                hard("weekday_prep_over_limit",
                     f"Dinner '{rid}' on {day} has activeMinutes={recipe['activeMinutes']} > 30 on weekday")

    # 4. Hard: no same recipe twice in same week (breakfasts, dinners, non-leftover lunches only)
    # Snacks may repeat if the library is small — soft penalise instead.
    seen_main = set()
    seen_snack = set()
    for rid in list(breakfasts.values()) + list(dinners.values()) + non_leftover_lunches:
        if rid in seen_main:
            hard("recipe_repeated_in_week", f"Recipe '{rid}' appears more than once in the week")
        seen_main.add(rid)
    snack_repeats = 0
    for rid in snacks.values():
        if rid in seen_snack:
            snack_repeats += 1
        seen_snack.add(rid)
    if snack_repeats > 0:
        soft_penalties["snack_recipe_repeated"] = snack_repeats * 5

    # 5. Hard: dinner or breakfast from last 2 weeks
    for day, rid in dinners.items():
        if rid in hard_exclude:
            hard("dinner_in_2week_exclusion",
                 f"Dinner '{rid}' on {day} was used in the previous 2 weeks")
    for day, rid in breakfasts.items():
        if rid in hard_exclude:
            hard("breakfast_in_2week_exclusion",
                 f"Breakfast '{rid}' on {day} was used in the previous 2 weeks")

    # 6. Hard: consecutive same-protein dinner days (fish/chicken/meat only — legumes ok consecutive)
    prev_protein = None
    for day in all_days_sorted:
        rid = dinners.get(day)
        recipe = recipes_by_id.get(rid) if rid else None
        if recipe:
            pcat = dominant_protein(recipe, ingredient_map)
            if pcat == prev_protein and pcat not in ("other", "legume", None):
                hard("consecutive_same_protein_dinner",
                     f"Dinner on {day} ('{rid}') has same protein category '{pcat}' as previous day")
            prev_protein = pcat
        else:
            prev_protein = None

    # 7. Hard: same breakfast two consecutive days
    prev_breakfast = None
    for day in all_days_sorted:
        rid = breakfasts.get(day)
        if rid and rid == prev_breakfast:
            hard("same_breakfast_consecutive",
                 f"Breakfast '{rid}' repeats on consecutive day {day}")
        prev_breakfast = rid

    # ── Soft penalties ────────────────────────────────────────────────────────
    fish_meals = sum(1 for rid in all_this_week if recipes_by_id.get(rid, {}).get("flags", {}).get("containsFish"))
    omega3_meals = sum(1 for rid in all_this_week if recipes_by_id.get(rid, {}).get("flags", {}).get("containsOmega3Fish"))
    legume_meals = sum(1 for rid in all_this_week if recipes_by_id.get(rid, {}).get("flags", {}).get("containsLegumes"))
    red_meat_meals = sum(1 for rid in all_this_week if recipes_by_id.get(rid, {}).get("flags", {}).get("containsRedMeat"))

    if fish_meals < 2:   soft("fish_count_below_2")
    if omega3_meals < 2: soft("omega3_count_below_2")
    if legume_meals < 3: soft("legume_count_below_3")
    if red_meat_meals > 2: soft("red_meat_above_2")
    if len(snacks) < 4:  soft("low_snack_coverage")

    # Soft: dinner/breakfast in weeks 3–4 lookback
    for day, rid in dinners.items():
        if rid in soft_exclude:
            soft("dinner_repeated_week3_4")
    for day, rid in breakfasts.items():
        if rid in soft_exclude:
            soft("breakfast_repeated_week3_4")

    # Compute total score
    total_penalty = sum(soft_penalties.values())
    total_score = max(0, 100 - total_penalty)
    passed = len(hard_rejects) == 0

    return {
        "hardRejects": hard_rejects,
        "softPenalties": dict(soft_penalties),
        "totalScore": total_score,
        "passed": passed,
    }


def main():
    parser = argparse.ArgumentParser(description="Score a candidate weekly plan.")
    parser.add_argument("--plan", required=True, help="Path to candidate plan JSON file")
    parser.add_argument("--recent-menus", nargs="*", default=[], help="Paths to recent menu JSON files (most recent first)")
    args = parser.parse_args()

    candidate = load_json(Path(args.plan))
    recipes_list = load_json(ROOT / "data" / "recipes.json")
    ingredient_map_raw = load_json(ROOT / "data" / "catalog" / "ingredient-map.json")

    recipes_by_id = {r["id"]: r for r in recipes_list}
    ingredient_map = ingredient_map_raw.get("ingredients", {})
    recent_menus = [load_json(Path(p)) for p in args.recent_menus]

    report = score_plan(candidate, recipes_by_id, ingredient_map, recent_menus)

    print(json.dumps(report, ensure_ascii=False, indent=2))
    sys.exit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
