Run all validators for a specific week and return a machine-readable report.

## Input contract

```
weekId: 2026-W16
```

## Process

1. Run:
   ```
   python scripts/validate_data.py --week {weekId} --json
   ```
2. Parse the JSON output.
3. Categorise findings:
   - `errors` with validator name `validate_allergy_safety` → **CRITICAL** (highlight separately)
   - `errors` with other validators → ERROR
   - `warnings` → WARNING

## Output contract

```json
{
  "weekId": "2026-W16",
  "passed": true,
  "critical": [],
  "errors": [],
  "warnings": [
    { "validator": "validate_weekly_rules", "message": "red meat meals = 2 (at cap)", "target": "2026-W16" }
  ],
  "summary": "PASS — 0 critical, 0 errors, 1 warning"
}
```

If `passed: false`, include a `remediationHints` array:
```json
"remediationHints": [
  { "error": "...", "hint": "Use /swap-meal 2026-W16 2026-04-15 dinner to replace the failing slot" }
]
```

## This skill does NOT

- Modify any files
- Make content decisions
- Auto-repair failures
