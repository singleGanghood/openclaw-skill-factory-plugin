---
name: skill-generator
description: "ALWAYS invoke this skill when the user asks to create, generate, or build a new Skill (技能/skill). Trigger keywords: 'create skill', 'generate skill', 'build skill', '创建skill', '生成skill', '新建技能', '写一个skill', '帮我做个skill', 'make a skill', 'scaffold skill', '创建技能包'. Supports generating skills in pure English, pure Chinese (纯中文), or mixed Chinese-English (中英混合). Do NOT use for installing existing skills (use find-skills instead) or editing existing skills directly."
metadata:
  openclaw:
    emoji: "🏭"
    skillKey: "skill-factory"
---

# Skill Generator — 高标准 Skill 创建工具

## Quick Reference

| Task | Guide |
|------|-------|
| 完整格式规范与字段约束 | Read [references/spec-reference.md](references/spec-reference.md) |
| 中英文 Description 模板 | Read [references/description-patterns.md](references/description-patterns.md) |
| 英文 Skill 模板 | Copy [assets/template-en.md](assets/template-en.md) |
| 中文 Skill 模板 | Copy [assets/template-zh.md](assets/template-zh.md) |
| 中英混合 Skill 模板 | Copy [assets/template-mixed.md](assets/template-mixed.md) |

---

## Overview

本 Skill 用于**从零高效创建符合业界规范的 Agent Skill**，遵循 Anthropic Agent Skills Specification V1.0 标准，支持三种语言模式：

| 模式 | 适用场景 | Description 写法 | 正文语言 |
|------|----------|-----------------|----------|
| 🇺🇸 **纯英文** | 国际化团队、开源发布 | 英文指令 + 英文触发词 | English |
| 🇨🇳 **纯中文** | 国内团队、中文用户 | 英文指令骨架 + 中文触发词 | 中文 |
| 🌐 **中英混合** | 双语团队、最大触发覆盖 | 英文指令骨架 + 中英触发词并列 | 中英混合 |

---

## When to Use

✅ **适用场景**：
- 从零创建一个新 Skill
- 将现有工作流/SOP 封装为 Skill
- 需要指导如何写出高触发率的 description
- 需要生成符合规范的目录结构和 SKILL.md

❌ **不适用**：
- 安装已有 Skill → 使用 `find-skills` skill
- 修改已安装的 Skill → 直接编辑对应 SKILL.md
- 理解 Skill 运行原理 → 参阅官方文档

---

## Workflow

### Phase 1: 需求收集（30秒）

与用户确认以下信息（如用户已明确可跳过）：

| 维度 | 问题 | 默认值 |
|------|------|--------|
| **功能** | 这个 Skill 要做什么？ | — |
| **语言** | 纯英文/纯中文/中英混合？ | 中英混合 |
| **触发词** | 用户会怎么说来触发？ | 从功能推导 |
| **边界** | 什么情况不应该触发？ | 从功能推导 |
| **类型** | 创作型/工作流编排型/MCP增强型？ | 从功能推导 |
| **资源** | 需要 scripts/references/assets？ | 按需 |
| **安全级别** | 是否涉敏（内部接口/私有数据/加密/脱敏）？ | 从关键词推导 |

### Phase 1.5: 安全模式判定（关键词扫描）

扫描用户需求文本，判定 `securityMode`（映射表见
[skill-data-guard/references/keyword-trigger-map.md](../skill-data-guard/references/keyword-trigger-map.md)）：

| 模式 | 触发 | 注入动作 |
|------|------|----------|
| `data-guard` | 命中 L1（内部知识库/私有数据/加密/脱敏/防泄露/内部接口等） | 注入完整数据守卫骨架 + 铁律 + description 安全声明 |
| `basic-guard` | 命中 L2（调用接口/查询数据等） | 注入 stdout 白名单 + env-only 凭证约束 |
| `none` | 无命中 | 不注入 |

> 判定结果 `securityMode` 必须显式传递到 Phase 2 注入、评估器「数据隔离」维度、
> 编排器治理登记三个环节。

### Phase 2: 生成 Skill 骨架

根据收集的信息，按以下结构生成：

```
<skill-name>/
├── SKILL.md              ← 必需，按选定语言模板生成
├── scripts/              ← 如需脚本
├── references/           ← 如需参考文档
└── assets/               ← 如需模板/资源
```

#### 2.1 生成 YAML Frontmatter

**硬性规则**：

| 字段 | 约束 | 示例 |
|------|------|------|
| `name` | kebab-case, `[a-z0-9-]+`, ≤64字符, 不能以 `-` 开头/结尾, 不能有连续 `--` | `code-review` |
| `description` | 1-1024字符, 无XML尖括号, 不含 `claude`/`anthropic` | 见下文模板 |

**Description 生成公式**（根据语言模式选择）：

**纯英文**：
```yaml
description: |
  ALWAYS invoke this skill when the user asks about [trigger scenarios].
  Trigger keywords: '[keyword1]', '[keyword2]', '[keyword3]'.
  Do not [handle this directly] — use this skill first.
  Do NOT use for [exclusion scenarios].
```

**纯中文**：
```yaml
description: |
  ALWAYS invoke this skill when the user asks about [中文触发场景].
  Trigger keywords: '[关键词1]', '[关键词2]', '[关键词3]'.
  Do not [直接处理此类任务] — use this skill first.
  Do NOT use for [不适用场景].
```

