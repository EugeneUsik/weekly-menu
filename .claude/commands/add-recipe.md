Add a single new recipe to the library through the validated pipeline.

## Usage

```
/add-recipe
```

No arguments. This command collects constraints interactively before invoking the generator.

## Steps

1. **Collect constraints** by asking the user:
   - `mealType`: breakfast / lunch / dinner / snack
   - `containsOmega3Fish`: needed? (yes/no/don't care)
   - `containsLegumes`: needed? (yes/no/don't care)
   - `weekdayFriendly`: must fit in 30 min active? (yes/no)
   - Key ingredient or cuisine direction (optional free text, e.g. "salmon", "chickpea", "Georgian")
   - Any ingredients to avoid beyond the standard allergy list

2. **Show existing IDs** for this meal type (to help the generator avoid duplicates):
   ```
   Existing dinner recipes: salmon-lentil-bowl, chicken-rice-pilaf, [...]
   ```

3. **Invoke the `recipe-generator` agent** with the collected constraints. Pass the full `existingIds` list for the meal type.

4. **Display the draft** in full. Ask the user: "Does this recipe look correct? (yes / regenerate / cancel)"
   - "regenerate" → re-invoke the generator with a note about what to change
   - "cancel" → stop

5. **Invoke the `nutrition-validator` agent** to check the draft. Display the validation report.
   - If the report has errors → show them, ask the user if the generator should attempt a fix, then re-invoke if yes
   - If PASS → proceed

6. **Check for `NEW_INGREDIENT:` signals** at the bottom of the recipe draft. For each new ingredient:
   - Invoke the `catalog-mapper` agent to create the ingredient-map entry
   - Add the entry to `data/catalog/ingredient-map.json`

7. **Invoke the `append-recipes` skill** to write the validated recipe to `data/recipes.json`.

8. **Confirm:**
   ```
   ✓ Recipe 'trout-buckwheat-bowl' added to data/recipes.json
   New ingredients added to ingredient-map.json: [list if any]
   
   Run /validate-data to confirm, then /prepare-commit when ready.
   ```

## Constraints

- Never write to `data/recipes.json` directly — always go through the `append-recipes` skill.
- Never approve a recipe that failed the `nutrition-validator` check.
- Never skip the allergy check, even if the user says the recipe is fine.
