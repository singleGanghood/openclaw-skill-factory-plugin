---
name: skill-factory-eval
description: |
  ALWAYS invoke this skill to run EVAL-DRIVEN, TDD-style quality gating on a Skill:
  auto-generate a trigger eval set, run train/test split benchmark to measure
  precision/recall/accuracy, and AUTO-OPTIMIZE the description in a closed loop
  until it triggers on the right queries and ignores the wrong ones.
  用 TDD/eval 驱动的方式给 Skill 做动态触发跑分并自动优化 description，直到达标。
  Trigger keywords: 'eval skill', 'benchmark skill', 'test skill triggering',
  'optimize description', 'tune description', 'description 优化', '触发测试',
  'skill 跑分', 'skill benchmark', 'TDD skill', '自动优化触发词', 'trigger eval',
  'precision recall skill', 'golden case skill'.
  Do NOT use for static structure scoring only (use skill-assessor) or for creating
  a brand-new skill from scratch (use skill-generator).
metadata:
  openclaw:
    emoji: "🎯"
    skillKey: "skill-factory"
    requires:
      bins: ["python3"]
---

# Skill Factory Eval — TDD / eval-driven 触发跑分 + description 自动优化引擎

这是本插件相对 Anthropic 官方 `skill-creator` 的 **对标补齐 + 反超引擎**。它把
「把 Skill 当代码用 TDD 写」的 eval-driven 流派落地为**两段式**：

- **快路径（Fast Path）**：零模型调用、毫秒级的**静态触发力分析**，先淘汰 80% 的弱 description。
- **慢路径（Deep Path）**：只对通过快路径的候选，用**宿主自带 subagent**做 train/test 分层跑分，
  测 precision/recall/accuracy，并按 test 集选最优 description（防过拟合）。

> 与官方 `skill-creator` 的关键差异见 [references/vs-skill-creator.md](references/vs-skill-creator.md)：
> **零外部 SDK 依赖**（不依赖 `anthropic` / `claude -p` CLI / `webbrowser`）、**快路径短路提速**、
> **静态+动态混合判分**、**与 OpenClaw 生态注册打通**。

## Quick Reference

| 任务 | 指引 |
|------|------|
| 生成触发 eval set（正例/反例） | Run [scripts/gen_eval_set.py](scripts/gen_eval_set.py) 生成骨架，再人工/subagent 补全 |
| 静态触发力分析（快路径，0 模型调用） | Run [scripts/static_trigger_score.py](scripts/static_trigger_score.py) |
| train/test 分层分割（防过拟合） | Run [scripts/split_eval.py](scripts/split_eval.py) |
| 动态跑分聚合（precision/recall/accuracy） | Run [scripts/aggregate_eval.py](scripts/aggregate_eval.py) |
| description 自动优化的判分/停止规则 | Read [references/eval-loop.md](references/eval-loop.md) |
| TDD golden case 写法 | Read [references/tdd-golden-cases.md](references/tdd-golden-cases.md) |
| 判分器（grader）评判准则 | Read [references/grader-rubric.md](references/grader-rubric.md) |
| 对标官方 skill-creator 的差异与反超点 | Read [references/vs-skill-creator.md](references/vs-skill-creator.md) |

---

## Overview：两段式 eval（快路径 → 慢路径）

```
候选 SKILL.md
   │
   ├─(1) 快路径 static_trigger_score.py ── 0 模型调用，毫秒级
   │        └─ score < 阈值 ? → 直接产出优化指令回喂 generator（不起模型，秒级闭环）
   │
   └─(2) 通过快路径 → 慢路径动态跑分
            ├─ gen_eval_set.py    生成正例(should_trigger)+反例(should NOT)骨架
            ├─ split_eval.py      按 should_trigger 分层切 train/test（默认 holdout=0.4）
            ├─ 宿主 subagent 跑 train+test：每 query 跑 N 次，统计触发率
            ├─ aggregate_eval.py  算 precision/recall/accuracy，标 PASS/FAIL
            └─ 未达标 → 用 failed/false triggers（隐藏 test 分）回喂改 description → 循环
                       └─ 按 TEST 集选最优（防过拟合）
```

**为什么比官方快**：官方每轮都真实起 `claude -p` 子进程对全量 query 跑 `runs_per_query` 次；
本引擎先用**零调用的静态分析**淘汰绝大多数弱候选，只有"值得跑"的才进慢路径，
且慢路径复用**宿主已在运行的 subagent**而非新拉外部 CLI，省掉进程/SDK 冷启动。

---

## When to Use

✅ **适用**：
- 给一个 Skill 做**动态触发测试**（正例能触发、反例不误触发）——这是纯静态评估补不上的短板
- 让 description **自动迭代优化**到 precision/recall 达标，而不是手工瞎改
- 交付前做 TDD 式质量门禁：先写会失败的反例/正例 golden case，再逼着 description 通过
- 对比多个 description 候选，用 benchmark 数据客观选最优

❌ **不适用**：
- 只要静态结构/规范打分 → 用 `skill-assessor`
- 从零造 Skill → 用 `skill-generator`
- 大 Skill 拆分 → 用 `skill-splitter`

---

## Workflow

### Phase 0 — 快路径静态触发力分析（先跑，秒级）

```bash
python3 scripts/static_trigger_score.py <skill-dir>/SKILL.md
```

输出 0–100 的**静态触发力分数**与明细（触发词数量、口语化词、排除边界、歧义冲突、长度）。