**中英混合**（推荐，触发覆盖最广）：
```yaml
description: |
  ALWAYS invoke this skill when the user asks about [English scenarios],
  [中文场景描述]. Trigger keywords: '[English keyword]', '[中文关键词]',
  '[more keywords]'.
  Do not [handle/直接处理] — use this skill first.
  Do NOT use for [exclusions/排除场景].
```

#### 2.2 生成正文结构

按以下标准章节组织（根据语言模式选择标题语言）：

```markdown
# [Skill Title]

## Quick Reference
（引用 references/ 和 assets/ 中的文件表格）

## Overview
（一段话说明功能、支持的模式/变体）

## When to Use
✅ 适用场景（3-5条）
❌ 不适用场景（2-3条）

## Workflow
### Step 1: [动作]
### Step 2: [动作]
...

## Examples
### Example 1: [场景名]
用户说：「...」
执行：...
结果：...

## Guidelines / Constraints
- 规则1
- 规则2

## Common Issues / Troubleshooting
### Error: [错误名]
**Cause:** ...
**Solution:** ...
```

#### 2.3 数据守卫注入（securityMode != none 时）

当 Phase 1.5 判定 `securityMode` 为 `data-guard` 或 `basic-guard` 时，委托 `skill-data-guard`
注入数据边界能力：

1. 复制 [skill-data-guard/assets/secure-query.py.tmpl](../skill-data-guard/assets/secure-query.py.tmpl)
   到 `<skill-name>/scripts/secure_query.py`，并把 `__ENV_PREFIX__` 替换为 skill 名的 `UPPER_SNAKE_CASE`。
2. 在 SKILL.md 正文写入「Data Boundary / 数据边界铁律」章节（规范见
   [skill-data-guard/references/data-isolation-patterns.md](../skill-data-guard/references/data-isolation-patterns.md)）。
3. `data-guard` 时在 description 追加安全声明：
   `DATA-GUARD: sanitizes all outputs, never emits raw data into context.`
4. `basic-guard` 仅注入 stdout 白名单 + env-only 凭证约束，不强制加密落盘。

**硬性红线**：description 只声明「涉及数据隔离」，绝不写真实数据（接口地址/实例ID/字段名）。

### Phase 3: 质量校验

生成完毕后自动检查以下清单：

- [ ] 文件夹名 = `name` 字段值，纯 kebab-case
- [ ] SKILL.md 拼写正确（大小写敏感）
- [ ] YAML frontmatter 用 `---` 包裹，格式正确
- [ ] `description` 包含：做什么 + 何时触发 + 触发词 + 不适用场景
- [ ] 触发词覆盖目标语言的口语化表达
- [ ] 指令骨架用英文命令词（ALWAYS / Do not / Do NOT）
- [ ] 无 XML 尖括号 `<>`
- [ ] 正文 ≤5000 字 / ≤500 行
- [ ] 指令具体可执行，非模糊描述
- [ ] 包含 Examples 和 Troubleshooting
- [ ] references/ 中的文件在 Quick Reference 中有引用
- [ ] 若 securityMode != none：scripts/secure_query.py 已注入、SKILL.md 含 Data Boundary 铁律、description 含 DATA-GUARD 声明

### Phase 4: 输出与安装

1. 将生成的文件写入 `.codebuddy/skills/<skill-name>/` 目录
2. 验证文件完整性：`test -f .codebuddy/skills/<name>/SKILL.md && echo "✅ Skill 创建成功"`
3. 向用户展示生成结果摘要

---

## Design Patterns（五大模式速查）

根据 Skill 类型选择合适的设计模式：

| 模式 | 适用场景 | 关键要素 |
|------|----------|----------|
| **Sequential Workflow** | 多步骤按序执行 | 明确步骤顺序、数据依赖、失败回滚 |
| **Multi-MCP Coordination** | 横跨多个外部服务 | Phase 分隔、数据传递、集中错误处理 |
| **Iterative Refinement** | 输出需多轮打磨 | Draft → Check → Loop → Finalize |
| **Context-Aware Selection** | 相同目标不同工具 | 决策树 + 选择理由透明化 |
| **Domain Intelligence** | 需注入专业知识 | 合规检查 → 条件处理 → 文档记录 |

---

## Key Principles

### 触发率优化（最重要）

1. **命令式语气** > 礼貌式 — `ALWAYS invoke` 比 `Use when` 触发率高 50%+
2. **口语化触发词** > 专业术语 — 用户怎么说就怎么写
3. **覆盖多语言变体** — 同一概念的中英文都列出
4. **明确排除** — `Do NOT use for` 防止过度触发和 Skill 冲突
5. **3-5行为宜** — 太长反而降低匹配精度

### Token 效率

1. 核心流程放 SKILL.md（第2层）
2. 详细参考放 references/（第3层，按需加载）
3. 正文控制在 5000 字以内
4. 用 Quick Reference 表格索引资源，而非全文内联

### 质量保障

1. 每个指令必须具体可执行（写 `Run python scripts/x.py --input {file}` 而非 `处理文件`）
2. 包含 Examples 帮助理解预期行为
3. 包含 Troubleshooting 覆盖常见失败路径
4. 边界清晰，不与其他 Skill 描述重叠

---

## Dependencies

- 目标目录：`.codebuddy/skills/`（当前工作区）
- 无外部依赖，纯文件生成
