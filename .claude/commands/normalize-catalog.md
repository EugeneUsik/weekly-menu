Normalize a raw Barbora catalog snapshot and update ingredient mappings.

## Usage

```
/normalize-catalog
/normalize-catalog data/catalog/raw/2026-04-01.json
```

Optional argument: path to a specific raw snapshot file. If omitted, uses the most recent file in `data/catalog/raw/`.

## Steps

1. **Find the snapshot.** If no argument given, list files in `data/catalog/raw/` and use the most recently modified one. Show the filename to the user.

2. **Run the normalizer:**
   ```
   python scripts/normalize_catalog.py --input {snapshotPath}
   ```

3. **Display the results:**
   ```
   Matched: 47 products → ingredient-map.json updated
   Unmatched: 3 products
   
   Unmatched (require manual mapping):
     [fish]    Skumbrių filė (unit: g)
     [grains]  Avižų kruopos (unit: g)
     [pantry]  Kokosų aliejus (unit: ml)
   ```

4. **For each unmatched product**, ask if you should invoke the `catalog-mapper` agent to create a new ingredient-map entry. If yes, run the agent with the Lithuanian name, category, and unit as input. After each new entry is created, add it to `ingredient-map.json`.

5. **After mapping is complete**, re-run the normalizer with `--force` to confirm all new entries are resolved:
   ```
   python scripts/normalize_catalog.py --input {snapshotPath} --force
   ```

6. **Show final summary:**
   ```
   ✓ Catalog normalised: 50/50 products matched
   Files updated: data/catalog/ingredient-map.json
   Normalised snapshot saved: data/catalog/normalized/{filename}
   
   Next: run /validate-data to confirm no broken references, then /prepare-commit
   ```

## Important constraints

- **Never overwrite an existing `nameLt` or `category`** without the `--force` flag.
- Raw snapshot files (`data/catalog/raw/`) are excluded from git by `.gitignore`. Do not commit them.
- The normalised output (`data/catalog/normalized/`) is committed — it serves as the audit trail.
