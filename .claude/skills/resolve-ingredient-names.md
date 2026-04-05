Resolve a list of ingredient IDs to their full multilingual names using ingredient-map.json only.

## Input contract

```
ingredientIds:
  - salmon_fillet
  - green_lentils
  - buckwheat
  - unknown_ingredient
```

## Process

1. Load `data/catalog/ingredient-map.json`.
2. For each ID:
   - If found → extract `nameRu`, `nameLt`, `category`, `defaultUnit`, `barboraResolved`
   - If not found → add to `unresolved` list
3. For resolved entries where `barboraResolved: false` → add to `unverified` list with a note

## Output contract

```json
{
  "resolved": [
    {
      "ingredientId": "salmon_fillet",
      "nameRu": "Филе лосося",
      "nameLt": "Lašišos filė",
      "category": "fish",
      "defaultUnit": "g",
      "barboraResolved": true
    }
  ],
  "unverified": [
    {
      "ingredientId": "coconut_oil",
      "nameRu": "Кокосовое масло",
      "nameLt": "Kokosų aliejus [unverified]",
      "barboraResolved": false,
      "note": "nameLt not confirmed against Barbora catalog — run /normalize-catalog"
    }
  ],
  "unresolved": [
    {
      "ingredientId": "unknown_ingredient",
      "note": "Not found in ingredient-map.json — add via /add-recipe or catalog-mapper agent"
    }
  ]
}
```

## This skill does NOT

- Infer or guess Lithuanian names
- Create new ingredient-map entries (that is the `catalog-mapper` agent)
- Make any network requests to Barbora
