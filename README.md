# 🏭 OpenClaw Skill Factory Plugin

[![npm version](https://img.shields.io/npm/v/openclaw-skill-factory-plugin)](https://www.npmjs.com/package/openclaw-skill-factory-plugin)
[![GitHub stars](https://img.shields.io/github/stars/singleGanghood/openclaw-skill-factory-plugin)](https://github.com/singleGanghood/openclaw-skill-factory-plugin)
[![validate](https://github.com/singleGanghood/openclaw-skill-factory-plugin/actions/workflows/validate.yml/badge.svg)](https://github.com/singleGanghood/openclaw-skill-factory-plugin/actions/workflows/validate.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**A skills-only [OpenClaw](https://github.com/openclaw) plugin** that turns the "one-off skill helpers" into a governed, end-to-end **skill production line** — and can optionally use OpenClaw's screenshot capability as input for authoring skills.

> 把 `skill-generator` / `skill-assessor` / `skill-splitter` 三项通用能力，叠加"看屏截图输入"，封装成一个可直接开源、可通过 `openclaw plugins` 命令管理的插件。

---

## ✨ What's inside

This is a **skills-only** plugin (no channel, no TypeScript runtime). It bundles **5 skills**:

| Skill | 作用 | 门禁 (metadata.openclaw) |
|-------|------|--------------------------|
| `skill-generator` 🏭 | 把自然语言需求转成标准 Skill 候选，补齐触发边界、输入输出、依赖、权限与 eval | 无外部依赖 |
| `skill-assessor` 📊 | 7 维度分层检查（结构/安全/脚本/依赖/测试/运行时安装/eligible/真实触发） | `requires.bins: [bash]` |
| `skill-splitter` 🪓 | 识别大 Skill 的职责/依赖/数据契约，生成可审阅的子 Skill 与编排器提案 | `requires.bins: [python3]` |
| `skill-factory-screenshot` 📸 | 稳定实现"截图作为造技能输入"，桥接内置 `screen_snapshot` 与 `peekaboo` 两条后端 | 后端各自门控（见下） |
| `skill-factory-orchestrator` 🏗️ | 薄编排器：把上述能力串成需求→暂存创建→质量评估→授权安装→运行验证→新会话测试→治理登记的七步闭环 | 无外部依赖 |

### 与龙虾（OpenClaw）截图能力搭配

`skill-factory-screenshot` 不自己造截图，而是稳定桥接 OpenClaw 现有的两条官方后端：

- **后端 A（推荐，跨端）**：内置 `screen_snapshot` / `screen_record` agent tool，经 Gateway `node.invoke` 调配对节点（iOS/Android/macOS companion），返回图交给带 vision 的模型。高风险命令受 `phone-control` 插件 arm/disarm 授权门控。
- **后端 B（macOS 本机）**：`peekaboo` skill（`brew install steipete/tap/peekaboo`），复用 App bridge.sock 的 Screen Recording / Accessibility 授权。

---

## 🚦 Design constraints（严格遵守的边界）

本插件在设计上严格遵守以下约束（详见各 skill 的 `references/`）：

1. **依赖门控**：`skill-splitter` 声明 `requires.bins: [python3]`；截图后端 B 的 OS+bin 门控由 `peekaboo` skill 承载。运行时 eligibility 未满足则该 skill 自动不可用。
2. **不触碰核心**：全部为 Markdown 工作流 + 内置 tool/CLI，**无任何 TS 运行时代码**，不 import OpenClaw 核心 `src/**`，天然满足扩展导入边界。
3. **截图授权门控**：高风险屏幕命令必须先经 `phone-control` arm（推荐带 `--ttl` 自动过期）+ macOS TCC 授权，用完 disarm，禁止未授权静默截图。
4. **两个事实源分离**：per-agent **eligible** 清单决定"现在能不能用"；**治理注册表**（`registry.json`）只记录"哪个版本通过过什么验证"。注册表不能替代运行时；登记步骤不修改 eligible。

---

## 📦 Install & manage (via `openclaw plugins`)

### Requirements
- OpenClaw `>= 2026.3.28`
- Node.js（运行本地校验脚本用，可选）
- `python3`（仅 `skill-splitter` 用）
- `peekaboo`（可选，仅 macOS 本机截图后端用）

### Install

```bash
# 从 npm 安装（发布后）
openclaw plugins install openclaw-skill-factory-plugin

# 或从本地目录安装（开发/内网）
openclaw plugins install /path/to/openclaw-skill-factory-plugin
```

### Manage

```bash
openclaw plugins list                              # 查看已安装插件
openclaw plugins update openclaw-skill-factory-plugin
openclaw plugins remove openclaw-skill-factory-plugin
```

### Configure（可选）

```bash
openclaw config set plugins.openclaw-skill-factory-plugin.assessorPassScore 85
openclaw config set plugins.openclaw-skill-factory-plugin.stagingDir ".openclaw/skills-staging"
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
3. 委托 `skill-assessor` 打分，不达标回喂重生成
4. 用户**明确同意**后安装
5. 判定 `info + eligible` 运行验证
6. 新会话正/反例触发测试
7. 治理登记（version / hash / score / rollbackRef）

单步也可直接触发对应 skill（如「评估 xxx skill」「拆解 xxx skill」）。

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
    ├── skill-assessor/
    ├── skill-splitter/
    ├── skill-factory-screenshot/     # 截图输入桥（含授权清单）
    └── skill-factory-orchestrator/   # 七步闭环编排器（含治理注册表规范）
```

## 🔧 Develop

```bash
npm run validate     # 校验 manifest 与所有 SKILL.md frontmatter
```

## 📄 License

MIT
