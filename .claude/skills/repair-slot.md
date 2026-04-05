Replace a single failed meal slot without touching any other day or meal type.

## Input contract

```
weekId: 2026-W16
day: 2026-04-15
mealType: dinner
failureReason: "dinner_in_2week_exclusion: recipe 'chicken-rice-pilaf' was used in 2026-W14"
```

## Process

1. Load `data/menus/{weekId}.json` and `data/recipes.json`.
2. Identify the current slot contents (recipeId, isLeftover, sourceDay).
3. Determine replacement constraints based on `failureReason`:
   - `allergy_violation` → find recipe for same mealType with same flags but no forbidden ingredients
   - `dinner_in_2week_exclusion` → find different recipe for same mealType
   - `consecutive_same_protein_dinner` → find recipe with different dominant protein category
   - `weekday_prep_over_limit` → find recipe with `activeMinutes ≤ 30` or `weekdayFriendly: true`
   - `recipe_repeated_in_week` → find any recipe for same mealType not already used this week
   - `missing_recipe_reference` → find any valid recipe for same mealType
4. Filter the recipe library to candidates satisfying the constraint.
5. Score the top 3 candidates using `scripts/score_plan.py` (with the single-slot patch applied).
6. Select the highest-scoring candidate that does not introduce new violations.
7. Patch **only** the affected slot in the menu JSON:
   ```json
   "dinner": {
     "recipeId": "new-recipe-id",
     "isLeftover": false,
     "sourceDay": null
   }
   ```
8. Run `python scripts/aggregate_shopping.py --week {weekId}` to rebuild the shopping list.
9. Run `python scripts/validate_data.py --week {weekId}` to confirm the repair is clean.

## Output contract

```json
{
  "weekId": "2026-W16",
  "day": "2026-04-15",
  "mealType": "dinner",
  "replaced": "chicken-rice-pilaf",
  "with": "buckwheat-mushroom-bowl",
  "reason": "2-week exclusion",
  "validationPassed": true
}
```

## Strict constraints

- **Touch ONLY the one specified slot.** Do not adjust adjacent days.
- If no valid replacement exists in the library, do NOT apply any patch. Return:
  ```json
  { "status": "NEED_RECIPE", "constraints": { "mealType": "dinner", "differentFrom": ["chicken-rice-pilaf"] } }
  ```
  The caller must then invoke `generate-recipe-from-constraints` and retry.
- If the repair introduces a new violation (e.g. drops omega-3 count below 2), report the new violation but still apply the repair — let the caller decide whether to fix it too.
