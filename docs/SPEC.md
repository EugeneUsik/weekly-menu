# Weekly Menu App — Implementation Specification for Claude Code

## Purpose

This document defines how to implement the Weekly Menu App using Claude Code as the development and content-orchestration environment.

The key goal is to build the system with a **deterministic local pipeline** where Claude Code is used only for the parts that benefit from language generation.

This specification is intended to be provided to Claude Code so it can plan and execute the full implementation program, including repository setup, application development, data tooling, validation logic, and creation of Claude-specific agents, commands, and skills.

This specification covers:
- product and app requirements
- repository structure
- JSON contracts
- deterministic planning and validation pipeline
- Claude Code agents
- Claude Code commands
- Claude Code skills
- implementation phases
- acceptance criteria

---

# 1. Product Goal

Build a static web application for weekly family meal planning.

The application is read-only for family members and is hosted on GitHub Pages. All content creation, updates, menu generation, substitutions, and commits happen locally through Claude Code on the manager’s computer.

The system must optimize for:
- low token usage
- deterministic outputs
- schema-valid JSON generation
- repeatable local execution
- fast repair of individual meals instead of whole-menu regeneration
- strong nutrition and allergy enforcement
- Barbora catalog compatibility

---

# 2. Core Design Principle

## 2.1 Required Architecture

The system must be implemented as a **pipeline**:

1. deterministic input loading
2. recipe library selection
3. lightweight LLM-assisted ideation only when necessary
4. deterministic nutrition and rule validation
5. deterministic Barbora product resolution
6. deterministic JSON generation
7. deterministic schema validation
8. optional localized repair of only failing items

Claude Code should act as:
- developer
- orchestrator
- targeted content generator
- targeted repair assistant

Claude Code should **not** act as the runtime execution engine for all decision-making.

---

# 3. Family and Nutrition Requirements

These rules are hard requirements and must be encoded in local validation logic.

## 3.1 Household
- Husband, 40M
- Wife, 40F
- Child, 12M

## 3.2 Meal Pattern
- Breakfast, lunch, dinner at home for all three
- Child school snack is excluded from planning
- Shared family snack planned on at least 4 of 7 days

## 3.3 Child Allergy Constraint
Forbidden in any form:
- cherries
- apples
- pears
- apricots
- peaches

The validator must reject any recipe or menu containing those ingredients, including:
- fresh
- cooked
- puree
- juice
- jam
- dried form
- mixed ingredient naming variants

## 3.4 General Food Constraints
- family-friendly flavors
- not spicy
- no processed meat
- red meat limited
- legumes at least 3 times per week
- omega-3 fatty fish at least 2 times per week
- leftovers must be planned intentionally
- weekday active cooking <= 30 minutes
- only immersion blender available
- use metric units

## 3.5 Nutrition Enforcement Strategy
The system must use **rule-based thresholds** and recipe metadata rather than repeated model reasoning.

Nutrition checks must include at minimum:
- meal protein floor per adult
- weekly fish frequency
- weekly legume frequency
- red meat weekly cap
- wife LDL-supportive meal frequency signals
- child growth-supportive coverage signals
- breakfast protein anchor check
- dinner leftovers suitability

The UI does not need to display nutrition calculations, but generation-time validation must enforce them.

---

# 4. Application Scope

## 4.1 In Scope
- static web app
- week selector
- menu view
- shopping list view
- recipes view
- favorites in localStorage
- shopping checkbox state in localStorage
- JSON-driven runtime data loading
- local content generation through Claude Code

## 4.2 Out of Scope
- direct Barbora ordering/cart integration
- backend
- browser-side editing
- accounts/auth
- notifications
- service worker/offline mode
- browser nutrition analytics UI

---

# 5. Technical Architecture

## 5.1 Hosting
- GitHub Pages
- no backend
- no database
- no build step required for MVP

## 5.2 Frontend Stack
Preferred:
- HTML
- CSS
- vanilla JavaScript

Optional:
- TypeScript with zero/very light build tooling only if needed

The default recommendation is:
- `index.html`
- `styles.css`
- `app.js`

Reason: simplest deployment and maintenance model for GitHub Pages.

## 5.3 Runtime Data Loading
The frontend loads JSON using `fetch()` from `/data/`.

