#!/usr/bin/env python3
"""
normalize_catalog.py — Normalize a raw Barbora catalog snapshot into ingredient-map.json.

Usage:
  python scripts/normalize_catalog.py --input data/catalog/raw/2026-04-01.json [--force]

Raw snapshot format (place Barbora export here):
  {
    "products": [
      { "name": "Lašišos filė", "category": "Žuvis", "unit": "kg", "price": 12.99 }
    ]
  }

Processing:
  1. Normalize Barbora category names to internal category enum
  2. Attempt alias matching against existing ingredient-map entries
  3. Report unmatched products for manual mapping
  4. Update ingredient-map.json (never overwrites existing entries without --force)

Exit codes:
  0  Success
  1  Unmatched products found (check output)
  2  Fatal error
"""

import json
import sys
import argparse
from pathlib import Path

ROOT = Path(__file__).parent.parent

# Barbora Lithuanian category name substrings → internal category enum.
# Listed longest/most-specific first so earlier entries win on overlap.
# Matching is case-insensitive substring: first hit wins.
CATEGORY_RULES = [
    # Fish & seafood
    ("jūros gėrybės",    "fish"),
    ("žuvis",            "fish"),
    # Meat & poultry
    ("paukštiena",       "meat"),
    ("mėsos gaminiai",   "meat"),
    ("mėsa",             "meat"),
    # Dairy & eggs
    ("kiaušiniai",       "dairy"),
    ("pieno",            "dairy"),
    ("sūriai",           "dairy"),
    ("sūris",            "dairy"),
    ("jogurtas",         "dairy"),
    ("grietinė",         "dairy"),
    ("sviestas",         "dairy"),
    # Produce
    ("daržovės",         "produce"),
    ("vaisiai",          "produce"),
    ("žalumynai",        "produce"),
    ("grybai",           "produce"),
    # Grains & pasta
    ("makaronai",        "grains"),
    ("kruopos",          "grains"),
    ("miltai",           "grains"),
    ("duona",            "grains"),
    ("ryžiai",           "grains"),
    ("grūdiniai",        "grains"),
    ("grūdai",           "grains"),
    # Legumes
    ("ankštiniai",       "legumes"),
    ("pupelės",          "legumes"),
    ("žirniai",          "legumes"),
    # Frozen
    ("šaldyti",          "frozen"),
    ("šaldyta",          "frozen"),
    # Pantry
    ("aliejai",          "pantry"),
    ("riebalai",         "pantry"),
    ("prieskoniai",      "pantry"),
    ("padažai",          "pantry"),
    ("konservai",        "pantry"),
    ("saldumynai",       "pantry"),
    ("cukrus",           "pantry"),
    ("druska",           "pantry"),
    ("actas",            "pantry"),
    ("sultys",           "pantry"),
    ("gėrimai",          "pantry"),
    ("kava",             "pantry"),
    ("arbata",           "pantry"),
]

# Legacy exact-match map kept for backwards compatibility
_LEGACY_CATEGORY_MAP = {
    "Žuvis": "fish",
    "Žuvis ir jūros gėrybės": "fish",
    "Mėsa": "meat",
    "Mėsos gaminiai": "meat",
    "Paukštiena": "meat",
    "Pieno produktai": "dairy",
    "Sūriai": "dairy",
    "Kiaušiniai": "dairy",
    "Daržovės": "produce",
    "Vaisiai": "produce",
    "Žalumynai": "produce",
    "Grūdiniai produktai": "grains",
    "Kruopos": "grains",
    "Makaronai": "grains",
    "Ankštiniai": "legumes",
    "Šaldyti produktai": "frozen",
    "Aliejai ir riebalai": "pantry",
    "Prieskoniai": "pantry",
    "Konservai": "pantry",
    "Saldumynai": "pantry",
    "Kita": "other",
}


def map_category(barbora_cat: str) -> str:
    """Map a Barbora category name to an internal category enum value."""
    # Exact match first (legacy)
    if barbora_cat in _LEGACY_CATEGORY_MAP:
        return _LEGACY_CATEGORY_MAP[barbora_cat]
    # Substring match (case-insensitive), longest-specific rules listed first
    lower = barbora_cat.lower()
    for substring, internal in CATEGORY_RULES:
        if substring in lower:
            return internal
    return "other"


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


