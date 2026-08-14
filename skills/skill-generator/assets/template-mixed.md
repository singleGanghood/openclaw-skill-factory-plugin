---
name: your-skill-name
description: |
  ALWAYS invoke this skill when the user asks about [English description],
  [中文功能描述]. Trigger keywords: '[English keyword]', '[中文关键词]',
  '[keyword3]', '[关键词4]', '[keyword5]'.
  Do not [handle/直接处理此任务] — use this skill first.
  Do NOT use for [exclusion/排除场景].
---

# Skill Title / 技能标题

## Quick Reference

| Task / 任务 | Guide / 指引 |
|------|------|
| 详细规范 / Detailed spec | Read [references/detail-spec.md](references/detail-spec.md) |
| 输出模板 / Output template | Copy [assets/output-template.md](assets/output-template.md) |

---

## Overview / 概述

Brief description of what this skill does.
简要描述本技能的功能、支持的模式和核心价值。

---

## When to Use / 适用场景

✅ **Use when / 适用**：
- Scenario 1 / 场景 1
- Scenario 2 / 场景 2
- Scenario 3 / 场景 3

❌ **Do NOT use for / 不适用**：
- Exclusion 1 / 排除场景 1
- Exclusion 2 / 排除场景 2

---

## Workflow / 工作流程

### Step 1: [Action] / 步骤 1：[动作]

Description of this step.
本步骤的具体操作描述。

```bash
# Example command / 示例命令
python scripts/process.py --input {file}
```

Expected output / 预期输出：[describe / 描述]

### Step 2: [Action] / 步骤 2：[动作]

Step 2 description.
步骤 2 描述。

### Step 3: [Action] / 步骤 3：[动作]

Step 3 description.
步骤 3 描述。

---

## Examples / 示例

### Example 1: [Scenario] / 示例 1：[场景]

**User says / 用户说：** "Do X with Y" / 「对 Y 执行 X」

**Execution / 执行：**
1. Parse input / 解析输入
2. Process / 处理
3. Output / 输出

**Result / 结果：** [Expected output / 预期输出]

---

## Guidelines / 约束规则

- Rule 1 / 规则 1：Validate input / 验证输入
- Rule 2 / 规则 2：Handle errors gracefully / 优雅处理错误
- Rule 3 / 规则 3：Follow format strictly / 严格遵循格式

---

## Common Issues / 常见问题

### Error: [Name] / 错误：[名称]

**Cause / 原因：** Why / 为什么
**Solution / 解决：** How / 如何修复

---

## Dependencies / 依赖

- Dependency 1 / 依赖 1
- Dependency 2 / 依赖 2 (optional / 可选)
