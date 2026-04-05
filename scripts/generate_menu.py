#!/usr/bin/env python3
"""
generate_menu.py — Generate a weekly menu from the recipe library.

Usage:
  python scripts/generate_menu.py --week 2026-W16

Algorithm:
  1. Load recipe library, last 4 menu files, ingredient map
  2. Build candidate pools per meal type (filter hard constraints)
  3. Apply 2-week hard exclusion from recent menus
  4. Greedy selection with variety and nutrition enforcement
  5. Score the candidate plan
  6. If hard rejects: print failure report, EXIT (no file written)
  7. If passed: run aggregate_shopping, validate, write menu file

Exit codes:
  0  Menu written successfully
  1  Validation failure (report printed)
  2  Fatal error (file not found)
  3  Insufficient recipe library (NEED_RECIPE emitted) — caller must generate recipes then retry
"""

import json
import sys
import argparse
import random
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from scripts.score_plan import score_plan, dominant_protein

FAMILY_SERVINGS = 3
DAYS_RU = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
WEEKDAY_INDICES = {0, 1, 2, 3, 4}  # Mon=0 ... Fri=4


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


def week_days(week_id: str):
    """Return list of 7 date strings (Mon–Sun) for the given ISO week ID."""
    year, week = week_id.split("-W")
    monday = datetime.strptime(f"{year}-W{int(week):02d}-1", "%G-W%V-%u").date()
    return [str(monday + timedelta(days=i)) for i in range(7)]


def load_recent_menus(week_id: str, count: int = 4):
    """Load up to `count` most recent menu files before the given week."""
    menus_dir = ROOT / "data" / "menus"
    files = sorted(menus_dir.glob("*.json"), reverse=True)
    recent = []
    for f in files:
        if f.stem == week_id:
            continue
        if len(recent) >= count:
            break
        try:
            menu = load_json(f)
            recent.append(menu)
        except SystemExit:
            continue
    return recent


def build_exclusion_sets(recent_menus):
    """Build hard_exclude (weeks 1–2) and soft_exclude (weeks 3–4) sets per meal type."""
    hard_exclude = {"dinner": set(), "breakfast": set(), "lunch": set(), "snack": set()}
    soft_exclude = {"dinner": set(), "breakfast": set(), "lunch": set(), "snack": set()}

    for i, menu in enumerate(recent_menus[:4]):
        target = hard_exclude if i < 2 else soft_exclude
        for day in menu.get("days", []):
            for mt, meal in day.get("meals", {}).items():
                if meal and meal.get("recipeId"):
                    target.get(mt, target["dinner"]).add(meal["recipeId"])

    return hard_exclude, soft_exclude


def filter_pool(recipes, meal_type, hard_exclude_ids, is_weekday_context=False):
    """Return candidate recipes for the given meal type, applying hard constraints."""
    pool = []
    for r in recipes:
        if r.get("mealType") != meal_type:
            continue
        if r["id"] in hard_exclude_ids:
            continue
        if not r.get("flags", {}).get("childSafe", True):
            continue
        if is_weekday_context and not r.get("flags", {}).get("weekdayFriendly", True):
            continue
        pool.append(r)
    return pool