On app load:
1. fetch `/data/index.json`
2. determine selected week
3. fetch `/data/recipes.json`
4. fetch selected `/data/menus/{weekId}.json`
5. render active screen

---

# 6. Repository Structure

```text
/
  index.html
  styles.css
  app.js
  /data/
    index.json
    recipes.json
    /menus/
      2026-Mar-2.json
    /catalog/
      /raw/
      /normalized/
      ingredient-map.json
      substitution-map.json
  /scripts/
    generate_menu.py
    validate_data.py
    normalize_catalog.py
    score_plan.py
    aggregate_shopping.py
    sync_index.py
  /.claude/
    /agents/
    /commands/
    /skills/
  /docs/
    SPEC.md
    DATA_SCHEMA.md
    OPERATIONS.md
```

---

# 7. Data Model

## 7.1 Rule
Claude Code must never directly handcraft final JSON in an unconstrained way.

All generated data must be validated against explicit schemas before being written.

## 7.2 Files

### `/data/index.json`
Manifest of available weeks.

### `/data/recipes.json`
Append-only recipe library.

### `/data/menus/{weekId}.json`
Resolved weekly menu and shopping list.

### `/data/catalog/ingredient-map.json`
Canonical ingredient mapping between internal ingredient keys and Barbora Lithuanian names.

### `/data/catalog/substitution-map.json`
Approved substitutions for unavailable products.

---

# 8. Canonical Internal Model

The system must use **canonical ingredient IDs** and **recipe metadata**.

## 8.1 Canonical Ingredient Example
```json
{
  "id": "chicken_breast",
  "nameEn": "chicken breast",
  "nameRu": "Куриное филе",
  "nameLt": "Vištienos filė",
  "category": "meat",
  "defaultUnit": "g",
  "aliases": ["chicken fillet", "куриное филе"]
}
```

## 8.2 Recipe Metadata Requirements
Each recipe must contain, at minimum:
- stable recipe ID
- display name in Russian
- meal type
- active minutes
- total minutes
- servings metadata
- ingredients with canonical IDs and quantities
- Russian steps
- storage note
- substitutions note
- tags
- nutrition estimate metadata
- validation flags

## 8.3 Required Recipe Flags
Each recipe should include booleans/tags for deterministic planning:
- `weekdayFriendly`
- `leftoversFriendly`
- `childSafe`
- `containsFish`
- `containsOmega3Fish`
- `containsLegumes`
- `containsRedMeat`
- `containsSoy`
- `containsEggs`
- `containsDairy`
- `highProtein`
- `highFiber`

---

# 9. Menu Generation Strategy

## 9.1 Planning Model
Menu generation must be a **selection-and-validation problem**, not a fully generative composition problem.

The planner should prefer existing recipes from `recipes.json`.

Only generate a new recipe when:
- no existing recipe fits constraints, or
- variety rules require expansion, or
- a requested swap has no acceptable library replacement

## 9.2 Planning Inputs
The planner must load:
- recipe library
- recent 4 weeks of menus
- family rules
- normalized catalog
- ingredient map
- substitution map

## 9.3 Variety Rules
- >= 70% of dinners must differ from the previous 4 weeks
- >= 50% of breakfasts must differ from the previous 4 weeks
- no signature dinner repeat within 4 rolling weeks

## 9.4 Leftover Rule
Dinner planned with leftovers must provide:
- dinner for household
- next-day lunch for household

Portion scaling must be done in code.

## 9.5 Weekly Candidate Generation
The planner should:
1. select candidate breakfasts
2. select candidate dinners
3. assign lunches based on leftovers first
4. fill remaining lunches from recipe library
5. assign >=4 snacks
6. run rule scoring
7. repair only failing slots

## 9.6 Candidate Scoring
Implement a scoring function with hard rejects and soft penalties.

### Hard Rejects
- allergy violation
- missing recipe reference
- missing ingredient mapping without substitution
- weekday prep over limit for weekday meal
- invalid schema

### Soft Penalties
- protein below target
- insufficient fish count
- insufficient legume count
- too much red meat
- too little breakfast variety
- too much dinner repetition
- weak wife LDL support distribution
- insufficient dairy coverage for child signals

---

# 10. Barbora Catalog Strategy

## 10.1 Rule
Barbora product resolution must be done **outside** the main LLM reasoning flow.

