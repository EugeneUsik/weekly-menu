Serialise a validated intermediate plan and shopping list to production menu JSON.

## Input contract

```json
{
  "weekId": "2026-W16",
  "candidate": { ... },      // intermediate plan object (schema §6) — must have passed score_plan
  "scoreReport": { ... },    // from score_plan.py — must have passed: true
  "shoppingList": [ ... ]    // output of aggregate_shopping.py — must be non-empty
}
```

Both `scoreReport.passed` must be `true` and `shoppingList` must be non-empty before this skill writes anything.

## Process

1. **Validate preconditions:**
   - `scoreReport.passed === true` → proceed
   - `scoreReport.passed === false` → STOP: return `{ "status": "ERROR", "reason": "Score report has hard rejects — fix before writing" }`
   - `shoppingList.length === 0` → STOP: return `{ "status": "ERROR", "reason": "Shopping list is empty — run aggregate_shopping first" }`

2. **Convert candidate to production schema:**
   - Merge breakfasts/lunches/dinners/snacks by day into `days[].meals` structure
   - Add `dayNameRu` for each date
   - Compute `scoreReport` summary fields (fishMeals, legumeMeals, redMeatMeals, snackDays, warnings from softPenalties)
   - Set `generatedAt` to current ISO datetime with timezone

3. **Write `data/menus/{weekId}.json`:**
   - 2-space indentation
   - UTF-8 encoding, `ensure_ascii: false`

4. **Run `python scripts/sync_index.py`** to update `data/index.json`.

5. **Run `python scripts/validate_data.py --week {weekId}`** to confirm the written file is valid.

6. **Return:**
   ```json
   {
     "status": "OK",
     "weekId": "2026-W16",
     "path": "data/menus/2026-W16.json",
     "scoreReport": { ... },
     "validationPassed": true
   }
   ```

## Strict constraints

- **Only write if both validation gates pass** (scoreReport + final validate_data).
- **Never overwrite an existing menu file without explicit user confirmation** if the file already exists and is published (`published: true` in index.json).
- Do not write partial files. If any step fails, leave the existing file unchanged.
