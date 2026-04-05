# Operations Guide

How to run the Weekly Menu App content pipeline using Claude Code commands.

---

## Weekly Workflow

The standard flow each week:

```
1. (optional) Refresh Barbora catalog snapshot  →  /normalize-catalog
2. Generate the new week                        →  /generate-menu 2026-W16
3. Inspect the summary output and score
4. (optional) Swap individual meals             →  /swap-meal 2026-W16 2026-04-13 dinner
5. Validate all data                            →  /validate-data
6. Prepare commit message                       →  /prepare-commit
7. git add <files listed by prepare-commit>
8. git commit -m "<message from prepare-commit>"
9. git push origin main
```

GitHub Pages serves the app automatically from the `main` branch root.

---

## Commands Reference

### `/bootstrap-app`

Creates the full project scaffold from scratch. Run once on a fresh clone.

- Creates all directories under `data/`, `scripts/`, `docs/`, `.claude/`
- Creates empty stub data files (`recipes.json`, `index.json`, etc.)
- Runs `git init` if not already a repo
- Prints a checklist of remaining manual steps

---

### `/generate-menu <weekId>`

Generates a complete weekly menu from the recipe library.

```
/generate-menu 2026-W16
```

**What it does:**
1. Validates existing data (pre-flight)
2. Runs `scripts/generate_menu.py --week {weekId}`
3. If exit 3 (NEED_RECIPE): invokes `recipe-generator` agent per signal, appends recipes, retries
4. If exit 1 (hard rejects): invokes `repair-slot` skill per failed slot, retries
5. Runs post-generation validation
6. Shows summary: fish/legume/redmeat counts, score, files written

**Exit conditions that require action:**
- `NEED_RECIPE: dinner, containsOmega3Fish=true` → run `/add-recipe` specifying omega-3 fish dinner
- Hard reject `consecutive_same_protein_dinner` → the scorer will attempt repair automatically; if it cannot, run `/swap-meal`

---

### `/swap-meal <weekId> <date> <mealType>`

Replaces one meal slot without touching the rest of the week.

```
/swap-meal 2026-W16 2026-04-15 dinner
```

**What it does:**
1. Shows current recipe in that slot
2. Finds up to 3 alternatives satisfying all constraints
3. Presents options and waits for selection
4. Patches only the targeted slot
5. Rebuilds shopping list
6. Validates the week

**Notes:**
- If the swapped slot was providing a required nutrition metric (e.g. one of the 2 omega-3 meals), the replacement must carry the same flag.
- Leftover lunches automatically update `isLeftover` and `sourceDay` if dinner is swapped.

---

### `/validate-data [weekId]`

Runs all validators and displays a formatted report.

```
/validate-data
/validate-data 2026-W16
```

With no argument, validates all weeks in `index.json`. With a weekId, validates only that week.

**Report levels:**
- `CRITICAL` — allergy violation (must fix immediately, do not commit)
- `ERROR` — schema, referential integrity, or weekly rule violation (must fix before commit)
- `WARNING` — soft rule, unverified ingredient mapping (should fix, but not blocking)

---

### `/normalize-catalog [snapshotPath]`

Normalizes a raw Barbora product snapshot and updates `ingredient-map.json`.

```
/normalize-catalog
/normalize-catalog data/catalog/raw/2026-04-01.json
```

Raw snapshot files go in `data/catalog/raw/` (excluded from git). Normalized outputs go in `data/catalog/normalized/` (committed for audit).

**Workflow:**
1. Place Barbora export JSON in `data/catalog/raw/`
2. Run `/normalize-catalog`
3. Review unmatched products in output
4. For each unmatched: approve an automatic entry via `catalog-mapper` agent or add manually
5. Commit `ingredient-map.json` and the normalized snapshot

---

### `/add-recipe`

Adds a single new recipe to the library through the full validated pipeline.

```
/add-recipe
```

Collects constraints interactively (mealType, omega-3, legumes, prep time, key ingredient), invokes `recipe-generator`, runs `nutrition-validator`, then appends via `append-recipes` skill.

**When to use:**
- Before generating a week when the library needs more variety
- When `/generate-menu` emits a `NEED_RECIPE` signal
- To expand a specific meal type that is getting stale due to the 2-week exclusion window

---

### `/rebuild-shopping <weekId>`

Recomputes and overwrites the shopping list in an existing menu file.

```
/rebuild-shopping 2026-W16
```

Runs `scripts/aggregate_shopping.py`, validates the output, then patches the `shoppingList` field in the menu JSON. Useful after ingredient amount corrections or after adding new ingredient-map entries.

**Note:** Changing an ingredient's `nameRu`, `category`, or `unit` will change its `checkboxKey`, which resets any browser checkbox state for that item.

