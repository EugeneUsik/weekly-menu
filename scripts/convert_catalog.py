#!/usr/bin/env python3
"""
convert_catalog.py — Convert raw Barbora catalog (nested categories format)
to the flat format expected by normalize_catalog.py.

Usage:
  python scripts/convert_catalog.py \
      --input data/catalog/raw/catalog.json \
      --output data/catalog/raw/catalog_flat.json

Input format (actual Barbora export):
  {
    "categories": [
      {
        "name_lt": "Daržoves ir vaisiai",
        "products": [
          { "id": "...", "name_lt": "Bananai, 1 kg", "name_ru": null, ... }
        ]
      }
    ]
  }

Output format (expected by normalize_catalog.py):
  {
    "products": [
      { "name": "Bananai, 1 kg", "category": "Daržoves ir vaisiai", "unit": "kg" }
    ]
  }

Unit extraction:
  Parses unit from patterns like "1 kg", "200 g", "1 l", "500 ml", "1 vnt." in product names.
  Defaults to "pcs" if no unit found.
"""

import json
import re
import sys
import argparse
from pathlib import Path

ROOT = Path(__file__).parent.parent

# Regex to extract unit from product name strings like:
#   "Bananai, 1 kg", "Pienas 3.5%, 1 l", "Kiaušiniai, 10 vnt.", "Lašišos filė, 400 g"
UNIT_RE = re.compile(
    r'\b\d+(?:[.,]\d+)?\s*(kg|g|l|ml|vnt\.?|pak\.?|por\.?)\b',
    re.IGNORECASE
)

UNIT_NORMALIZE = {
    "kg":   "kg",
    "g":    "g",
    "l":    "l",
    "ml":   "ml",
    "vnt":  "vnt.",
    "vnt.": "vnt.",
    "pak":  "pcs",
    "pak.": "pcs",
    "por":  "pcs",
    "por.": "pcs",
}


def extract_unit(name: str) -> str:
    """Extract the unit from a product name string, default to 'vnt.'."""
    matches = UNIT_RE.findall(name)
    if matches:
        raw = matches[-1].lower().rstrip(".")
        return UNIT_NORMALIZE.get(raw + ".", UNIT_NORMALIZE.get(raw, "vnt."))
    return "vnt."


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


def main():
    parser = argparse.ArgumentParser(
        description="Flatten nested Barbora catalog to normalize_catalog.py input format."
    )
    parser.add_argument("--input",  default="data/catalog/raw/catalog.json",
                        help="Path to raw Barbora catalog JSON")
    parser.add_argument("--output", default="data/catalog/raw/catalog_flat.json",
                        help="Path to write flattened output")
    parser.add_argument("--unique", action="store_true",
                        help="Deduplicate products by name (keep first occurrence)")
    args = parser.parse_args()

    in_path = Path(args.input)
    if not in_path.is_absolute():
        in_path = ROOT / in_path

    out_path = Path(args.output)
    if not out_path.is_absolute():
        out_path = ROOT / out_path

    raw = load_json(in_path)
    categories = raw.get("categories", [])

    if not categories:
        print("FATAL: No 'categories' key found in input. Is this the right file?", file=sys.stderr)
        sys.exit(2)

    products = []
    seen_names = set()
    total_skipped = 0
    total_products = 0

    for cat in categories:
        cat_name = cat.get("name_lt", "").strip()
        for product in cat.get("products", []):
            name_lt = (product.get("name_lt") or "").strip()
            if not name_lt:
                continue

            total_products += 1

            if args.unique:
                key = name_lt.lower()
                if key in seen_names:
                    total_skipped += 1
                    continue
                seen_names.add(key)

            unit = extract_unit(name_lt)
            products.append({
                "name":     name_lt,
                "category": cat_name,
                "unit":     unit,
            })

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"products": products}, f, ensure_ascii=False, indent=2)

    print(f"Input:    {in_path.name}")
    print(f"Output:   {out_path}")
    print(f"Categories processed: {len(categories)}")
    print(f"Total product rows:   {total_products}")
    if args.unique:
        print(f"Duplicates skipped:   {total_skipped}")
    print(f"Products written:     {len(products)}")


if __name__ == "__main__":
    main()
