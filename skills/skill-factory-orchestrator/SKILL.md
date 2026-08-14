---
name: skill-factory-orchestrator
description: |
  ALWAYS invoke this skill when the user wants an END-TO-END skill production pipeline:
  from a requirement (or a screenshot / design mock) all the way to a validated, governed Skill.
  从需求（或截图）一站式产出、评估、（可选）拆分并治理登记一个高质量 Skill。
  Trigger keywords: 'skill factory', 'produce a skill', 'make a skill end to end', '造技能',
  '技能工厂', '一站式做skill', '从截图做skill', '批量产skill', '持续生产skill',
  'skill pipeline', 'generate then assess skill'.
  Do NOT use for a single isolated step — use skill-generator / skill-assessor / skill-splitter
  / skill-factory-screenshot directly for one-off actions.
metadata:
  openclaw:
    emoji: "🏗️"
    skillKey: "skill-factory"
---

# Skill Factory Orchestrator — 龙虾持续生产新 Skill 的薄编排器

把 `skill-factory-screenshot`（可选看屏输入）、`skill-generator`（生成）、`skill-assessor`（评估）、
`skill-splitter`（可选拆分）串成一条闭环流水线，并完成 **OpenClaw 路径与授权边界改造**。

本编排器**只做路由与治理登记，不含业务逻辑**——每一步都委托给对应的子 skill。

## Quick Reference

| 任务 | 指引 |
|------|------|
| 治理注册表 Schema 与登记规则 | Read [references/governance-registry.md](references/governance-registry.md) |
| eligible vs 治理：两个事实源边界 | Read [references/two-sources-of-truth.md](references/two-sources-of-truth.md) |

---

## Overview：七步闭环（对应产品设计）

| # | 步骤 | 委托给 | 门禁 |
|---|------|--------|------|
| 01 | 需求（功能/边界/输入输出） | 用户 / screenshot | — |
| 02 | 暂存创建（隔离候选，不影响线上） | `skill-generator` | 只写暂存区，不自动安装、不覆盖同名 skill |
| 03 | 质量评估（结构/安全/测试/eval） | `skill-assessor` | 静态高分不能冒充运行时可用 |
| 04 | 授权安装（用户明确同意后执行） | `openclaw plugins`/手动 | 需用户明确同意 |
| 05 | 运行验证（info + eligible） | eligibility 判定 | OS/bins/env 真实就绪才算可用 |
| 06 | 新会话测试（正例触发、反例不误触） | 新 session | 触发词命中 + 排除有效 |
| 07 | 治理登记（版本、hash、回滚证据） | 本编排器 | 只写注册表，不改 eligible |

> **两个事实源不能混**：OpenClaw 的 per-agent eligible 清单决定"现在能不能用"；治理注册表记录"哪个版本通过过什么验证"。注册表不能替代运行时。

---

## When to Use

✅ **适用**：
- 从一句话需求 / 一张截图，一路产出可用且经过质量把关的 Skill
- 需要"生成 → 评估 → 不达标回喂重生成"的自动迭代闭环
- 需要在产出后做治理登记（版本/hash/回滚证据）以便审计

❌ **不适用**：
- 只想做单步（只生成 / 只评估 / 只拆 / 只截图）→ 直接用对应子 skill
- 安装外部 skill → 用 `find-skills`

---

## Workflow

### Step 01 — 需求收集
若用户提供的是**截图/设计稿/现有工具界面**，先委托 `skill-factory-screenshot` 产出 `requirementDraft`；
否则直接从用户描述提炼：功能、边界、输入/输出、触发词、是否需要脚本/依赖。

### Step 02 — 暂存创建（隔离候选）
委托 `skill-generator` 生成骨架。**门禁**：
- 只写入**暂存目录**（如 `.skill-factory/staging/<name>/`），不写入生效目录
- **不自动安装**、**不覆盖同名已有 skill**（同名冲突则改名或提示）

### Step 03 — 质量评估
委托 `skill-assessor` 对暂存候选打分（7 维度，100 分制）。
**门禁**：静态高分 ≠ 运行时可用。低于阈值（建议 ≥ 80）则拿评估输出的"优化指令"回喂 Step 02，形成 Draft→Check→Loop。
（可选）若候选超阈值过大（>10 分钟 / >20 文件 / ≥3 功能域），委托 `skill-splitter` 拆分。

### Step 04 — 授权安装（需用户明确同意）
**必须由用户明确同意后**，才把暂存候选转正到生效目录，或经 `openclaw plugins install` 走插件分发。
未同意前一律停留在暂存区。

### Step 05 — 运行验证（info + eligible）
- `info`：读取 SKILL.md 静态元数据（name/description/metadata.openclaw）
- `eligible`：判定运行时是否真正就绪——OS 是否匹配 `os`、`requires.bins` 是否在 PATH、`env`/`config` 是否满足
- 二者同时满足才算"该 agent 现在能用"。**只读判定，不修改 per-agent 白名单。**

### Step 06 — 新会话测试
在新 session 验证：正例（目标触发词能命中并加载）、反例（`Do NOT use for` 场景不误触发）。

### Step 07 — 治理登记（只写注册表）
按 [references/governance-registry.md](references/governance-registry.md) 追加一条记录到治理注册表：
`name / version / contentHash / assessorScore / verifiedAt / verifiedBy / rollbackRef`。
**约束**：本步骤**只写治理注册表，绝不修改 eligible / per-agent skills 配置**——两个事实源分离。

---

## Examples

### 示例：从截图一路产出并登记
**用户说：**「这是内部报销工具的截图，帮我造个自动填报销的 skill，走完整流程」
1. Step01 委托 screenshot 桥接 → requirementDraft
2. Step02 skill-generator → 暂存 `expense-filler`
3. Step03 skill-assessor → 76 分 → 回喂优化 → 再评 88 分
4. Step04 用户同意 → 转正
5. Step05 eligible 判定（需 peekaboo，os=darwin）通过
6. Step06 新会话正/反例测试通过
7. Step07 登记 `expense-filler@1.0.0 / hash / 88 / verified`

---

## Guidelines / Constraints

- **编排器要薄**：只路由 + 治理登记，业务全部委托子 skill。
- **暂存优先**：未经用户明确同意，候选永远停在暂存区，不影响线上。
- **回喂闭环**：assessor 低分必须回喂 generator，禁止跳过评估直接安装。
- **两个事实源分离**：治理登记 ≠ 运行时 eligible；登记步骤不改 per-agent 白名单。
- **授权边界**：涉及截图的高风险命令，遵守 `skill-factory-screenshot` 的 arm/disarm 与 TCC 授权。

---

## Common Issues / Troubleshooting

### Error: 候选评估分数上不去
**原因：** description 无触发词 / 缺 When to Use / 缺 Examples。
**解决：** 用 assessor 输出的优化指令回喂 generator，循环至达标。

### Error: 安装后 agent 里看不到该 skill
**原因：** eligible 未通过（OS 不匹配 / bin 缺失 / 不在 per-agent 白名单）。
**解决：** 看 Step05 的 eligible 判定；确认 `requires.bins`；检查 `agents.<id>.skills` 或 `agents.defaults.skills` 白名单。这是 eligible 问题，与治理注册表无关。

---

## Dependencies

- 子 skill：`skill-factory-screenshot`、`skill-generator`、`skill-assessor`、`skill-splitter`（同插件捆绑）
- 治理注册表文件：`.skill-factory/registry.json`（首次自动创建）
- 无第三方依赖