## 10.2 Catalog Pipeline
Implement a normalization script:
- ingest raw Barbora snapshot
- normalize category names
- normalize units
- map aliases
- create canonical ingredient map
- generate substitution map for unavailable ingredients

## 10.3 Resolution Order
When resolving an ingredient:
1. exact canonical mapping
2. alias mapping
3. category-compatible substitution
4. explicit failure report

## 10.4 LLM Usage for Catalog
Claude Code may assist only in building or refining mapping tables offline.
It should not perform store-product lookup reasoning during every weekly generation.

---

# 11. Validation Pipeline

## 11.1 Required Validators
Implement separate validators for:
- schema validation
- ingredient mapping completeness
- allergy safety
- recipe link integrity
- leftovers integrity
- weekly nutrition rule coverage
- shopping list deduplication
- unit consistency

## 11.2 Validation Rule
No file may be written to `/data/menus/` unless all hard validations pass.

## 11.3 Repair Rule
When validation fails, repair should target only:
- one recipe
- one meal slot
- one ingredient mapping
- one substitution

Never regenerate the whole week unless the structure is unsalvageable.

---

# 12. Shopping List Rules

The shopping list must be generated in code from resolved recipe ingredients.

## 12.1 Requirements
- each product appears once only per week
- grouped by earliest day first needed
- then grouped by category
- row contains checkbox-compatible identity
- Russian and Lithuanian names must both be present
- amount and unit must be normalized

## 12.2 Checkbox Identity Key
Use:
`{weekId}:{category}|{nameRu}|{unit}`

---

# 13. Frontend UX Requirements

## 13.1 Devices
Primary target: iPhone 13/15/16 width class.
No horizontal scrolling allowed.

## 13.2 Navigation
Sticky top bar with:
- week selector
- Menu
- Shopping List
- Recipes

## 13.3 Menu Screen
- days as rows
- meal types as columns
- clickable dish links
- inline recipe expansion
- leftover cells link to original recipe
- snack empty state shown as em dash

## 13.4 Shopping List Screen
- tappable rows
- checkbox state in localStorage
- Reset / Check All buttons

## 13.5 Recipes Screen
- meal type filter tabs
- favourites toggle
- inline expandable cards
- favourite stored in localStorage

---

# 14. Claude Code Operating Model

Claude Code must be configured with dedicated agents, commands, and skills.

The purpose is to reduce context bloat and make each operation small, deterministic, and reusable.

---

# 15. Claude Code Agents

Agents are role-focused helpers with tightly scoped responsibilities.

## 15.1 `frontend-architect`
### Responsibility
- scaffold and evolve static UI
- maintain app structure
- implement rendering logic
- enforce mobile layout rules

### Inputs
- SPEC.md
- menu JSON schema
- recipes schema

### Output
- HTML/CSS/JS code

### Must Not
- invent nutrition rules
- alter data contracts without approval

---

## 15.2 `menu-planner`
### Responsibility
- assemble weekly meal selections from recipe library
- apply variety heuristics
- propose localized swaps

### Inputs
- recipe metadata
- previous menus
- weekly target week ID

### Output
- intermediate planning object only

### Must Not
- write final production JSON directly
- resolve Barbora names inline

---

## 15.3 `recipe-generator`
### Responsibility
- generate new recipes only when planner cannot satisfy constraints from library
- produce Russian recipe text from constrained structured input

### Inputs
- meal type
- target ingredient set
- constraints
- required nutrition profile bands

### Output
- recipe draft object

### Must Not
- generate an entire weekly plan
- perform shopping aggregation

---

## 15.4 `nutrition-validator`
### Responsibility
- review candidate recipes and weekly plans
- check them against encoded rules
- emit machine-readable warnings/errors

### Output
- validation report

### Must Not
- rewrite recipe prose unless explicitly asked

---

## 15.5 `catalog-mapper`
### Responsibility
- maintain ingredient-map and substitution-map
- resolve canonical ingredient IDs to Barbora Lithuanian names

### Output
- normalized mapping files
- mapping diffs

### Must Not
- plan menus

---

## 15.6 `data-integrity-keeper`
### Responsibility
- validate schemas
- ensure link integrity
- ensure no missing fields
- ensure IDs are stable
- ensure shopping list dedupe

### Output
- pass/fail report
- exact remediation targets

---

## 15.7 `repo-operator`
### Responsibility
- run generation flow
- update index
- stage files
- prepare commits
- maintain docs

