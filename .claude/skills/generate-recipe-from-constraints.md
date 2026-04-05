Generate a single recipe from structured constraints and return a validated draft object.

## Input contract

```
mealType: dinner
ingredientConstraints:
  containsOmega3Fish: true
prepTimeLimit: 25
nutritionBand: high-protein
prohibitedIngredients:
  - cherry
  - вишня
  - черешня
  - apple
  - яблоко
  - яблочный
  - pear
  - груша
  - грушевый
  - apricot
  - абрикос
  - peach
  - персик
existingIds:
  - salmon-lentil-bowl
  - trout-buckwheat-bowl
weekdayFriendly: true
childSafe: true
```

## Process

1. Invoke the `recipe-generator` agent with the full input above.
2. The agent returns a recipe draft object with all fields populated in Russian.
3. Invoke the `nutrition-validator` agent to check the draft.
4. If validation passes → proceed to step 5.
5. If validation fails:
   - Show the validation report.
   - If errors are fixable (e.g. wrong flag value), re-invoke `recipe-generator` with a correction note.
   - Retry up to 2 times. If still failing after 2 retries, return the failure to the caller.
6. Check for `NEW_INGREDIENT:` signals in the draft. For each:
   - Invoke the `catalog-mapper` agent to create a new ingredient-map entry.
   - Collect the new entry (do not write to file yet — that happens in `append-recipes`).

## Output contract

```json
{
  "recipe": { ... },           // fully validated recipe draft object (schema §2)
  "newIngredients": [ { ... } ], // new ingredient-map entries needed (may be empty)
  "validationReport": { ... }    // nutrition-validator output
}
```

## This skill does NOT

- Append to `data/recipes.json` (that is the `append-recipes` skill)
- Write to `data/catalog/ingredient-map.json` directly
- Generate more than one recipe per invocation
