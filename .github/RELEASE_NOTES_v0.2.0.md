# 🏭 openclaw-skill-factory-plugin v0.2.0

An eval-driven **Skill Factory** for OpenClaw — aligning with Anthropic's `skill-creator` and outperforming it on dependency-freeness, speed and ecosystem governance.

## ✨ What's new in v0.2.0

### 🎯 New: `skill-factory-eval` — TDD / eval-driven triggering engine
The gap that pure-static assessment cannot cover — **dynamic triggering quality** — is now a first-class skill:

- **Fast path (0 model calls)**: `static_trigger_score.py` statically scores a description's triggering power in milliseconds; weak candidates are intercepted and refed to the generator — **~80% never enter the expensive dynamic loop**.
- **Dynamic benchmark**: `gen_eval_set.py` (TDD golden cases, ≥3 positive + ≥3 negative) → `split_eval.py` (stratified train/test, anti-overfitting) → host-subagent judging → `aggregate_eval.py` (precision / recall / accuracy, alignment with official metrics).
- **Closed-loop description auto-optimization**: train-optimize / test-select-best / blinded history — mirrors official `run_loop.py` semantics, but with **zero external SDK** (no `anthropic`, no `claude -p`, no browser).
- **vs-skill-creator**: line-by-line comparison doc added.

### 🏗️ Orchestrator: 7-step → 9-step closed loop
Inserted **fast-path pre-check** (Step 03) and **TDD dynamic eval + auto-optimize** (Step 05) — the two official `skill-creator` strengths now fully covered, with governance registry extended to carry `evalPrecision` / `evalRecall` evidence.

### 📊 Assessor: static-vs-dynamic handoff
`skill-assessor` now explicitly hands off dynamic triggering to `skill-factory-eval`, closing the "missing dynamic trigger test" gap.

### 📦 Packaging
- `manifest` / `package.json` bumped to **0.2.0**; new `fastPathMinScore` and `evalPassTarget` config options.

## 🎯 vs. Anthropic `skill-creator` — highlights

| 维度 | 官方 | 本插件 | 结论 |
|------|------|--------|------|
| 自动 eval / TDD / description 自动优化 | ✅ | ✅ `skill-factory-eval`（对齐判分口径） | **补齐** |
| 外部依赖 | ❌ `anthropic`+`claude -p`+`webbrowser` | ✅ 纯标准库 + 宿主 subagent | **反超** |
| 创建速度 | ⚠️ 逢改必跑模型 | ✅ 静态快路径 0 模型调用短路 | **反超** |
| 生态注册 | ❌ | ✅ `metadata.openclaw.skillKey` + 治理注册表 | **反超** |
| 多模态输入 | ⚠️ 纯文本 | ✅ 截图 → 需求草案 | **反超** |

## ✅ 校验
`npm run validate` — manifest + 5 skills frontmatter 全校验通过。