- **分数 ≥ 70**：值得进慢路径动态跑分。
- **分数 < 70**：**直接**用脚本给出的 `optimization_hints` 回喂 `skill-generator` 改写，
  改完再跑快路径——**全程 0 次模型调用**，秒级闭环。这是相对官方最大的提速点。

### Phase 1 — 生成 eval set（TDD golden cases）

```bash
python3 scripts/gen_eval_set.py <skill-dir>/SKILL.md > eval_set.json
```

脚本从 SKILL.md 的 description / When to Use / `Do NOT use for` 抽取，生成**骨架**：
- `should_trigger: true` 的正例（用户真实意图的多种问法）
- `should_trigger: false` 的反例（相邻/易混淆但不该触发的问法）

**TDD 要求**：交付前必须补足**至少 3 正例 + 3 反例**（写法见
[references/tdd-golden-cases.md](references/tdd-golden-cases.md)）。反例要覆盖 `Do NOT use for` 的每一条。

### Phase 2 — train/test 分层分割（防过拟合）

```bash
python3 scripts/split_eval.py eval_set.json --holdout 0.4 --seed 42 > split.json
```

按 `should_trigger` **分层**切分（train 用于优化、test 只用于选最优），避免 description 过拟合到具体问法。

### Phase 3 — 动态跑分（宿主 subagent，零外部 SDK）

对 train+test 的每个 query，用**宿主自带的 subagent 能力**发起一次"只给 available_skills 列表、
问模型是否会调用本 skill"的判定（判定准则见
[references/grader-rubric.md](references/grader-rubric.md)），每 query 重复 N 次（默认 3）统计触发率。

> **不要**调用 `anthropic` SDK 或 `claude -p` CLI。用你当前宿主（OpenClaw / CodeBuddy）
> 已提供的 subagent / task 机制发起判定，把每次结果写成 JSON 行喂给聚合脚本。

```bash
python3 scripts/aggregate_eval.py raw_runs.json --trigger-threshold 0.5 > eval_results.json
```

输出：每 query 的 `triggers/runs`、`pass`，以及总体 `precision / recall / accuracy`。

### Phase 4 — description 自动优化闭环

按 [references/eval-loop.md](references/eval-loop.md)：
- 若 train 有 FAIL：收集 `failed_triggers`（该触发没触发）+ `false_triggers`（不该触发却触发），
  **隐藏 test 分数**，连同"历史尝试（不要重复）"一起，让模型改写 description（≤ 100–200 词，硬上限 1024 字符）。
- 改完回 Phase 3 重跑；**按 test 集分数选最优**。
- 停止条件：train 全过 **或** 达到 `max_iterations`（默认 5）。

### Phase 5 — 产出判定

- **达标**（test 集 precision/recall 均 ≥ 目标，默认 ≥ 0.8）：把最优 description 写回 SKILL.md，
  产出 `eval_results.json` 作为**动态验证证据**，交回 orchestrator 登记。
- **未达标**：产出结构化优化指令 + 最优候选，交回 orchestrator，人工介入或换 generator 策略。

---

## Examples

### Example 1：快路径秒级拦截弱 description
**用户说：**「给我这个 skill 跑个触发测试」
1. Phase 0 `static_trigger_score.py` → 52 分（无口语化触发词、缺反例边界）
2. 直接回喂 generator 优化指令（**0 模型调用**）→ 改写后再跑 → 78 分
3. 进 Phase 1–4 动态跑分，precision 0.9 / recall 0.85 → 达标

### Example 2：动态跑分发现"反例误触发"
**用户说：**「我的 skill 老是误触发，帮我调 description」
1. Phase 1 生成 eval set，补 3 正 3 反
2. Phase 3 跑分：正例 recall=1.0，但 2 个反例被误触发（precision=0.6）
3. Phase 4 回喂：强化 `Do NOT use for` 边界 → 重跑 precision=1.0，recall=0.9 → 按 test 集选定

---

## Guidelines / Constraints

- **快路径优先**：能用 0 模型调用的静态分析解决就不起模型——这是提速与省钱的核心。
- **零外部 SDK**：动态跑分只用宿主 subagent，**禁止** import `anthropic` / 调 `claude -p` / 开 `webbrowser`。
- **防过拟合**：优化只看 train，选最优只看 test；改写时对模型**隐藏 test 分**。
- **description 硬约束**：≤ 1024 字符，无尖括号 `< >`，kebab-case name。
- **不改运行时 eligible**：本引擎只产出"验证证据"，是否上线由 orchestrator + 用户决定；
  不去动 per-agent skills 白名单（两个事实源分离）。

---

## Common Issues / Troubleshooting

### Error: 静态分数高但动态跑分差
**原因：** 关键词堆砌但与真实用户意图不符（overfit 到词面）。
**解决：** 补更贴近真实问法的正例、更接近边界的反例，重跑 Phase 3–4。

### Error: 优化几轮后来回震荡
**原因：** 在少量 query 上过拟合。
**解决：** 增大 eval set、提高 holdout、参考历史"不要重复的尝试"换结构而非堆词。

### Error: 动态跑分需要外部 API key
**原因：** 误用了官方 `anthropic` SDK 路径。
**解决：** 改用宿主 subagent 判定（本 skill 的既定路径），无需任何外部 key。

---

## Dependencies

- `python3`（仅标准库；脚本零第三方依赖）
- 宿主提供的 subagent / task 能力（用于动态触发判定）
- **无** `anthropic` SDK / `claude` CLI / 浏览器依赖
