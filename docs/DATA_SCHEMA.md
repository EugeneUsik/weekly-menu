# Data Schema Reference

All JSON files in `/data/` must conform to the schemas defined in this document.
No file may be written to `/data/menus/` unless it passes validation against these schemas.

---

## Conventions

- **weekId**: ISO week string, e.g. `2026-W15`. Always the Monday-anchored ISO 8601 week. Used as filename stem and JSON key. Never use human-readable forms as keys.
- **Dates**: ISO 8601 date strings, e.g. `2026-04-06`.
- **Datetimes**: ISO 8601 with timezone offset, e.g. `2026-04-06T14:00:00+03:00`.
- **Language**: recipe content (names, steps, notes) is in Russian. Lithuanian names appear only in catalog mappings and the shopping list.
- **Units enum**: `g`, `ml`, `pcs`, `tbsp`, `tsp`, `cup`
- **mealType enum**: `breakfast`, `lunch`, `dinner`, `snack`
- **category enum**: `produce`, `dairy`, `meat`, `fish`, `grains`, `legumes`, `frozen`, `pantry`, `other`

---

## 1. `data/index.json`

Manifest of all available weeks. Rebuilt by `scripts/sync_index.py`.

```json
{
  "weeks": [
    {
      "weekId": "2026-W15",
      "labelRu": "6–12 апреля",
      "startDate": "2026-04-06",
      "endDate": "2026-04-12",
      "published": true
    }
  ],
  "defaultWeekId": "2026-W15"
}
```

### Field rules
- `weekId`: matches filename stem of corresponding menu file (`data/menus/{weekId}.json`)
- `labelRu`: display string only, not used as a key anywhere
- `startDate`: always Monday of that ISO week
- `endDate`: always Sunday of that ISO week
- `published`: set to `false` to hide a draft week from the UI without deleting the file
- `defaultWeekId`: must reference a `weekId` present in the `weeks` array and have `published: true`

---

## 2. `data/recipes.json`

Append-only recipe library. Array of recipe objects. IDs are stable and never reused.

```json
[
  {
    "id": "salmon-lentil-bowl",
    "nameRu": "Боул с лососем и чечевицей",
    "mealType": "dinner",
    "activeMinutes": 25,
    "totalMinutes": 35,
    "servings": 3,
    "ingredients": [
      { "ingredientId": "salmon_fillet", "amount": 600, "unit": "g" },
      { "ingredientId": "green_lentils", "amount": 200, "unit": "g" },
      { "ingredientId": "olive_oil", "amount": 2, "unit": "tbsp" }
    ],
    "stepsRu": [
      "Промойте чечевицу и отварите в подсоленной воде 20 минут.",
      "Нарежьте лосось на порционные куски, посолите и обжарьте на оливковом масле по 3–4 минуты с каждой стороны.",
      "Подавайте лосось на подушке из чечевицы."
    ],
    "storageNote": "Хранить в холодильнике до 2 дней. Разогревать отдельно.",
    "substitutionsNote": "Лосось можно заменить форелью.",
    "tags": ["fish", "legumes", "high-protein", "omega3"],
    "nutrition": {
      "kcalPerServing": 480,
      "proteinG": 42,
      "fatG": 18,
      "carbsG": 32,
      "fiberG": 8
    },
    "flags": {
      "weekdayFriendly": true,
      "leftoversFriendly": false,
      "childSafe": true,
      "containsFish": true,
      "containsOmega3Fish": true,
      "containsLegumes": true,
      "containsRedMeat": false,
      "containsSoy": false,
      "containsEggs": false,
      "containsDairy": false,
      "highProtein": true,
      "highFiber": true
    },
    "createdAt": "2026-04-04",
    "version": 1
  }
]
```

### Field rules
- `id`: kebab-case slug, globally unique, never reused after deletion
- `nameRu`: display name in Russian, used in UI
- `mealType`: one of the mealType enum values
- `activeMinutes`: hands-on cooking time (for weekday constraint check: must be ≤30 for weekdayFriendly recipes)
- `servings`: base count; always `3` for family recipes (husband + wife + child)
- `ingredientId`: must exist as a key in `data/catalog/ingredient-map.json`
- `unit`: one of the units enum values
- `stepsRu`: ordered array of Russian cooking step strings
- `flags.childSafe`: must be `false` if any ingredient contains a forbidden allergen
- `flags.containsOmega3Fish`: `true` only for salmon, trout, mackerel, sardines, herring
- `flags.containsRedMeat`: `true` for beef, pork, lamb, veal
- `version`: increment if a recipe is structurally corrected (ingredient amounts, steps); never change `id`

