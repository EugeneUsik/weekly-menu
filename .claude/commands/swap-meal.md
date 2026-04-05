Replace a single meal slot in an existing weekly menu.

## Usage

```
/swap-meal 2026-W16 2026-04-15 dinner
```

Arguments: `<weekId> <date (YYYY-MM-DD)> <mealType (breakfast|lunch|dinner|snack)>`

## Steps

1. **Validate arguments.** weekId must match `YYYY-Wnn`, date must be a valid ISO date within that week, mealType must be one of `breakfast|lunch|dinner|snack`.

2. **Load current slot.** Read `data/menus/{weekId}.json`, find the day matching `date`, show the current recipe in that slot:
   ```
   Current dinner on 2026-04-15: Куриный плов (chicken-rice-pilaf)
   ```

3. **Find alternatives.** Load `data/recipes.json`, filter by:
   - `mealType` matches
   - `childSafe: true`
   - Not already used elsewhere in the week
   - Not in the 2-week hard-exclude window (check `data/menus/` files for last 2 weeks)
   - If replacing a weekday dinner: `activeMinutes ≤ 30` or `weekdayFriendly: true`
   - If the slot required specific flags (e.g. the original was an omega-3 dinner needed for the weekly minimum), ensure the replacement has the same flag

4. **Present top 3 options** with name, prep time, and key flags. Wait for user selection.

5. **Apply the swap.** Patch only the affected meal slot in the JSON — do not touch any other day or slot.

6. **Rebuild shopping list.** Run:
   ```
   python scripts/aggregate_shopping.py --week {weekId}
   ```

7. **Validate.** Run:
   ```
   python scripts/validate_data.py --week {weekId}
   ```
   If validation fails, report errors. The user may need to pick a different alternative.

8. **Confirm result:**
   ```
   ✓ Swapped: 2026-04-15 dinner → Боул с форелью (trout-buckwheat-bowl)
   Shopping list rebuilt. Run /prepare-commit when ready.
   ```

## Constraints

- **Touch only the targeted slot.** If the swap creates a weekly rule violation elsewhere (e.g. drops omega-3 count below 2), warn the user and suggest a fix — but do not auto-repair other slots.
- If the replacement is a leftover lunch, update `isLeftover` and `sourceDay` correctly.
