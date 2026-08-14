---
name: skill-factory-screenshot
description: |
  ALWAYS invoke this skill when the user asks to capture a screenshot / screen recording
  as INPUT for skill authoring, or wants the agent to "see" a UI / design mock / existing tool
  before generating or assessing a Skill.
  截图作为造技能的输入：看设计稿、看现有 UI、看报错界面来反推需求。
  Trigger keywords: 'screenshot', 'capture screen', 'screen snapshot', 'see the UI',
  '截图', '截屏', '屏幕截图', '看一下界面', '看设计稿', '录屏', 'screen record'.
  Do NOT use for general screenshotting unrelated to skill authoring — that is the raw
  `screen_snapshot` tool or `peekaboo` skill's job. Do NOT use to create/assess/split skills
  directly (use skill-generator / skill-assessor / skill-splitter).
metadata:
  openclaw:
    emoji: "📸"
    skillKey: "skill-factory"
---

# Skill Factory Screenshot Bridge — 造技能的"看屏"输入桥

在"用截图反推需求 → 生成/评估 Skill"的闭环中，本 skill 只做一件事：**以稳定、可授权、可回退的方式获取一张（或一段）屏幕画面，交给带 vision 的模型理解**，然后把理解结果作为 `skill-generator` / `skill-assessor` 的输入。

本 skill **不自己实现截图**，而是桥接 OpenClaw 现有的两条官方截图后端，并严格遵守其授权与门控边界。

## Quick Reference

| 任务 | 指引 |
|------|------|
| 两条后端的选择决策树 | Read [references/backend-decision.md](references/backend-decision.md) |
| 授权与门控检查清单（务必先过） | Read [references/authorization-checklist.md](references/authorization-checklist.md) |

---

## Overview

| 后端 | 实现 | 适用平台 | 门控 |
|------|------|----------|------|
| **A. 内置 `screen_snapshot` / `screen_record`** | OpenClaw 内置 `nodes` agent tool，经 Gateway `node.invoke` 调配对节点 | iOS / Android / macOS companion 节点 | `phone-control` 插件 arm/disarm 授权 + `node-command-policy` |
| **B. `peekaboo` skill** | macOS 本机 `peekaboo image/see`，复用 App bridge.sock 的 TCC 授权 | 仅 macOS | `os:["darwin"]` + `requires.bins:["peekaboo"]` |

> ⚠️ 本 skill 本身不声明 `requires.bins`：后端 A 是内置能力，后端 B 的 bin/OS 门控由 `peekaboo` skill 自己承载。这样做是为了让本 skill 在任何平台都可被"发现"，但真正执行截图时仍受后端各自的 eligibility 约束（见约束 1）。

---

## When to Use

✅ **适用**：
- 用户给了一张设计稿 / 现有工具界面 / 报错截图，希望据此造一个 Skill
- 造技能过程中需要 agent 实时"看"当前屏幕状态来补全需求边界
- 评估某个操作类 Skill 时，需要截图验证其真实交互效果

❌ **不适用**：
- 纯粹的截图需求（与造技能无关）→ 直接用 `screen_snapshot` tool 或 `peekaboo` skill
- 已有清晰文字需求，无需看图 → 直接进 `skill-generator`
- 需要连续 UI 自动化（点击/输入）→ 用 `peekaboo` skill

---

## Workflow

### Phase 0: 授权与门控前置检查（强制，对应第五点约束 3 与约束 1）

**在任何截图动作前**，按 [references/authorization-checklist.md](references/authorization-checklist.md) 逐项确认。禁止跳过。

1. **判定后端可用性（eligibility，只读，不修改）**：
   - 后端 B：确认当前 `os == darwin` 且 PATH 中存在 `peekaboo`；否则只能走后端 A 或提示用户安装。
   - 后端 A：确认存在已配对节点（`openclaw nodes list`）。
2. **确认授权（arm）**：后端 A 的 `screen.record` 等高风险命令受 `phone-control` 插件 arm/disarm 门控。执行前必须：
   ```bash
   # 由用户明确授权后，arm screen 能力组（带自动过期更安全）
   openclaw nodes arm --node <id> --group screen --ttl 10m
   ```
   截图完成后建议 `openclaw nodes disarm --node <id> --group screen`。
3. **TCC 授权（后端 B / macOS）**：确认 App 已获 Screen Recording + Accessibility 授权，并设置 bridge socket：
   ```bash
   export PEEKABOO_BRIDGE_SOCKET="${PEEKABOO_BRIDGE_SOCKET:-$HOME/Library/Application Support/OpenClaw/bridge.sock}"
   peekaboo bridge status --json   # hostKind 必须为 gui
   ```

> **约束 4（双事实源不能混）**：本 Phase 只做"运行时是否 eligible / 是否已 arm"的判定与请求，**绝不修改 per-agent skills 白名单，也不写治理注册表**。eligible 决定"现在能不能截"，治理登记只在编排器的收尾阶段记录"用哪个版本造过技能"，二者分开。

