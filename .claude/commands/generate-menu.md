Generate a weekly menu for the given week ID.

## Usage

```
/generate-menu 2026-W16
```

## Steps

1. **Validate argument.** The week ID must match the pattern `YYYY-Wnn`. If missing or malformed, stop and show the correct format.

2. **Pre-flight validation.** Run:
   ```
   python scripts/validate_data.py
   ```
   If it exits non-zero, stop and show the errors. Do not proceed with a broken data state.

3. **Generate the menu.** Run:
   ```
   python scripts/generate_menu.py --week {weekId}
   ```

4. **Handle exit codes:**
   - **Exit 0:** Generation succeeded. Show the summary and proceed to step 6.
   - **Exit 1:** Hard rejects found. Parse the failure report. For each failed slot, invoke the `repair-slot` skill. Then re-run step 3.
   - **Exit 3:** Library insufficient. For each `NEED_RECIPE:` line in the output, invoke the `recipe-generator` agent with the stated constraints. After all recipes are generated and validated, invoke the `append-recipes` skill for each, then re-run step 3.
   - **Exit 2:** Fatal error (missing file). Show the error and stop.

5. **Post-generation validation.** Run:
   ```
   python scripts/validate_data.py --week {weekId}
   ```
   If it exits non-zero, stop and show errors.

6. **Show summary:**
   ```
   ✓ Menu generated for 2026-W16
   Fish meals: 3 | Legume meals: 3 | Red meat: 0 | Snack days: 5
   Score: 92/100
   Warnings: [list any soft penalties]
   
   Files written:
     data/menus/2026-W16.json
     data/index.json (updated)
   
   Next: review the menu, then run /prepare-commit
   ```

## Important constraints

- **Never write menu files directly.** Always go through `scripts/generate_menu.py`.
- **Never skip the post-generation validation step.**
- Do not commit. That is the user's responsibility after reviewing the output.
