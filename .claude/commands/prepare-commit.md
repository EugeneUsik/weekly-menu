Summarise all staged changes and prepare a conventional commit message for review.

## Usage

```
/prepare-commit
```

No arguments.

## Steps

1. **Check working tree status:**
   ```
   git status
   git diff --stat HEAD
   ```

2. **Group changed files by concern:**

   | Concern | Files |
   |---------|-------|
   | New/updated menu | `data/menus/*.json`, `data/index.json` |
   | Recipe library changes | `data/recipes.json` |
   | Catalog changes | `data/catalog/ingredient-map.json`, `data/catalog/substitution-map.json`, `data/catalog/normalized/` |
   | Frontend changes | `index.html`, `styles.css`, `app.js` |
   | Scripts | `scripts/*.py` |
   | Docs | `docs/*.md` |
   | Automation | `.claude/agents/*.md`, `.claude/commands/*.md`, `.claude/skills/*.md` |

3. **Run validation** on all changed data files:
   ```
   python scripts/validate_data.py
   ```
   If validation fails, stop and show errors. Do not prepare a commit for invalid data.

4. **Draft a conventional commit message** based on the grouped changes:

   Examples:
   - `feat: add menu for 2026-W16 (13–19 апреля)` — new menu file
   - `feat: add 5 dinner recipes to library` — new recipes
   - `fix: correct shopping list amounts for 2026-W15` — shopping fix
   - `chore: update ingredient mappings for Barbora April snapshot` — catalog update
   - `feat: add swap-meal command and repair-slot skill` — automation
   - `fix: correct weekdayFriendly flag on trout-buckwheat-bowl` — data fix

   For multiple concerns, use the most significant as the primary type and list others in the body.

5. **Display the full proposed commit:**
   ```
   Proposed commit
   ===============
   feat: add menu for 2026-W16 (13–19 апреля)
   
   - 3 fish meals (2 omega-3), 3 legume meals, 0 red meat
   - 2 new recipes added: trout-buckwheat-bowl, chickpea-vegetable-curry
   - Score: 94/100
   
   Files to stage:
     data/menus/2026-W16.json
     data/index.json
     data/recipes.json
   
   Run this to commit:
     git add data/menus/2026-W16.json data/index.json data/recipes.json
     git commit -m "feat: add menu for 2026-W16 (13–19 апреля)"
   ```

6. **Do not run `git add` or `git commit`.** Only display the commands. The user commits explicitly.

## Constraints

- Never use `git add -A` or `git add .` in the suggested commands.
- Never commit `data/catalog/raw/` files.
- Never commit if `validate_data.py` failed.
- The commit message body should include the scoreReport summary when adding a menu.
