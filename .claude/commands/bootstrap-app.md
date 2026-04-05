Create the complete project scaffold for the Weekly Menu App from scratch.

## Steps

1. Verify the current directory is the project root (contains `docs/SPEC.md`).

2. Create the full folder tree if any directories are missing:
   ```
   data/menus/
   data/catalog/raw/
   data/catalog/normalized/
   scripts/
   docs/
   .claude/agents/
   .claude/commands/
   .claude/skills/
   ```

3. Verify all required files exist. For each missing file, create it with the correct stub content:
   - `data/index.json` — `{"weeks": [], "defaultWeekId": null}`
   - `data/recipes.json` — `[]`
   - `data/catalog/ingredient-map.json` — `{"version": 1, "updatedAt": "YYYY-MM-DD", "ingredients": {}}`
   - `data/catalog/substitution-map.json` — `{"version": 1, "updatedAt": "YYYY-MM-DD", "substitutions": {}}`
   - `.gitignore` — standard Python + macOS ignores, exclude `data/catalog/raw/`

4. Run `git init` if `.git` does not exist.

5. Run `python scripts/validate_data.py` and report results. If it fails on missing files, that is expected at this stage.

6. Print a checklist of manual tasks remaining:
   ```
   ✓ Folder structure created
   ✓ Stub data files created
   □ Generate seed recipes: /add-recipe (repeat 19 times)
   □ Generate first week: /generate-menu 2026-W{n}
   □ Validate: /validate-data
   □ Set up GitHub Pages in repo settings (branch: main, root: /)
   ```
