Safely append a validated recipe draft to data/recipes.json.

## Input contract

```json
{
  "recipe": { ... },           // validated recipe draft object (schema §2)
  "newIngredients": [ { ... } ] // new ingredient-map entries (may be empty array)
}
```

The recipe must have already passed the `nutrition-validator` check before this skill is invoked.

## Process

1. **Load `data/recipes.json`.**
2. **Check for ID collision:** if `recipe.id` already exists in the array → **STOP** and return:
   ```json
   { "status": "ERROR", "reason": "ID collision: recipe id 'trout-buckwheat-bowl' already exists" }
   ```
   Do not overwrite existing recipes.
3. **Validate the draft schema** (spot check):
   - All 12 flags present and boolean
   - All required fields present
   - `mealType` is one of the valid enum values
   - No forbidden allergen terms in any ingredient ID
4. **Append** the recipe object to the end of the array.
5. **Write** `data/recipes.json` with consistent 2-space indentation.
6. **If `newIngredients` is non-empty:**
   - Load `data/catalog/ingredient-map.json`
   - For each entry, check for ID collision (same rule: stop if exists)
   - Append new entries to `ingredients` object
   - Update `updatedAt` to today's date
   - Write `ingredient-map.json`
7. **Confirm:**
   ```json
   {
     "status": "OK",
     "appended": "trout-buckwheat-bowl",
     "totalRecipes": 23,
     "newIngredients": ["buckwheat", "dill"]
   }
   ```

## Strict constraints

- **Never modify existing recipe entries.** Only append.
- **Never overwrite an existing ingredient entry.** Only add new ones.
- **Never call this skill on an unvalidated draft.** The caller is responsible for running `nutrition-validator` first.
- This skill writes files directly — it is the only skill/command with this permission for recipe data.
