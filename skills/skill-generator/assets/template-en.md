---
name: your-skill-name
description: |
  ALWAYS invoke this skill when the user asks about [primary function],
  [secondary function], or [tertiary function].
  Trigger keywords: '[keyword1]', '[keyword2]', '[keyword3]', '[keyword4]'.
  Do not [handle this type of task] directly — use this skill first.
  Do NOT use for [exclusion1], [exclusion2], or [exclusion3].
---

# Your Skill Name — One-Line Description

## Quick Reference

| Task | Guide |
|------|-------|
| Detailed specification | Read [references/detail-spec.md](references/detail-spec.md) |
| Output template | Copy [assets/output-template.md](assets/output-template.md) |

---

## Overview

Brief description of what this skill does, what modes/variants it supports,
and what makes it valuable.

---

## When to Use

✅ **Use when**:
- Scenario 1
- Scenario 2
- Scenario 3

❌ **Do NOT use for**:
- Exclusion 1
- Exclusion 2

---

## Workflow

### Step 1: [Action Name]

Description of what happens in this step.

```bash
# Example command if applicable
python scripts/process.py --input {file}
```

Expected output: [describe what success looks like]

### Step 2: [Action Name]

Description of step 2.

### Step 3: [Action Name]

Description of step 3.

---

## Examples

### Example 1: [Common Scenario]

**User says:** "Do X with Y"

**Execution:**
1. Parse input
2. Process with Z
3. Output result

**Result:** [Expected output description]

### Example 2: [Edge Case]

**User says:** "Handle unusual case"

**Execution:**
1. Detect edge case
2. Apply fallback logic

**Result:** [Expected output description]

---

## Guidelines

- Rule 1: Always validate input before processing
- Rule 2: Handle errors gracefully with descriptive messages
- Rule 3: Output should follow the specified format exactly
- Rule 4: [Domain-specific constraint]

---

## Common Issues

### Error: [Common Error Name]

**Cause:** Why this happens
**Solution:** How to fix it

### Error: [Another Error]

**Cause:** Why this happens
**Solution:** How to fix it

---

## Dependencies

- Dependency 1 (version requirement)
- Dependency 2 (optional, for feature X)
