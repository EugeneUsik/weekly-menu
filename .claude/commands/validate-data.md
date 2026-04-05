Run all data validators and display a formatted report.

## Usage

```
/validate-data
/validate-data 2026-W16
```

Optional argument: a specific weekId to validate (otherwise validates all weeks in index.json).

## Steps

1. Run the validator:
   ```
   python scripts/validate_data.py --json [--week {weekId}]
   ```

2. Parse the JSON output and display as a human-readable report:

   **If passed:**
   ```
   ✓ All validators passed
   
   Warnings (3):
     [nutrition_validator] Week 2026-W16: red meat meals = 2 (at cap)
     [ingredient_map] salmon_fillet: barboraResolved = false
     [ingredient_map] green_lentils: barboraResolved = false
   
   Data is clean. Safe to commit.
   ```

   **If failed:**
   ```
   ✗ 2 error(s) found — must fix before committing
   
   Errors:
     [validate_recipes] Recipe 'trout-bowl' missing flag 'containsSoy'
       → Fix: add "containsSoy": false to the flags object
     [validate_menu_week] menus/2026-W16.json Day 3 lunch references unknown recipeId 'unknown-recipe'
       → Fix: replace with a valid recipeId from recipes.json, or run /swap-meal
   
   Warnings (1):
     [validate_weekly_rules] Week 2026-W16: snack days = 3 (minimum is 4)
   ```

3. For each error, suggest the minimal remediation action:
   - Schema errors → point to `docs/DATA_SCHEMA.md` for the correct format
   - Broken recipe references → suggest `/swap-meal`
   - Missing ingredient mapping → suggest `/normalize-catalog` or manually adding to `ingredient-map.json`
   - Allergy violation → **this is a hard stop — do not suggest overriding, flag for immediate manual review**
   - Weekly rule violations → suggest `/swap-meal` for the offending slot

## Important

- An allergy violation is never a warning — treat it as a critical error and emphasise it clearly.
- Do not attempt to auto-fix errors in this command. Report and guide; let the user or a targeted command apply fixes.
