Select recipes to form a full candidate weekly plan, ready for scoring.

## Input contract

```
targetWeekId: 2026-W16
recipeLibraryPath: data/recipes.json
recentMenuPaths:
  - data/menus/2026-W15.json
  - data/menus/2026-W14.json
  - data/menus/2026-W13.json
  - data/menus/2026-W12.json
```

## Process

1. Load `data/recipes.json` and the provided recent menu files (up to 4).
2. Build the exclusion sets:
   - `hard_exclude`: all recipeIds from the most recent 2 menu files
   - `soft_penalize`: all recipeIds from menu files 3–4
3. Invoke the `menu-planner` agent with the recipe library and exclusion sets.
4. The agent produces a **candidate plan object** (intermediate schema §6).
5. Write the candidate to a temp file: `/tmp/candidate-{weekId}.json`
6. Run scoring: `python scripts/score_plan.py --plan /tmp/candidate-{weekId}.json`
7. Return the candidate plan object and score report together.

## Output contract

```json
{
  "candidate": { ... },    // intermediate plan schema §6
  "scoreReport": {
    "hardRejects": [],
    "softPenalties": {},
    "totalScore": 94,
    "passed": true
  }
}
```

If `passed: false`, do not proceed — return the output to the caller for repair or library expansion.

## This skill does NOT

- Write to `data/menus/`
- Resolve Lithuanian product names
- Generate new recipes (that is the `generate-recipe-from-constraints` skill)