---

### `/prepare-commit`

Summarises all changed files and drafts a conventional commit message.

```
/prepare-commit
```

**What it does:**
1. Runs `git status` and `git diff --stat`
2. Groups files by concern (menu data / recipes / catalog / frontend / scripts / docs / automation)
3. Runs `validate_data.py` — stops if validation fails
4. Drafts and displays the commit message and `git add` command
5. Does NOT commit — you confirm and run the commands manually

---

## Repair Procedures

Decision tree for when `/validate-data` returns errors:

### Allergy violation
**CRITICAL. Never override.**
1. Identify the offending recipe and ingredient.
2. If the recipe has `childSafe: true` but contains a forbidden ingredient → set `childSafe: false` AND remove from any week that uses it.
3. If the ingredient itself is mislabelled in `ingredient-map.json` → correct the entry; do not remove the ingredient.
4. Run `/validate-data` again to confirm clean.

### Missing recipe reference
`menus/2026-W16.json Day 3 dinner references unknown recipeId 'deleted-recipe'`
→ Run `/swap-meal 2026-W16 2026-04-15 dinner` to replace with a valid recipe.

### Missing ingredient mapping
`Recipe 'buckwheat-bowl' references unknown ingredientId 'buckwheat'`
→ Add `buckwheat` to `ingredient-map.json` via the `catalog-mapper` agent, then run `/rebuild-shopping` for any affected weeks.

### Weekly rule violation (insufficient fish/legumes)
`Week 2026-W16: omega-3 fish meals = 1 (minimum 2)`
→ Run `/swap-meal` to replace a non-fish dinner with an omega-3 fish dinner. If no omega-3 fish recipe is available, run `/add-recipe` first.

### Duplicate checkboxKey in shopping list
→ Run `/rebuild-shopping {weekId}` to recompute from scratch.

### Shopping list unit mismatch warning
→ Check `ingredient-map.json` for the affected ingredient. Ensure `defaultUnit` matches the unit used in recipes. Run `/rebuild-shopping {weekId}`.

---

## Barbora Catalog Refresh

When Barbora product availability changes (typically monthly):

1. Export current product list from Barbora website as JSON.
2. Save to `data/catalog/raw/YYYY-MM-DD.json`.
3. Run `/normalize-catalog`.
4. For each unmatched product that corresponds to an ingredient in the library, use the `catalog-mapper` agent to add a mapping.
5. For ingredients now unavailable in Barbora, add entries to `substitution-map.json` via `catalog-mapper`.
6. Run `/validate-data` to confirm no broken references.
7. Run `/prepare-commit` and commit the changes.

**File locations:**
- Raw snapshots: `data/catalog/raw/` — **not committed** (gitignored)
- Normalized outputs: `data/catalog/normalized/` — **committed** as audit trail
- Updated registry: `data/catalog/ingredient-map.json` — **committed**

---

## Adding a New Recipe

Use `/add-recipe` when:
- The planner emits a `NEED_RECIPE` signal during generation
- A meal type is getting repetitive (2-week exclusion window is blocking most candidates)
- You want to add a seasonal or requested dish

**Do not edit `data/recipes.json` directly** — always go through `/add-recipe` to ensure:
- Schema validation
- Allergy check
- ID uniqueness
- Correct flag values

**Minimum recipe distribution to maintain the generation pipeline:**

| Meal type | Minimum in library |
|-----------|-------------------|
| Breakfasts | 5 (at least 3 beyond the 2-week exclusion window) |
| Omega-3 fish dinners | 4 |
| Legume dinners | 5 |
| Other dinners | 4 |
| Non-leftover lunches | 4 |
| Snacks | 4 |

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `generate_menu.py` exits with code 3 | Recipe library too small after 2-week exclusion | Run `/add-recipe` for the needed meal type |
| Shopping list has items missing `nameLt` | `barboraResolved: false` in ingredient-map | Run `/normalize-catalog` or add `nameLt` manually |
| Frontend shows blank menu screen | `data/index.json` out of sync or malformed | Run `python scripts/sync_index.py` then `/validate-data` |
| Validation fails after `/swap-meal` | Shopping list not rebuilt | Run `/rebuild-shopping {weekId}` |
| Score < 70 for generated week | Too many soft penalties (repetition, low variety) | Expand the recipe library with `/add-recipe` before next generation |
| `checkboxKey` mismatch error | `nameRu` or `category` changed for an ingredient | Run `/rebuild-shopping {weekId}` — browser state for that item resets |
| Week shows as blank on phone | `published: false` in `index.json` | Edit `index.json` to set `published: true` for that week |
