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
| **★ 一键全自动闭环**（split→判定→聚合→改写→按test选最优） | Run [scripts/run_eval_loop.py](scripts/run_eval_loop.py) |
| **★ 生成可视化 HTML 报告**（零依赖单文件） | Run [scripts/generate_report.py](scripts/generate_report.py) |
| **★ 触发判定/改写的进程协议**（host-cmd/replay/mock，可插拔可回放） | Run [scripts/grader_adapter.py](scripts/grader_adapter.py) · Read [references/eval-harness-protocol.md](references/eval-harness-protocol.md) |
| 生成触发 eval set（正例/反例） | Run [scripts/gen_eval_set.py](scripts/gen_eval_set.py) 生成骨架，再人工/subagent 补全 |
| 静态触发力分析（快路径，0 模型调用） | Run [scripts/static_trigger_score.py](scripts/static_trigger_score.py) |
| train/test 分层分割（防过拟合） | Run [scripts/split_eval.py](scripts/split_eval.py) |
| 动态跑分聚合（precision/recall/accuracy） | Run [scripts/aggregate_eval.py](scripts/aggregate_eval.py) |
| description 自动优化的判分/停止规则 | Read [references/eval-loop.md](references/eval-loop.md) |
| TDD golden case 写法 | Read [references/tdd-golden-cases.md](references/tdd-golden-cases.md) |
| 判分器（grader）评判准则 | Read [references/grader-rubric.md](references/grader-rubric.md) |
| 对标官方 skill-creator 的差异与反超点 | Read [references/vs-skill-creator.md](references/vs-skill-creator.md) |

> **一键跑法（推荐）**：通过 `run_eval_loop.py` 一条命令跑完动态优化闭环，再用 `generate_report.py`
> 出可视化报告。判定与改写通过 [eval-harness-protocol.md](references/eval-harness-protocol.md) 的
> **进程协议**委托给宿主命令（生产）/ 回放文件（CI）/ 内置 mock（自测）——**全程零第三方 SDK**。
>
> ```bash
> # 生产：宿主命令做判定与改写，全自动
> python3 scripts/run_eval_loop.py --skill <skill-dir>/SKILL.md --eval-set eval_set.json \
>   --distractors distractors.json \
>   --grader-backend host-cmd  --grader-cmd  "openclaw subagent grade" \
>   --rewriter-backend host-cmd --rewriter-cmd "openclaw subagent rewrite-desc" \
>   --out eval_results.json
> python3 scripts/generate_report.py eval_results.json -o eval_report.html
>
> # 自测/CI：mock 判定跑通闭环（不改写）
> python3 scripts/run_eval_loop.py --skill <skill-dir>/SKILL.md --eval-set eval_set.json \
>   --grader-backend mock --rewriter-backend none --out eval_results.json
> ```

---

## Overview：两段式 eval（快路径 → 慢路径）

```
候选 SKILL.md
   │
   ├─(1) 快路径 static_trigger_score.py ── 0 模型调用，毫秒级
   │        └─ score < 阈值 ? → 直接产出优化指令回喂 generator（不起模型，秒级闭环）
   │
   └─(2) 通过快路径 → 慢路径动态跑分（run_eval_loop.py 一键编排）
            ├─ gen_eval_set.py    生成正例(should_trigger)+反例(should NOT)骨架
            ├─ split_eval.py      按 should_trigger 分层切 train/test（默认 holdout=0.4）
            ├─ grader_adapter     进程协议判定 train+test：每 query 跑 N 次（host-cmd/replay/mock）
            ├─ aggregate_eval.py  算 precision/recall/accuracy，标 PASS/FAIL
            ├─ rewriter（host-cmd）用 failed/false triggers（隐藏 test 分）自动改写 description → 循环
            │                     └─ 按 TEST 集选最优（防过拟合）
            └─ generate_report.py 产出单文件 HTML 可视化报告（离线可开）
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

### Phase 3 — 动态跑分（全自动闭环，零外部 SDK）★已升级为一键可跑

**推荐：一条命令跑完 Phase 2–4 的全自动闭环**（split→判定→聚合→改写→按 test 选最优）：

```bash
python3 scripts/run_eval_loop.py \
  --skill <skill-dir>/SKILL.md --eval-set eval_set.json --distractors distractors.json \
  --grader-backend host-cmd  --grader-cmd  "<宿主判定命令>" \
  --rewriter-backend host-cmd --rewriter-cmd "<宿主改写命令>" \
  --holdout 0.4 --runs-per-query 3 --trigger-threshold 0.5 --target 0.8 --max-iterations 5 \
  --out eval_results.json