### Must Not
- silently change data model

---

# 16. Claude Code Commands

Commands are user-facing entry points. They should be thin wrappers around scripts and skills.

## 16.1 `/bootstrap-app`
### Purpose
Create the project from scratch.

### Actions
- scaffold frontend files
- scaffold data folders
- scaffold Claude folders
- create schemas and placeholders
- create starter docs

### Output
- initial runnable repository

---

## 16.2 `/generate-menu <weekId...>`
### Purpose
Generate one or more menu weeks.

### Actions
1. load recipes and prior menus
2. build candidate plan
3. generate only missing recipes if needed
4. resolve ingredients to catalog
5. validate
6. write JSON
7. update index
8. print summary

### Output Summary
- weeks generated
- recipes reused
- recipes newly created
- substitutions applied
- warnings

---

## 16.3 `/swap-meal <weekId> <day> <mealType>`
### Purpose
Replace a single meal slot without regenerating the whole week.

### Actions
- inspect current slot
- find compatible alternatives
- validate replacement
- patch affected shopping list
- rewrite only impacted files

---

## 16.4 `/validate-data`
### Purpose
Run all validators.

### Output
- schema errors
- integrity errors
- mapping gaps
- allergy violations
- menu rule violations

---

## 16.5 `/normalize-catalog`
### Purpose
Rebuild normalized Barbora mapping artifacts from raw snapshot.

---

## 16.6 `/add-recipe`
### Purpose
Create a single recipe entry from a constrained structured request.

### Output
- validated recipe draft
- optional append to library

---

## 16.7 `/rebuild-shopping <weekId>`
### Purpose
Recompute shopping list from existing menu and recipe references.

---

## 16.8 `/prepare-commit`
### Purpose
Summarize changed files and suggest commit message.

---

# 17. Claude Code Skills

Skills are reusable internal workflows used by commands and agents.

## 17.1 Skill: `plan-week`
### Purpose
Produce an intermediate weekly plan object using recipe metadata and recent menus.

### Inputs
- target week ID
- recipe library
- previous 4 weeks

### Output
- candidate plan object
- score breakdown

---

## 17.2 Skill: `generate-recipe-from-constraints`
### Purpose
Generate one recipe only.

### Inputs
- meal type
- ingredient constraints
- prep time limit
- nutrition requirements
- prohibited ingredients

### Output
- structured recipe draft

---

## 17.3 Skill: `resolve-ingredient-names`
### Purpose
Attach `nameLt` and product category using local mapping files.

### Output
- resolved ingredient list
- unresolved items list

---

## 17.4 Skill: `validate-week`
### Purpose
Run all weekly checks and emit a machine-readable report.

---

## 17.5 Skill: `repair-slot`
### Purpose
Repair one failed meal slot.

### Rule
Must not touch unaffected days/meals.

---

## 17.6 Skill: `append-recipes`
### Purpose
Merge new validated recipes into `recipes.json` without breaking IDs or formatting.

---

## 17.7 Skill: `write-menu-files`
### Purpose
Serialize validated intermediate objects into production JSON files.

---

# 18. Intermediate Data Contracts

To minimize model complexity, generation must use small intermediate schemas.

## 18.1 Weekly Plan Candidate
```json
{
  "weekId": "2026-Mar-2",
  "breakfasts": [
    { "day": "Monday", "recipeId": "protein-oat-bowl" }
  ],
  "lunches": [
    { "day": "Monday", "recipeId": "chicken-rice-bowl", "isLeftover": true }
  ],
  "dinners": [
    { "day": "Monday", "recipeId": "chicken-rice-bowl", "cookFresh": true }
  ],
  "snacks": [
    { "day": "Monday", "recipeId": "yogurt-walnut-berries" }
  ]
}
```

## 18.2 Recipe Draft
```json
{
  "id": "salmon-lentil-bowl",
  "nameRu": "Боул с лососем и чечевицей",
  "mealType": "dinner",
  "activeMinutes": 25,
  "totalMinutes": 35,
  "ingredients": [
    { "ingredientId": "salmon_fillet", "amount": 600, "unit": "g" }
  ],
  "stepsRu": ["..."],
  "tags": ["fish", "high-protein", "weekday-friendly"]
}
```

The final production schema should be built from these intermediate structures in code.