### Allergy enforcement
The following ingredients are **forbidden** for the child (allergies): apples, prunes/plums, peaches, apricots.

Matching uses **word boundaries** to avoid false positives — `pineapple` is safe, `apple` is not.

Forbidden patterns (checked against `ingredientId`, `nameRu`, `nameEn`, and `aliases`):

```
apple, apples, яблоко, яблоки, яблочный (and all яблочн- forms)
prune, prunes, plum, plums, чернослив, слива, сливы
apricot, apricots, абрикос (and all абрикос- forms)
peach, peaches, персик (and all персик- forms)
```

**Safe**: pineapple/ананас, nectarine/нектарин, cherry tomatoes/помидоры черри (use "помидоры" in Russian), grapes/виноград.

---

## 3. `data/menus/{weekId}.json`

One file per week. Fully resolved weekly plan including shopping list.

```json
{
  "weekId": "2026-W15",
  "generatedAt": "2026-04-04T14:00:00+03:00",
  "days": [
    {
      "date": "2026-04-06",
      "dayNameRu": "Понедельник",
      "meals": {
        "breakfast": {
          "recipeId": "oat-protein-bowl",
          "isLeftover": false,
          "sourceDay": null
        },
        "lunch": {
          "recipeId": "salmon-lentil-bowl",
          "isLeftover": true,
          "sourceDay": "2026-04-05"
        },
        "dinner": {
          "recipeId": "chicken-rice-pilaf",
          "isLeftover": false,
          "sourceDay": null
        },
        "snack": {
          "recipeId": "yogurt-walnut-bowl",
          "isLeftover": false,
          "sourceDay": null
        }
      }
    }
  ],
  "shoppingList": [
    {
      "ingredientId": "salmon_fillet",
      "nameRu": "Филе лосося",
      "nameLt": "Lašišos filė",
      "category": "fish",
      "amount": 600,
      "unit": "g",
      "neededByDate": "2026-04-06",
      "checkboxKey": "2026-W15:fish|Филе лосося|g"
    }
  ],
  "scoreReport": {
    "fishMeals": 3,
    "legumeMeals": 3,
    "redMeatMeals": 1,
    "snackDays": 5,
    "warnings": []
  }
}
```

### Field rules
- `days`: exactly 7 entries, one per day, Monday through Sunday in order
- `date`: ISO date of that day
- `dayNameRu`: Russian day name (Понедельник, Вторник, Среда, Четверг, Пятница, Суббота, Воскресенье)
- `meals.snack`: may be `null` if no snack planned for that day
- `meals.*.recipeId`: must reference a valid `id` in `recipes.json`
- `meals.*.isLeftover`: `true` when this meal is reused from a prior day's dinner
- `meals.*.sourceDay`: ISO date of the original dinner day when `isLeftover: true`; `null` otherwise
- `shoppingList`: deduplicated; each `checkboxKey` appears exactly once
- `checkboxKey` pattern: `{weekId}:{category}|{nameRu}|{unit}`
- `scoreReport.fishMeals`: count of meals where referenced recipe has `containsFish: true`
- `scoreReport.legumeMeals`: count of meals where referenced recipe has `containsLegumes: true`

### Weekly rule minimums (hard requirements)
| Rule | Minimum |
|------|---------|
| Fish meals | ≥ 2 (must include ≥ 2 omega-3 fish) |
| Legume meals | ≥ 3 |
| Snack days | ≥ 4 of 7 |
| Red meat meals | ≤ 2 |

### Variety rules (enforced at generation time)
| Rule | Type |
|------|------|
| No recipe ID repeated within the same week | Hard reject |
| No same dinner protein category on consecutive days | Hard reject |
| No same breakfast on consecutive days | Hard reject |
| Any dinner recipe used in previous 2 weeks | Hard reject (excluded from pool) |
| Any breakfast recipe used in previous 2 weeks | Hard reject (excluded from pool) |
| Dinner repeated in weeks 3–4 lookback | Soft penalty −20 |
| Breakfast repeated in weeks 3–4 lookback | Soft penalty −10 |

---

## 4. `data/catalog/ingredient-map.json`

Canonical ingredient registry. Maps internal ingredient IDs to multilingual names and Barbora metadata.