def normalize_unit(raw_unit: str) -> str:
    """Convert Barbora unit strings to internal unit enum."""
    unit_map = {
        "kg": "g",  # we store in grams; price data uses kg
        "g": "g",
        "l": "ml",
        "ml": "ml",
        "vnt": "pcs",
        "vnt.": "pcs",
        "pcs": "pcs",
    }
    return unit_map.get(raw_unit.lower().strip(), "g")


def build_alias_index(ingredient_map: dict) -> dict:
    """Build a lowercase alias → ingredient_id lookup for matching."""
    index = {}
    for iid, entry in ingredient_map.items():
        for term in [entry.get("nameLt", ""), entry.get("nameEn", ""), entry.get("nameRu", "")] + entry.get("aliases", []):
            if term:
                index[term.lower().strip()] = iid
    return index


def main():
    parser = argparse.ArgumentParser(description="Normalize Barbora catalog snapshot.")
    parser.add_argument("--input", required=True, help="Path to raw snapshot JSON")
    parser.add_argument("--force", action="store_true", help="Overwrite existing ingredient-map entries")
    parser.add_argument("--dry-run", action="store_true", help="Do not write to ingredient-map.json")
    args = parser.parse_args()

    raw_path = Path(args.input)
    if not raw_path.is_absolute():
        raw_path = ROOT / raw_path

    raw = load_json(raw_path)
    products = raw.get("products", [])

    map_path = ROOT / "data" / "catalog" / "ingredient-map.json"
    ingredient_map_file = load_json(map_path)
    ingredient_map = ingredient_map_file.get("ingredients", {})

    alias_index = build_alias_index(ingredient_map)

    matched = []
    unmatched = []

    for product in products:
        name_lt = product.get("name", "").strip()
        barbora_cat = product.get("category", "")
        raw_unit = product.get("unit", "g")

        internal_category = map_category(barbora_cat)
        internal_unit = normalize_unit(raw_unit)

        # Try exact match by Lithuanian name
        lower_name = name_lt.lower()
        matched_id = alias_index.get(lower_name)

        # Try partial match if exact fails
        if not matched_id:
            for alias, iid in alias_index.items():
                if alias in lower_name or lower_name in alias:
                    matched_id = iid
                    break

        if matched_id:
            entry = ingredient_map[matched_id]
            if args.force:
                entry["nameLt"] = name_lt
                entry["barboraResolved"] = True
                entry["category"] = internal_category
                entry["defaultUnit"] = internal_unit
            else:
                # Only update barboraResolved and nameLt if not already set
                if not entry.get("barboraResolved"):
                    entry["nameLt"] = name_lt
                    entry["barboraResolved"] = True
            matched.append({"nameLt": name_lt, "ingredientId": matched_id})
        else:
            unmatched.append({
                "nameLt": name_lt,
                "barboraCategory": barbora_cat,
                "internalCategory": internal_category,
                "unit": internal_unit,
            })

    print(f"Matched: {len(matched)} products")
    print(f"Unmatched: {len(unmatched)} products")

    if unmatched:
        # Print only first 20 to avoid encoding issues on Windows terminals;
        # full list is saved to the normalized snapshot JSON.
        print("\nUnmatched products (first 20 — full list in normalized snapshot):")
        for p in unmatched[:20]:
            name_safe = p['nameLt'].encode(sys.stdout.encoding or 'utf-8', errors='replace').decode(sys.stdout.encoding or 'utf-8')
            print(f"  [{p['internalCategory']}] {name_safe} (unit: {p['unit']})")
        if len(unmatched) > 20:
            print(f"  ... and {len(unmatched) - 20} more")

    if not args.dry_run:
        from datetime import date
        ingredient_map_file["ingredients"] = ingredient_map
        ingredient_map_file["updatedAt"] = str(date.today())
        with open(map_path, "w", encoding="utf-8") as f:
            json.dump(ingredient_map_file, f, ensure_ascii=False, indent=2)
        print(f"\nOK ingredient-map.json updated ({len(matched)} entries resolved)")

        # Save normalized snapshot
        norm_dir = ROOT / "data" / "catalog" / "normalized"
        norm_dir.mkdir(parents=True, exist_ok=True)
        norm_path = norm_dir / raw_path.name
        normalized = {
            "sourceFile": raw_path.name,
            "matched": matched,
            "unmatched": unmatched,
        }
        with open(norm_path, "w", encoding="utf-8") as f:
            json.dump(normalized, f, ensure_ascii=False, indent=2)
        print(f"OK Normalized snapshot saved: {norm_path}")

    sys.exit(1 if unmatched else 0)


if __name__ == "__main__":
    main()