```

判定与改写通过 [references/eval-harness-protocol.md](references/eval-harness-protocol.md) 定义的
**进程协议**委托出去，`run_eval_loop.py` 只负责编排口径（与官方 `run_loop.py` 对齐）：

- **判定后端**：`host-cmd`（生产，委托宿主 subagent，stdin/stdout JSON 协议）/ `replay`（CI 确定性复现）/ `mock`（自测）。
- **改写后端**：`host-cmd`（生产，宿主 subagent 改写，blinded 不给 test 分）/ `none`（只测不改）。
- 每 query 重复 `runs_per_query`（默认 3）次统计触发率；判定纪律见
  [references/grader-rubric.md](references/grader-rubric.md)。

> **仍然零外部 SDK**：`run_eval_loop.py` 与 `grader_adapter.py` 只用标准库，通过**子进程**与
> 宿主命令通信；**不要** import `anthropic` / 调 `claude -p`。这样任何宿主接上自己的
> grader/rewriter 命令即变为生产级全自动闭环，无宿主命令时用 `mock` 也能跑通验证。

（如需手动分步，仍可用 `split_eval.py` + `aggregate_eval.py` 单独调用。）

```bash
# 分步聚合（可选，run_eval_loop 内部已自动完成）
python3 scripts/aggregate_eval.py raw_runs.json --trigger-threshold 0.5 > eval_results.json
```

输出：每 query 的 `triggers/runs`、`pass`，以及总体 `precision / recall / accuracy`。

### Phase 4 — description 自动优化闭环（已由 run_eval_loop.py 自动执行）

`run_eval_loop.py` 内部按 [references/eval-loop.md](references/eval-loop.md) 与
[references/eval-harness-protocol.md](references/eval-harness-protocol.md) 自动完成：
- 若 train 有 FAIL：收集 `failed_triggers`（该触发没触发）+ `false_triggers`（不该触发却触发），
  **隐藏 test 分数**（blinded），连同"历史尝试（不要重复）"一起，通过 rewriter 进程协议
  让宿主 subagent 改写 description（≤ 100–200 词，硬上限 1024 字符）。
- 改完自动重跑；**按 test 集分数选最优**（记在结果 JSON 的 `best`）。
- 停止条件：train 全过 **或** 达到 `max_iterations`（默认 5）**或** 改写器无新方案。

（`--rewriter-backend none` 时跳过改写，仅做一轮基准测量。）

### Phase 5 — 产出判定 + 可视化报告

`run_eval_loop.py` 产出 `eval_results.json`（含每轮 train/test 分、`best`、`best_description`、`verdict`）。
再生成**单文件 HTML 可视化报告**供人工复核：

```bash
python3 scripts/generate_report.py eval_results.json -o eval_report.html
```

- **达标**（`verdict=PASS`，test 集 precision/recall 均 ≥ 目标，默认 ≥ 0.8）：把 `best_description`
  写回 SKILL.md，`eval_results.json` + `eval_report.html` 作为**动态验证证据**交回 orchestrator 登记。
- **未达标**（`verdict=FAIL`）：报告里失败项已置顶，交回 orchestrator，人工介入或换 generator 策略。

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

- `python3`（仅标准库；所有脚本零第三方依赖）
- 宿主提供的 grader / rewriter 命令（用于 `run_eval_loop.py` 的 `host-cmd` 后端做动态判定/改写）；
  无宿主命令时可用 `replay`（CI 复现）或 `mock`（自测）后端跑通闭环
- **无** `anthropic` SDK / `claude` CLI / 浏览器依赖（HTML 报告为离线单文件，双击即开）

### 脚本清单

| 脚本 | 作用 |
|------|------|
| `static_trigger_score.py` | 快路径：0 模型调用静态触发力打分 |
| `gen_eval_set.py` | 从 SKILL.md 生成正/反例骨架 |
| `split_eval.py` | train/test 分层切分 |
| `aggregate_eval.py` | 聚合成 precision/recall/accuracy |
| `grader_adapter.py` | 触发判定进程协议（host-cmd/replay/mock） |
| `run_eval_loop.py` | **一键全自动优化闭环编排** |
| `generate_report.py` | **零依赖单文件 HTML 可视化报告** |