```json
{
  "version": 1,
  "updatedAt": "2026-04-04",
  "ingredients": {
    "salmon_fillet": {
      "id": "salmon_fillet",
      "nameEn": "salmon fillet",
      "nameRu": "Филе лосося",
      "nameLt": "Lašišos filė",
      "category": "fish",
      "defaultUnit": "g",
      "aliases": ["лосось", "семга", "salmon"],
      "barboraResolved": true
    },
    "green_lentils": {
      "id": "green_lentils",
      "nameEn": "green lentils",
      "nameRu": "Зелёная чечевица",
      "nameLt": "Žaliosios lęšiai",
      "category": "legumes",
      "defaultUnit": "g",
      "aliases": ["чечевица зелёная", "lentils"],
      "barboraResolved": true
    }
  }
}
```

### Field rules
- Top-level key equals `ingredient.id`
- `id`: snake_case, stable, never reused
- `nameLt`: Lithuanian name as it appears in Barbora catalog
- `aliases`: used by allergy scanner and catalog normalizer for fuzzy matching
- `barboraResolved`: `false` until a Barbora product has been confirmed for this ingredient
- Every `ingredientId` referenced in `recipes.json` must have an entry here

---

## 5. `data/catalog/substitution-map.json`

Approved ingredient substitutions for when a product is unavailable in Barbora.

```json
{
  "version": 1,
  "updatedAt": "2026-04-04",
  "substitutions": {
    "salmon_fillet": {
      "substituteId": "trout_fillet",
      "ratio": 1.0,
      "noteRu": "Форель — равноценная замена лосося по питательности и вкусу.",
      "approved": true
    }
  }
}
```

### Field rules
- Top-level key is the `ingredientId` being substituted
- `substituteId`: must exist in `ingredient-map.json`
- `ratio`: amount multiplier (1.0 = same amount, 0.8 = use 80% of original amount)
- `approved`: only `true` substitutions are used by the generation pipeline automatically

---

## 6. Intermediate Schemas (used during generation, not persisted)

### Weekly Plan Candidate (`scripts/generate_menu.py` output before validation)

```json
{
  "weekId": "2026-W15",
  "breakfasts": [
    { "day": "2026-04-06", "recipeId": "oat-protein-bowl" }
  ],
  "lunches": [
    { "day": "2026-04-06", "recipeId": "salmon-lentil-bowl", "isLeftover": true, "sourceDay": "2026-04-05" }
  ],
  "dinners": [
    { "day": "2026-04-06", "recipeId": "chicken-rice-pilaf", "isLeftover": false }
  ],
  "snacks": [
    { "day": "2026-04-06", "recipeId": "yogurt-walnut-bowl" }
  ]
}
```

### Recipe Draft (`recipe-generator` agent output before appending)

```json
{
  "id": "salmon-lentil-bowl",
  "nameRu": "Боул с лососем и чечевицей",
  "mealType": "dinner",
  "activeMinutes": 25,
  "totalMinutes": 35,
  "servings": 3,
  "ingredients": [
    { "ingredientId": "salmon_fillet", "amount": 600, "unit": "g" }
  ],
  "stepsRu": ["..."],
  "storageNote": "...",
  "substitutionsNote": "...",
  "tags": ["fish", "high-protein"],
  "nutrition": {
    "kcalPerServing": 480,
    "proteinG": 42,
    "fatG": 18,
    "carbsG": 32,
    "fiberG": 8
  },
  "flags": { "weekdayFriendly": true, "leftoversFriendly": false, "childSafe": true, "containsFish": true, "containsOmega3Fish": true, "containsLegumes": false, "containsRedMeat": false, "containsSoy": false, "containsEggs": false, "containsDairy": false, "highProtein": true, "highFiber": false },
  "createdAt": "2026-04-04",
  "version": 1
}
```

Draft objects must pass schema validation and allergy check before being appended to `recipes.json`.

---

## 7. Protein Category Classification

Used by the variety engine to prevent consecutive same-protein dinners.

| Category label | Ingredients |
|---|---|
| `fish` | all fish (salmon, trout, cod, mackerel, herring, tuna, etc.) |
| `chicken` | chicken breast, chicken thigh, chicken drumstick |
| `beef` | beef, minced beef, veal |
| `pork` | pork, ham (non-processed only) |
| `lamb` | lamb |
| `legume` | lentils, chickpeas, beans, tofu (when protein source) |
| `egg` | egg-dominant dishes |
| `dairy` | cottage cheese, yogurt (when protein source in a dish) |
| `other` | mixed or unclassifiable |

The protein category is derived from the dominant protein `ingredientId` in a recipe, resolved via `ingredient-map.json` category field.
