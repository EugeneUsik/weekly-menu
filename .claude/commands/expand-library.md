Expand the recipe library to cover an upcoming week, generating all needed recipes in one batch.

## Usage

```
/expand-library 2026-W19
```

The week ID tells the command which exclusion window to plan against. It does **not** generate the menu itself.

## Steps

1. **Run the sufficiency check** to get the current pool sizes and NEED_RECIPE signals:
   ```
   python scripts/check_library.py --week {weekId}
   ```
   Parse the output. Collect every line starting with `NEED_RECIPE:` plus every pool marked `⚠` (at or below target). Build a **generation plan** — a list of (mealType, constraint, count) tuples, targeting the `TARGETS` values defined in `check_library.py`, not just the minimums.

   Example generation plan:
   ```
   breakfast  : +3 recipes  (have 7, target 10)
   dinner omega3 : +2 recipes  (have 2, target 4)
   dinner legumes: +1 recipe   (have 4, target 5)
   snack      : +3 recipes  (have 2, target 5)
   ```
   Show this plan to the user before proceeding.

2. **Collect context for the generator:**
   - Load all existing recipe IDs from `data/recipes.json` (to pass as `existingIds`)
   - Load all existing ingredient IDs from `data/catalog/ingredient-map.json`
   - Load the forbidden allergy terms from the project (apples, prunes/plums, peaches, apricots — see recipe-generator agent for exact list)

3. **Generate all recipes in one agent call.**
   Invoke the `recipe-generator` agent with a batch prompt containing the full generation plan, the complete `existingIds` list, and the complete `existingIngredientIds` list. Request all recipes in a single JSON array response.

   The batch prompt must include:
   - Total count and breakdown by type/constraint
   - Full `existingIds` list (to prevent ID collisions)
   - Full `existingIngredientIds` list (so the agent knows what's already in the map)
   - The correct recipe schema (§2 of DATA_SCHEMA.md), including all 12 required flags
   - Per-type nutrition targets (from the schema doc)
   - The allergy forbidden list

4. **Parse the response.** Extract the JSON array of recipe drafts and any `NEW_INGREDIENT:` lines.

5. **Fix-up pass** — before validation, programmatically ensure every recipe has:
   - Nutrition fields: `kcalPerServing`, `proteinG`, `fatG`, `carbsG`, `fiberG` (correct names; rename if agent used alternatives like `calories`)
   - All 12 flags present and boolean: `weekdayFriendly`, `leftoversFriendly`, `childSafe`, `containsFish`, `containsOmega3Fish`, `containsLegumes`, `containsRedMeat`, `containsSoy`, `containsEggs`, `containsDairy`, `highProtein`, `highFiber`
   - `servings: 3`
   - `createdAt` set to today's date

6. **Write all new ingredients** to `data/catalog/ingredient-map.json` for any `NEW_INGREDIENT:` signals.

7. **Run validation:**
   ```
   python scripts/validate_data.py
   ```
   - If PASS → proceed to step 8.
   - If FAIL → show errors. Attempt an automated fix for mechanical errors (wrong field names, missing flags that can be inferred). Re-run validation. If still failing after one fix pass, show remaining errors and stop — do not loop endlessly.

8. **Append all validated recipes** to `data/recipes.json` using the `append-recipes` skill (one call per recipe, or write them all at once using the same logic).

9. **Re-run the sufficiency check** to confirm the library is now ready:
   ```
   python scripts/check_library.py --week {weekId}
   ```

10. **Show summary:**
    ```
    ✓ Library expanded for 2026-W19
    Added 9 recipes: 3 breakfast, 2 dinner-omega3, 1 dinner-legumes, 3 snack
    New ingredients added to ingredient-map.json: [list if any]

    Library is now sufficient for 2026-W19.
    Run /generate-menu 2026-W19 to proceed.
    ```

## Fix-up rules for step 5

Use these rules to infer missing flags when the generator omits them:

| Flag | Inference rule |
|---|---|
| `weekdayFriendly` | `activeMinutes <= 30` |
| `leftoversFriendly` | `mealType in [dinner, lunch]` and `totalMinutes >= 35` |
| `childSafe` | `true` unless a forbidden allergen is present in ingredient IDs or nameRu |
| `containsFish` | any ingredient ID contains `fish`, `fillet`, `tuna`, `sardine`, `mackerel`, `salmon`, `trout`, `herring` |
| `containsOmega3Fish` | ingredient matches: salmon, trout, mackerel, sardines, herring (NOT tuna, cod, pollock) |
| `containsLegumes` | ingredient matches: lentil, chickpea, bean, tofu, legume |
| `containsRedMeat` | ingredient matches: beef, pork, lamb, veal |
| `containsSoy` | ingredient matches: soy, tofu |
| `containsEggs` | ingredient ID is `eggs` |
| `containsDairy` | ingredient matches: milk, cheese, yogurt, butter, cream, cottage |
| `highProtein` | `proteinG >= 25` |
| `highFiber` | `fiberG >= 6` or `containsLegumes` |

## Constraints

- Never write to `data/recipes.json` directly without going through the fix-up and validation steps.
- Never skip the final sufficiency re-check.
- If the library is already sufficient (check_library exits 0), inform the user and stop — do not generate unnecessary recipes.
- Do not commit. That is the user's responsibility.
