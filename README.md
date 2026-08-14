# 🏭 OpenClaw Skill Factory Plugin

[![npm version](https://img.shields.io/npm/v/openclaw-skill-factory-plugin)](https://www.npmjs.com/package/openclaw-skill-factory-plugin)
[![GitHub stars](https://img.shields.io/github/stars/singleGanghood/openclaw-skill-factory-plugin)](https://github.com/singleGanghood/openclaw-skill-factory-plugin)
[![validate](https://github.com/singleGanghood/openclaw-skill-factory-plugin/actions/workflows/validate.yml/badge.svg)](https://github.com/singleGanghood/openclaw-skill-factory-plugin/actions/workflows/validate.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**A skills-only [OpenClaw](https://github.com/openclaw) plugin** that turns the "one-off skill helpers" into a governed, **eval-driven, end-to-end skill production line** — with a static fast-path for speed, a TDD/benchmark engine for triggering quality, and optional screenshot input for authoring skills.

> 把 `skill-generator` / `skill-assessor` / `skill-splitter` 叠加 **TDD/eval 动态跑分引擎** 与"看屏截图输入"，封装成一个可直接开源、可通过 `openclaw plugins` 命令管理的插件。
>
> 🎯 **对标 Anthropic 官方 `skill-creator` 并反超**：能力全面对齐（自动 eval / TDD / description 自动优化 / 防过拟合 train-test 分割），并在**零外部依赖、创建速度（静态快路径短路）、幂等安装（内容寻址四态收敛）、OpenClaw 生态注册、多模态需求输入、治理**六个维度更强。逐条对比见 [`skills/skill-factory-eval/references/vs-skill-creator.md`](skills/skill-factory-eval/references/vs-skill-creator.md)。

---

## ✨ What's inside

This is a **skills-only** plugin (no channel, no TypeScript runtime). It bundles **6 skills**:

| Skill | 作用 | 门禁 (metadata.openclaw) |
|-------|------|--------------------------|
| `skill-generator` 🏭 | 把自然语言需求转成标准 Skill 候选，补齐触发边界、输入输出、依赖、权限与 eval | 无外部依赖 |
| `skill-assessor` 📊 | 静态 7 维评估（结构/frontmatter/正文/token 效率/生态兼容等），并衔接动态跑分 | `requires.bins: [bash]` |
| `skill-splitter` 🪓 | 识别大 Skill 的职责/依赖/数据契约，生成可审阅的子 Skill 与编排器提案（四种模式 + AST 分析） | `requires.bins: [python3]` |
| `skill-factory-eval` 🎯 | **TDD/eval 引擎**：快路径静态触发力分析（0 模型调用）→ train/test 分层跑分（precision/recall）→ description 自动优化闭环。对标并反超官方 skill-creator | `requires.bins: [python3]` |
| `skill-factory-screenshot` 📸 | 稳定实现"截图作为造技能输入"，桥接内置 `screen_snapshot` 与 `peekaboo` 两条后端 | 后端各自门控（见下） |
| `skill-factory-orchestrator` 🏗️ | 薄编排器：把上述能力串成需求→暂存→**快路径预检**→静态评估→**TDD 动态跑分/优化**→授权**幂等安装**→运行验证→新会话测试→**幂等治理登记**的**九步闭环**（`scripts/install_skill.py` 内容寻址四态收敛） | 无外部依赖 |

### 与龙虾（OpenClaw）截图能力搭配

`skill-factory-screenshot` 不自己造截图，而是稳定桥接 OpenClaw 现有的两条官方后端：

- **后端 A（推荐，跨端）**：内置 `screen_snapshot` / `screen_record` agent tool，经 Gateway `node.invoke` 调配对节点（iOS/Android/macOS companion），返回图交给带 vision 的模型。高风险命令受 `phone-control` 插件 arm/disarm 授权门控。
- **后端 B（macOS 本机）**：`peekaboo` skill（`brew install steipete/tap/peekaboo`），复用 App bridge.sock 的 Screen Recording / Accessibility 授权。

---

## 🎯 vs. Anthropic `skill-creator`（对标 + 反超）

基于对官方 `skill-creator`（含 V3 的 `run_loop.py` / `improve_description.py` / `grader.md`）源码的逐行核对：

| 维度 | 官方 skill-creator | 本插件 | 结论 |
|------|--------------------|--------|------|
| 自动 eval / benchmark | ✅ `run_loop.py` | ✅ `run_eval_loop.py` **一键全自动闭环**（split→判定→聚合→改写→按test选最优） | **补齐** |
| TDD 测试驱动 | ✅ | ✅ `gen_eval_set.py` + golden cases（先红后绿） | **补齐** |
| description 自动优化 | ✅ V3 核心 | ✅ eval-loop：train 优化 / test 选优 / blinded history | **补齐** |
| 防过拟合 train/test 分割 | ✅ | ✅ `split_eval.py` 分层切分 | 持平 |
| precision/recall/accuracy | ✅ | ✅ `aggregate_eval.py`（口径对齐） | 持平 |
| **eval 可视化报告** | ✅ eval-viewer（HTML，需脚本+浏览器） | ✅ `generate_report.py` **零依赖单文件 HTML，离线双击即开** | **补齐并更轻** |
| **判定/改写执行体** | ❌ 硬编码 `anthropic` SDK + `claude -p` | ✅ **可插拔进程协议**：host-cmd（宿主）/ replay（CI 回放）/ mock（自测） | **反超** |
| **外部依赖** | ❌ 硬依赖 `anthropic` SDK + `claude -p` + `webbrowser` | ✅ **纯标准库 + 宿主 subagent，零 SDK/CLI/API key** | **反超** |
| **创建速度** | ⚠️ 逢改必真实跑模型 | ✅ **静态快路径 0 模型调用短路，~80% 弱候选秒级拦截** | **反超** |
| **CI 可复现（回放）** | ❌ 每次真起模型 | ✅ `replay` 后端离线确定性复现 eval | **反超** |
| **幂等安装** | ❌ 手动拷贝，重复安装产生漂移 | ✅ `install_skill.py` **内容寻址四态收敛**（install/noop/conflict/upgrade）+ 原子转正 + 查重登记，CI 反复跑结果稳定 | **反超** |
| **生态注册** | ❌ 无 | ✅ `metadata.openclaw.skillKey` + 门控 + 治理注册表 | **反超** |
| **多模态需求输入** | ⚠️ 纯文本 interview | ✅ 截图 → 需求草案 | **反超** |
| 大 Skill 拆分 | ✅ | ✅ 四种模式 + AST 分析 | 更专业 |

> **同标准、更快、更省、更可移植、且带生态治理**。判分口径（`trigger_threshold=0.5`、`runs_per_query=3`、`holdout=0.4`、`max_iterations=5`、按 test 集选最优）**刻意对齐官方**，不靠降低标准取胜。详见 [`vs-skill-creator.md`](skills/skill-factory-eval/references/vs-skill-creator.md)。

---


本插件在设计上严格遵守以下约束（详见各 skill 的 `references/`）：

1. **依赖门控**：`skill-splitter` 声明 `requires.bins: [python3]`；截图后端 B 的 OS+bin 门控由 `peekaboo` skill 承载。运行时 eligibility 未满足则该 skill 自动不可用。
2. **不触碰核心**：全部为 Markdown 工作流 + 内置 tool/CLI，**无任何 TS 运行时代码**，不 import OpenClaw 核心 `src/**`，天然满足扩展导入边界。
3. **截图授权门控**：高风险屏幕命令必须先经 `phone-control` arm（推荐带 `--ttl` 自动过期）+ macOS TCC 授权，用完 disarm，禁止未授权静默截图。
4. **两个事实源分离**：per-agent **eligible** 清单决定"现在能不能用"；**治理注册表**（`registry.json`）只记录"哪个版本通过过什么验证"。注册表不能替代运行时；登记步骤不修改 eligible。**幂等安装**（`install_skill.py`）只作用于**磁盘 + 注册表**，同样绝不触碰 eligible / per-agent skills。

---

## 📦 Install & manage

### Requirements
- Node.js `>= 18`（npm 安装与本地校验用）
- `python3`（`skill-splitter` / `skill-factory-eval` / 幂等安装 `install_skill.py` 用，标准库即可）
- `peekaboo`（可选，仅 macOS 本机截图后端用）

### Install via npm（当前推荐）

> **注**：本插件目前以**独立 npm 包**形式发布，尚未集成到 OpenClaw 的插件市场。
> 在 OpenClaw 官方支持通过 `openclaw plugins install <npm-package>` 安装前，
> 先用 npm 方式安装到本地，再把 `skills/` 目录挂载给 OpenClaw 使用（见下）。

```bash
# 全局安装（推荐，方便 CLI / 各项目复用）
npm install -g openclaw-skill-factory-plugin

# 或安装到当前项目
npm install openclaw-skill-factory-plugin

# 或直接拉到本地目录（开发/内网/离线）
git clone https://github.com/singleGanghood/openclaw-skill-factory-plugin.git
```

### 让 OpenClaw 使用本插件的 skills

安装后，把包内的 `skills/` 目录指向 OpenClaw 的 skill 加载路径（二选一）：

```bash
# 方式 A：全局安装后，把 skills 目录软链到 OpenClaw 配置的 skills 目录
ln -s "$(npm root -g)/openclaw-skill-factory-plugin/skills" <your-openclaw-skills-dir>/skill-factory

# 方式 B：直接在项目内引用（通过相对路径指向 node_modules 中的 skills）
# 在 OpenClaw 配置中把 skills 路径指向：
#   <project>/node_modules/openclaw-skill-factory-plugin/skills
```

### Manage

```bash
npm ls -g openclaw-skill-factory-plugin           # 查看已安装版本
npm update -g openclaw-skill-factory-plugin       # 更新到最新版
npm uninstall -g openclaw-skill-factory-plugin    # 卸载
```

> **未来**：当 OpenClaw 支持插件市场后，将可直接通过
> `openclaw plugins install openclaw-skill-factory-plugin` 一行安装（本包结构已按
> `openclaw.plugin.json` + `package.json#openclaw` 规范预置，届时无需改动）。

### Configure（可选）

```bash
openclaw config set plugins.openclaw-skill-factory-plugin.assessorPassScore 85
openclaw config set plugins.openclaw-skill-factory-plugin.stagingDir ".skill-factory/staging"
openclaw gateway restart
```

### Per-agent 授权（eligible 第一层）

```bash
# 只允许某个 agent 使用工厂类 skill
openclaw config set agents.main.skills '["skill-factory-orchestrator","skill-generator","skill-assessor","skill-splitter","skill-factory-screenshot"]'
```

---

## 🧭 Usage

一站式造技能（推荐入口）：

> 「这是我们内部工具的截图，帮我照着造一个 skill，走完整流程」

编排器会自动：
1. 委托 `skill-factory-screenshot` 截图并反推需求
2. 委托 `skill-generator` 在**暂存区**生成候选（不影响线上）
3. **快路径静态预检**（`skill-factory-eval` Phase 0，0 模型调用）：低分秒级回喂重生成
4. 委托 `skill-assessor` 做静态 7 维评估，不达标回喂
5. **TDD 动态跑分 + description 自动优化**（`skill-factory-eval`）：precision/recall 达标才算触发合格
6. 用户**明确同意**后**幂等安装**（`install_skill.py`：内容寻址四态收敛 install/noop/conflict/upgrade，原子转正 + 并发锁，`--dry-run` 可先预演）
7. 判定 `info + eligible` 运行验证
8. 新会话正/反例触发测试
9. **幂等治理登记**（`(name, version, contentHash)` 幂等键查重，version / hash / assessorScore / precision / recall / rollbackRef）

单步也可直接触发对应 skill（如「评估 xxx skill」「给 xxx skill 跑触发测试」「拆解 xxx skill」）。

---

## 🗂️ Layout

```
openclaw-skill-factory-plugin/
├── openclaw.plugin.json          # 插件 manifest（id + configSchema + skills）
├── package.json                  # npm 分发元数据（openclaw.skills / install）
├── scripts/validate.mjs          # 零依赖本地校验（CI 可用）
├── LICENSE                       # MIT
└── skills/
    ├── skill-generator/
    ├── skill-assessor/               # 静态 7 维评估（+ 衔接动态跑分）
    ├── skill-splitter/
    ├── skill-factory-eval/           # TDD/eval 引擎（快路径 + 一键全自动闭环 + 可视化）
    │   ├── scripts/                  #   static_trigger_score / gen_eval_set / split_eval / aggregate_eval
    │   │                             #   + run_eval_loop（一键闭环） / grader_adapter（判定协议） / generate_report（HTML）
    │   └── references/               #   eval-loop / eval-harness-protocol / tdd-golden-cases / grader-rubric / vs-skill-creator
    ├── skill-factory-screenshot/     # 截图输入桥（含授权清单）
    └── skill-factory-orchestrator/   # 九步闭环编排器（含治理注册表规范 + 幂等安装）
        └── scripts/install_skill.py  # 内容寻址幂等安装（install/noop/conflict/upgrade + 原子转正 + 查重登记）
```

## 🔧 Develop

```bash
npm run validate     # 校验 manifest 与所有 SKILL.md frontmatter
```

## 📄 License

MIT