def select_dinners(pool, days, ingredient_map, recipes_by_id,
                   min_omega3=2, min_legumes=3, max_red_meat=2):
    """
    Select 7 dinners satisfying nutritional minimums.
    Prevents consecutive same-protein days.
    Returns (assignments, errors) where errors is a list of NEED_RECIPE strings.
    """
    omega3_pool   = [r for r in pool if r.get("flags", {}).get("containsOmega3Fish")]
    legume_pool   = [r for r in pool if r.get("flags", {}).get("containsLegumes") and not r.get("flags", {}).get("containsOmega3Fish")]
    other_pool    = [r for r in pool if not r.get("flags", {}).get("containsOmega3Fish") and not r.get("flags", {}).get("containsLegumes")]

    other_needed = 7 - min_omega3 - min_legumes
    errors = []
    if len(omega3_pool) < min_omega3:
        errors.append(f"NEED_RECIPE: dinner, containsOmega3Fish=true (have {len(omega3_pool)}, need {min_omega3})")
    if len(legume_pool) < min_legumes:
        errors.append(f"NEED_RECIPE: dinner, containsLegumes=true (have {len(legume_pool)}, need {min_legumes})")
    if len(other_pool) < other_needed:
        errors.append(f"NEED_RECIPE: dinner, general (have {len(other_pool)}, need {other_needed})")
    if errors:
        return None, errors

    random.shuffle(omega3_pool)
    random.shuffle(legume_pool)
    random.shuffle(other_pool)

    assignments = []
    used = set()
    prev_protein = None

    # Build a prioritised slot queue: place required types at spreading positions
    slot_plan = [None] * 7
    omega3_positions = [1, 4][:min_omega3]
    legume_positions = [2, 5, 6][:min_legumes]
    for pos in omega3_positions:
        slot_plan[pos] = "omega3"
    for pos in legume_positions:
        if slot_plan[pos] is None:
            slot_plan[pos] = "legume"
    for i in range(7):
        if slot_plan[i] is None:
            slot_plan[i] = "other"

    def pick(pool_list, used_set, prev_pcat, ingredient_map):
        for r in pool_list:
            if r["id"] in used_set:
                continue
            pcat = dominant_protein(r, ingredient_map)
            if pcat == prev_pcat and pcat not in ("other", None):
                continue
            return r
        # Relax consecutive constraint if no other choice
        for r in pool_list:
            if r["id"] not in used_set:
                return r
        return None

    for i, day in enumerate(days):
        slot_type = slot_plan[i]
        if slot_type == "omega3":
            chosen = pick(omega3_pool, used, prev_protein, ingredient_map)
        elif slot_type == "legume":
            chosen = pick(legume_pool, used, prev_protein, ingredient_map)
        else:
            chosen = pick(other_pool, used, prev_protein, ingredient_map)
            if not chosen:
                chosen = pick(legume_pool, used, prev_protein, ingredient_map)
            if not chosen:
                chosen = pick(omega3_pool, used, prev_protein, ingredient_map)

        if not chosen:
            return None, f"NEED_RECIPE: dinner slot {i} ({day}) could not be filled"

        assignments.append({"day": day, "recipeId": chosen["id"]})
        used.add(chosen["id"])
        prev_protein = dominant_protein(chosen, ingredient_map)

    return assignments, None