### Phase 1: 截图 / 录屏

**后端 A（推荐，跨端）**——直接调用内置 tool `screen_snapshot`：
- 参数：`node`（目标节点）、可选 `screenIndex` / `maxWidth` / `outPath`
- 返回 base64 图，若模型有 vision 能力则作为 image content 直接进上下文

**后端 B（macOS 本机）**：
```bash
peekaboo image --mode screen --screen-index 0 --retina --path /tmp/skillshot.png
# 或让 peekaboo 直接截图 + 分析
peekaboo see --mode screen --screen-index 0 --analyze "描述这个界面提供了哪些功能"
```

### Phase 2: 交给模型理解，产出"需求草稿"

把截图（image content）连同提问交给带 vision 的模型，产出结构化需求：
- 这个界面/工具做什么？核心功能点有哪些？
- 触发场景与边界？输入/输出是什么？
- 是否需要脚本/外部依赖？

**输出数据契约**（供编排器 / skill-generator 消费）：
```json
{
  "source": "screenshot",
  "backend": "nodes|peekaboo",
  "imagePath": "/tmp/skillshot.png",
  "requirementDraft": {
    "function": "...",
    "triggers": ["..."],
    "boundaries": ["..."],
    "io": { "input": "...", "output": "..." },
    "deps": ["..."]
  }
}
```

### Phase 3: 移交

将 `requirementDraft` 移交 `skill-generator`（生成）或 `skill-assessor`（对照界面评估已有 skill）。本 skill 到此结束，不越权去写 skill 文件。

---

## Examples

### 示例 1：看设计稿造技能

**用户说：**「这是我们内部工具的界面截图，帮我照着做一个能自动填单的 skill」

**执行：**
1. Phase 0：确认 macOS + peekaboo 可用并已授权；或走后端 A。
2. Phase 1：`peekaboo image --mode screen --path /tmp/shot.png`。
3. Phase 2：模型识别界面字段，产出 requirementDraft。
4. Phase 3：移交 `skill-generator` 生成 skill 骨架。

### 示例 2：跨端节点截图

**用户说：**「截一下我配对的这台手机的屏幕，我要照它造个操作 skill」

**执行：**
1. Phase 0：`openclaw nodes list` 找节点；`openclaw nodes arm --node phone-1 --group screen --ttl 10m`（用户授权后）。
2. Phase 1：调用 `screen_snapshot` tool，`node=phone-1`。
3. Phase 2/3：理解 + 移交。
4. 收尾：`openclaw nodes disarm --node phone-1 --group screen`。

---

## Guidelines / Constraints（严格对应可行性第五点）

- **约束 1（依赖门控）**：截图后端 B 的 `python3`?无关；其 OS+bin 门控由 `peekaboo` skill 承载，本 skill 不代为声明，避免"发现即报错"。真正执行前必须先过 eligibility 判定。
- **约束 2（不碰核心）**：本 skill 是纯 Markdown 工作流 + 调用内置 tool / CLI，**不包含任何 TypeScript 运行时代码**，因此不触碰 `src/**`，天然满足 `extension-import-boundaries` 约束。
- **约束 3（授权门控）**：高风险屏幕命令必须先经 `phone-control` arm（推荐带 `--ttl` 自动过期）+ macOS TCC 授权；用完 disarm。禁止在未授权时静默截图。
- **约束 4（双事实源分离）**：本 skill 只读判定 eligible、只请求 arm，**不改 per-agent skills 白名单、不写治理注册表**。

---

## Common Issues / Troubleshooting

### Error: peekaboo 截图失败 / 权限被拒
**原因：** 未设置 bridge socket 或缺 Screen Recording 授权。
**解决：** `peekaboo bridge status --json`（hostKind 须为 gui）→ `peekaboo permissions status --json` → 补授权后重试。

### Error: screen_snapshot 报节点不可用 / 未授权
**原因：** 节点未配对，或 `screen` 能力组未 arm。
**解决：** `openclaw nodes list` 确认节点在线；`openclaw nodes arm --node <id> --group screen` 后重试。

### Error: 当前平台不支持任何截图后端
**原因：** 非 macOS 且无配对节点。
**解决：** 提示用户配对一个节点（后端 A），或在 macOS 上安装 peekaboo（后端 B）。截图不是造技能的硬前提——无图时可退回纯文字需求走 `skill-generator`。

---

## Dependencies

- **后端 A**：OpenClaw 内置 `screen_snapshot` / `screen_record` tool（无需额外安装）；高风险命令依赖 `phone-control` 插件做授权门控。
- **后端 B**：`peekaboo` skill（`os: darwin`，`requires.bins: [peekaboo]`）。
- 本 skill 自身无第三方依赖，纯工作流桥接。
