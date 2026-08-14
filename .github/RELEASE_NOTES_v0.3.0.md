# 🏭 openclaw-skill-factory-plugin v0.3.0

An eval-driven **Skill Factory** for OpenClaw: produce, assess, benchmark, optimize, split and govern Agent Skills — aligning with Anthropic's `skill-creator` and outperforming it on **dependency-freeness, speed and ecosystem governance**.

> npm: `openclaw-skill-factory-plugin@0.3.0` — 现在通过 **npm** 安装（插件尚未进入 OpenClaw 市场，见 README）。

---

## ✨ What's new in v0.3.0

### 🎯 Runnable eval harness（一键全自动闭环）
Previously the eval-driven engine was a set of step scripts; now it is a **fully runnable closed-loop driver**:

- **`run_eval_loop.py`** — end-to-end loop: fast-path → gen eval set → train/test split → dynamic benchmark → auto-optimize description → **pick best by test set** (anti-overfitting), with `--max-iterations` / `--trigger-threshold` / `--holdout` knobs.
- **`grader_adapter.py`** — **pluggable process protocol** for trigger judging: `host` (host subagent, zero external SDK) / `replay` (offline deterministic CI replay) / `mock` (self-test). No `anthropic` SDK, no `claude -p`, no browser.
- **`generate_report.py`** — zero-dependency **single-file HTML eval report** (offline, double-click to open), replacing the heavyweight viewer.
- **`eval-harness-protocol.md`** — I/O protocol doc for the harness.

### 🏛️ Idempotent governance install（治理幂等安装）
- **`install_skill.py`** — content-addressed, idempotent promote+register with **four-state convergence**: `install / noop / conflict / upgrade`.
  - Idempotency key = `(name, version, contentHash)`; atomic `os.replace`; file-locked against TOCTOU; `--dry-run` for CI.
  - **CONFLICT** (same version, drifted content / downgrade) is an *error*, not a new record — bump version or `--force`.
- `governance-registry.md` — idempotency rules, CONFLICT policy, upgrade auto-fills `rollbackRef`.
- `validate.mjs` — now requires `install_skill.py` in CI checks.

### 📦 npm-first install
- README installation switched to **npm** (`npm install -g openclaw-skill-factory-plugin`), with symlink guidance to mount `skills/` into OpenClaw until the plugin market supports it.

---

## 🎯 vs. Anthropic `skill-creator` — 亮点对比

| 维度 | 官方 skill-creator | 本插件 | 结论 |
|------|--------------------|--------|------|
| 自动 eval / benchmark | ✅ `run_loop.py` | ✅ `run_eval_loop.py` **一键全自动闭环** | **补齐** |
| TDD 测试驱动 | ✅ | ✅ `gen_eval_set.py` + golden cases（先红后绿） | **补齐** |
| description 自动优化 | ✅ V3 核心 | ✅ train 优化 / test 选优 / blinded history | **补齐** |
| eval 可视化报告 | ✅ eval-viewer（HTML+浏览器） | ✅ `generate_report.py` **零依赖单文件 HTML** | **补齐并更轻** |
| 判定/改写执行体 | ❌ 硬编码 `anthropic` SDK + `claude -p` | ✅ **可插拔协议**：host / replay / mock | **反超** |
| 外部依赖 | ❌ `anthropic` + `claude -p` + `webbrowser` | ✅ **纯标准库 + 宿主 subagent，零 SDK/CLI/API key** | **反超** |
| 创建速度 | ⚠️ 逢改必真实跑模型 | ✅ **静态快路径 0 模型调用短路，~80% 弱候选秒级拦截** | **反超** |
| CI 可复现 | ❌ 每次真起模型 | ✅ `replay` 后端离线确定性复现 | **反超** |
| 生态注册 | ❌ 无 | ✅ `metadata.openclaw.skillKey` + 门控 + 治理注册表 | **反超** |
| 多模态需求输入 | ⚠️ 纯文本 interview | ✅ 截图 → 需求草案 | **反超** |
| 大 Skill 拆分 | ✅ | ✅ 四种模式 + AST 分析 | 更专业 |

> **同标准、更快、更省、更可移植、且带生态治理** — 判分口径（`trigger_threshold=0.5`、`runs_per_query=3`、`holdout=0.4`、`max_iterations=5`、按 test 集选最优）**刻意对齐官方**，不靠降低标准取胜。

---

## 📦 Install

```bash
npm install -g openclaw-skill-factory-plugin
# 挂载 skills 到 OpenClaw（详见 README）
ln -s "$(npm root -g)/openclaw-skill-factory-plugin/skills" <your-openclaw-skills-dir>/skill-factory
```

完整文档：https://github.com/singleGanghood/openclaw-skill-factory-plugin#readme

## ✅ 校验

```bash
npm run validate   # manifest + 6 skills frontmatter + harness + install script 全校验
```