def main():
    parser = argparse.ArgumentParser(description="Generate a weekly menu.")
    parser.add_argument("--week", required=True, help="Week ID (e.g. 2026-W16)")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    week_id = args.week
    days = week_days(week_id)

    recipes_list = load_json(ROOT / "data" / "recipes.json")
    ingredient_map_raw = load_json(ROOT / "data" / "catalog" / "ingredient-map.json")
    ingredient_map = ingredient_map_raw.get("ingredients", {})
    recipes_by_id = {r["id"]: r for r in recipes_list}

    recent_menus = load_recent_menus(week_id)
    hard_exclude, soft_exclude = build_exclusion_sets(recent_menus)

    need_recipe_signals = []

    # ── Select breakfasts ──────────────────────────────────────────────────────
    bfast_pool = filter_pool(recipes_list, "breakfast", hard_exclude["breakfast"])
    if len(bfast_pool) < 7:
        need_recipe_signals.append(
            f"NEED_RECIPE: breakfast (have {len(bfast_pool)} candidates, need 7 distinct)")
    random.shuffle(bfast_pool)

    breakfasts = []
    bfast_used = set()
    prev_bfast = None
    bfast_pool_cycle = list(bfast_pool)
    for i, day in enumerate(days):
        # No same breakfast two days in a row
        chosen = None
        for r in bfast_pool_cycle:
            if r["id"] != prev_bfast and r["id"] not in bfast_used:
                chosen = r
                break
        if not chosen:
            for r in bfast_pool_cycle:
                if r["id"] not in bfast_used:
                    chosen = r
                    break
        if not chosen and bfast_pool_cycle:
            chosen = bfast_pool_cycle[i % len(bfast_pool_cycle)]
        if chosen:
            breakfasts.append({"day": day, "recipeId": chosen["id"]})
            bfast_used.add(chosen["id"])
            prev_bfast = chosen["id"]

    # ── Select dinners ─────────────────────────────────────────────────────────
    dinner_pool = filter_pool(recipes_list, "dinner", hard_exclude["dinner"])
    dinner_assignments, dinner_errors = select_dinners(
        dinner_pool, days, ingredient_map, recipes_by_id)

    if dinner_errors:
        need_recipe_signals.extend(dinner_errors)

    # ── Pre-check lunch pool (before bail-out so all signals surface at once) ──
    lunch_pool = filter_pool(recipes_list, "lunch", hard_exclude["lunch"])
    # Need enough distinct lunches to cover non-leftover days (max 4 leftover slots → min 3 distinct)
    MIN_LUNCH_DISTINCT = 3
    if len(lunch_pool) < MIN_LUNCH_DISTINCT:
        need_recipe_signals.append(
            f"NEED_RECIPE: lunch (have {len(lunch_pool)} candidates, need {MIN_LUNCH_DISTINCT} distinct)")

    # ── Pre-check snack pool ───────────────────────────────────────────────────
    snack_pool = filter_pool(recipes_list, "snack", hard_exclude["snack"])
    MIN_SNACK_DISTINCT = 3
    if len(snack_pool) < MIN_SNACK_DISTINCT:
        need_recipe_signals.append(
            f"NEED_RECIPE: snack (have {len(snack_pool)} candidates, need {MIN_SNACK_DISTINCT} distinct)")

    # ── If library insufficient, bail out ─────────────────────────────────────
    if need_recipe_signals:
        print("LIBRARY INSUFFICIENT — generation cannot proceed.\n")
        for signal in need_recipe_signals:
            print(f"  {signal}")
        print("\nRun /add-recipe or the recipe-generator agent for each NEED_RECIPE signal, then retry.")
        sys.exit(3)

    # ── Assign lunches (leftovers first, then from lunch pool) ────────────────
    leftover_dinners = {a["day"]: a["recipeId"] for a in dinner_assignments
                        if recipes_by_id.get(a["recipeId"], {}).get("flags", {}).get("leftoversFriendly")}

    random.shuffle(lunch_pool)
    lunch_pool_cycle = list(lunch_pool)

    lunches = []
    leftover_days_used = 0
    lunch_used = set()
    for i, day in enumerate(days):
        # Use leftover from previous day's dinner if available
        prev_day = days[i - 1] if i > 0 else None
        if prev_day and prev_day in leftover_dinners and leftover_days_used < 4:
            source_rid = leftover_dinners[prev_day]
            lunches.append({
                "day": day,
                "recipeId": source_rid,
                "isLeftover": True,
                "sourceDay": prev_day,
            })
            leftover_days_used += 1
        else:
            # Pick from lunch pool
            chosen = None
            for r in lunch_pool_cycle:
                if r["id"] not in lunch_used:
                    chosen = r
                    break
            if chosen:
                lunches.append({"day": day, "recipeId": chosen["id"], "isLeftover": False, "sourceDay": None})
                lunch_used.add(chosen["id"])
            elif lunch_pool_cycle:
                # Recycle if pool exhausted
                lunches.append({"day": day, "recipeId": lunch_pool_cycle[i % len(lunch_pool_cycle)]["id"],
                                "isLeftover": False, "sourceDay": None})
            else:
                # Use leftover as fallback
                if prev_day and prev_day in leftover_dinners:
                    lunches.append({"day": day, "recipeId": leftover_dinners[prev_day],
                                    "isLeftover": True, "sourceDay": prev_day})
                else:
                    # Last resort: any dinner leftover — find correct sourceDay
                    fallback_day = next(iter(leftover_dinners.keys()), None)
                    if fallback_day:
                        lunches.append({"day": day, "recipeId": leftover_dinners[fallback_day],
                                        "isLeftover": True, "sourceDay": fallback_day})

    # ── Assign snacks (at least 4 days) ───────────────────────────────────────
    random.shuffle(snack_pool)

    # Pick snack days: prefer Mon/Wed/Fri/Sat/Sun for spread
    preferred_snack_positions = [0, 2, 4, 5, 6, 1, 3]
    snacks = []
    snack_count = 0
    snack_used = set()
    for pos in preferred_snack_positions:
        if snack_count >= 5:
            break
        day = days[pos]
        chosen = None
        for r in snack_pool:
            if r["id"] not in snack_used:
                chosen = r
                break
        if not chosen and snack_pool:
            chosen = snack_pool[snack_count % len(snack_pool)]
        if chosen:
            snacks.append({"day": day, "recipeId": chosen["id"]})
            snack_used.add(chosen["id"])
            snack_count += 1

    # ── Build candidate plan ───────────────────────────────────────────────────
    candidate = {
        "weekId": week_id,
        "breakfasts": breakfasts,
        "lunches": lunches,
        "dinners": dinner_assignments,
        "snacks": snacks,
    }

    # ── Score the plan ─────────────────────────────────────────────────────────
    report = score_plan(candidate, recipes_by_id, ingredient_map, recent_menus)

    if not report["passed"]:
        print("GENERATION FAILED — hard rejects:\n")
        for reject in report["hardRejects"]:
            print(f"  [{reject['rule']}] {reject['message']}")
        print("\nRepair the identified slots and retry. Use /swap-meal for targeted fixes.")
        sys.exit(1)

    if report["softPenalties"]:
        print(f"Score: {report['totalScore']}/100 (soft penalties applied)")
        for rule, pts in report["softPenalties"].items():
            print(f"  -{pts} {rule}")

    # ── Convert candidate to full menu format ──────────────────────────────────
    # Build day map
    by_day = {day: {} for day in days}
    for e in breakfasts:   by_day[e["day"]]["breakfast"] = e
    for e in lunches:      by_day[e["day"]]["lunch"] = e
    for e in dinner_assignments: by_day[e["day"]]["dinner"] = e
    for e in snacks:       by_day[e["day"]]["snack"] = e

    menu_days = []
    for i, day in enumerate(days):
        d = by_day[day]
        def meal_obj(entry, mt):
            if not entry:
                return None
            return {
                "recipeId": entry["recipeId"],
                "isLeftover": entry.get("isLeftover", False),
                "sourceDay": entry.get("sourceDay", None),
            }
        menu_days.append({
            "date": day,
            "dayNameRu": DAYS_RU[i],
            "meals": {
                "breakfast": meal_obj(d.get("breakfast"), "breakfast"),
                "lunch":     meal_obj(d.get("lunch"), "lunch"),
                "dinner":    meal_obj(d.get("dinner"), "dinner"),
                "snack":     meal_obj(d.get("snack"), "snack"),
            }
        })

    # Compute score report fields
    all_rids = ([e["recipeId"] for e in breakfasts] + [e["recipeId"] for e in lunches] +
                [e["recipeId"] for e in dinner_assignments] + [e["recipeId"] for e in snacks])
    fish_count    = sum(1 for rid in all_rids if recipes_by_id.get(rid, {}).get("flags", {}).get("containsFish"))
    legume_count  = sum(1 for rid in all_rids if recipes_by_id.get(rid, {}).get("flags", {}).get("containsLegumes"))
    red_meat_count= sum(1 for rid in all_rids if recipes_by_id.get(rid, {}).get("flags", {}).get("containsRedMeat"))

    menu = {
        "weekId": week_id,
        "generatedAt": datetime.now().astimezone().isoformat(),
        "days": menu_days,
        "shoppingList": [],  # filled by aggregate_shopping below
        "scoreReport": {
            "fishMeals": fish_count,
            "legumeMeals": legume_count,
            "redMeatMeals": red_meat_count,
            "snackDays": len(snacks),
            "warnings": [f"{k}: -{v}" for k, v in report["softPenalties"].items()],
        },
    }

    # ── Write menu file ────────────────────────────────────────────────────────
    out_path = ROOT / "data" / "menus" / f"{week_id}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(menu, f, ensure_ascii=False, indent=2)
    print(f"OK Menu written: {out_path}")

    # ── Run aggregate_shopping ─────────────────────────────────────────────────
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "aggregate_shopping.py"), "--week", week_id],
        cwd=str(ROOT),
    )
    if result.returncode != 0:
        print("WARN: aggregate_shopping.py reported issues — check ingredient-map.json")

    # ── Run validate_data ──────────────────────────────────────────────────────
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate_data.py"), "--week", week_id],
        cwd=str(ROOT),
    )
    if result.returncode != 0:
        print("FAIL Validation failed after generation. Review errors above.")
        sys.exit(1)

    # ── Run sync_index ─────────────────────────────────────────────────────────
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "sync_index.py")],
        cwd=str(ROOT),
    )

    print(f"\nOK Week {week_id} generated successfully.")
    print(f"  Breakfasts: {len(breakfasts)} | Dinners: {len(dinner_assignments)} | "
          f"Lunches: {len(lunches)} ({leftover_days_used} leftovers) | Snacks: {len(snacks)}")
    print(f"  Fish: {fish_count} | Legumes: {legume_count} | Red meat: {red_meat_count}")
    sys.exit(0)


if __name__ == "__main__":
    main()
