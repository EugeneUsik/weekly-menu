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

3. **Library sufficiency check.** Run:
   ```
   python scripts/check_library.py --week {weekId}
   ```
   - If it exits 0: library is sufficient — proceed to step 4.
   - If it exits 1: library is insufficient. Invoke `/expand-library {weekId}` and wait for it to complete before proceeding to step 4.
   - Show the check output to the user regardless of result.

4. **Generate the menu.** Run:
   ```
   python scripts/generate_menu.py --week {weekId}
   ```

5. **Handle exit codes:**
   - **Exit 0:** Generation succeeded. Show the summary and proceed to step 6.
   - **Exit 1:** Hard rejects found. Parse the failure report. For each failed slot, invoke the `repair-slot` skill. Then re-run step 4.
   - **Exit 3:** Library still insufficient after expand-library (edge case). Show the NEED_RECIPE signals to the user and stop — do not loop indefinitely.
   - **Exit 2:** Fatal error (missing file). Show the error and stop.

6. **Post-generation validation.** Run:
   ```
   python scripts/validate_data.py --week {weekId}
   ```
   If it exits non-zero, stop and show errors.

7. **Show summary:**
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