---

# 19. Implementation Rules for Claude Code

## 19.1 General Rules
Claude Code must:
- prefer editing existing files over rewriting large files when possible
- keep JSON stable and consistently formatted
- isolate changes by concern
- document every command and script
- keep prompts focused and narrow

## 19.2 Prompting Rules
Prompts must ask for one thing at a time.

Allowed:
- propose 5 dinner candidates
- generate 1 new breakfast recipe
- repair Tuesday dinner
- review mapping gaps

Not allowed:
- generate whole week + recipes + shopping + translations + final JSON in one prompt

## 19.3 Failure Handling
If a step fails:
1. produce explicit failure report
2. identify smallest repair unit
3. retry only that unit

---

# 20. Build Phases

## Phase 1 — Repository Bootstrap
- scaffold frontend
- scaffold `/data`
- scaffold `/scripts`
- scaffold `.claude`
- define schemas
- add placeholder sample week and recipes

## Phase 2 — Runtime UI
- implement week selector
- menu screen
- shopping screen
- recipes screen
- localStorage support

## Phase 3 — Deterministic Data Tooling
- recipe loader
- menu loader
- shopping aggregator
- validators
- index sync

## Phase 4 — Planning Engine
- recipe metadata model
- weekly selection logic
- scoring
- leftovers logic
- recent-menu variety check

## Phase 5 — Controlled Recipe Generation
- single recipe generation flow
- constrained prompt templates
- append-only recipe integration

## Phase 6 — Catalog Normalization
- normalized Barbora artifacts
- ingredient map
- substitution map
- resolution script

## Phase 7 — Claude Code Automation
- agents
- commands
- skills
- operational docs

## Phase 8 — Review and Hardening
- test on several weeks
- validate swap flows
- validate shopping dedupe
- validate performance and maintainability

---

# 21. Acceptance Criteria

Implementation is complete when all of the following are true:

## 21.1 App
- app loads statically from GitHub Pages
- no backend required
- no horizontal scroll on target phones
- week selection works
- menu/shopping/recipes screens work
- localStorage favorites and checkboxes work

## 21.2 Data
- all data loads from JSON
- schemas documented
- menu files validate
- recipe IDs are stable
- shopping list is deduplicated

## 21.3 Generation
- one-week generation can run through the defined command pipeline without a giant chat session
- most weeks are produced by recipe selection, not full recipe invention
- only missing recipes invoke generation
- a single meal can be swapped without rebuilding the whole week

## 21.4 Validation
- allergy violations are blocked
- missing Lithuanian mappings are blocked or substituted deterministically
- protein and weekly rule checks run locally
- failed slots can be repaired in isolation

## 21.5 Claude Code Workflow
- agents exist and are documented
- commands exist and are documented
- skills exist and are documented
- manager can run a predictable operational flow from bootstrap to commit

---

# 22. Suggested Initial Deliverables for Claude Code

Claude Code should implement the system in this order:

1. `SPEC.md` — this specification
2. `DATA_SCHEMA.md` — explicit JSON schemas and examples
3. `OPERATIONS.md` — how to use commands and skills
4. frontend scaffold
5. sample data files
6. validation scripts
7. weekly planning script
8. catalog normalization script
9. Claude agents
10. Claude commands
11. Claude skills

---

# 23. Operational Flow for the Manager

The intended weekly workflow is:

1. refresh or confirm Barbora snapshot if needed
2. run `/generate-menu <weekId>`
3. inspect summary
4. optionally run `/swap-meal ...`
5. run `/validate-data`
6. run `/prepare-commit`
7. commit and push

This flow must be faster and more reliable than the prior all-in-one generation approach.

---

# 24. Final Instruction to Claude Code

This document will be used as implementation input for planning and executing all required steps.

Claude Code should:
- first produce an implementation plan that breaks the work into ordered phases and concrete tasks
- explicitly identify which tasks require scripts, frontend files, schemas, agents, commands, and skills
- define dependencies between tasks before starting implementation
- implement the system using deterministic local logic wherever possible
- use small focused prompts over monolithic prompts
- use reusable recipe metadata over repeated reinvention
- use isolated repairs over full regeneration
- enforce schema validation before file writes
- prefer maintainable repository structure over cleverness

The implementation plan must include creation of all required Claude Code agents, commands, and skills as first-class deliverables.

