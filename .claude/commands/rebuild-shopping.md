Recompute and overwrite the shopping list for a given week.

## Usage

```
/rebuild-shopping 2026-W16
```

Required argument: weekId in `YYYY-Wnn` format.

## When to use

- After `/swap-meal` (the swap command calls this automatically, but you can run it manually too)
- After editing a recipe's ingredient amounts in `recipes.json`
- After adding a new ingredient mapping in `ingredient-map.json`
- When a shopping list looks incorrect or out of date

## Steps

1. **Validate argument.** weekId must match `YYYY-Wnn` and `data/menus/{weekId}.json` must exist.

2. **Run the aggregator:**
   ```
   python scripts/aggregate_shopping.py --week {weekId}
   ```

3. **Display the result:**
   - If successful:
     ```
     ✓ Shopping list rebuilt for 2026-W16: 18 items
     
     Categories: produce (4), dairy (2), fish (2), meat (1), legumes (2), grains (3), pantry (4)
     ```
   - If there are unresolved ingredients (exit 1):
     ```
     ✗ 2 ingredient(s) not in ingredient-map.json:
       - buckwheat
       - coconut_oil
     
     Add these to data/catalog/ingredient-map.json, then re-run /rebuild-shopping {weekId}.
     Or run /normalize-catalog to attempt automatic resolution from the Barbora snapshot.
     ```

4. **Run validation:**
   ```
   python scripts/validate_data.py --week {weekId}
   ```
   Report any errors.

5. If all clean:
   ```
   ✓ Shopping list valid. Run /prepare-commit when ready.
   ```

## Constraints

- This command patches only the `shoppingList` field in the menu JSON. It does not change meal assignments.
- All checkbox states stored in the browser (localStorage) use stable `checkboxKey` values. Rebuilding the shopping list will reset any checked items for this week if `nameRu`, `category`, or `unit` change for an ingredient.
