# Skill 格式规范参考

> 基于 Anthropic Agent Skills Specification V1.0（2025年12月18日发布）

## 一、目录结构规范

```
skill-name/                ← kebab-case，不能有空格/下划线/大写
├── SKILL.md              ← 必需，大小写完全一致
├── scripts/              ← 可选：Python/Bash 等可执行脚本
├── references/           ← 可选：按需加载的参考文档
└── assets/               ← 可选：模板、字体、图标等静态资源
```

### 禁止事项

- ❌ 根目录放 README.md
- ❌ 参考文档放在根目录（必须放 `references/`）
- ❌ 模板/资源放在根目录（必须放 `assets/`）
- ❌ 脚本放在根目录（必须放 `scripts/`）

---

## 二、YAML Frontmatter 字段规格

| 字段 | 必填 | 类型 | 约束 | 说明 |
|------|------|------|------|------|
| `name` | ✅ | string | `[a-z0-9-]+`, ≤64字符, 不以 `-` 开头/结尾, 无连续 `--` | 唯一标识符，必须与文件夹名一致 |
| `description` | ✅ | string | 1-1024字符, 无XML尖括号 | 驱动触发机制的核心字段 |
| `license` | ❌ | string | - | 如 `MIT`, `Apache-2.0` |
| `allowed-tools` | ❌ | string | 实验性 | 预授权工具清单 |
| `compatibility` | ❌ | string | ≤500字符 | 环境依赖说明 |
| `metadata` | ❌ | map | key-value | 自定义属性（author, version, tags 等） |

### Name 命名规则

```yaml
# ✅ 合法
name: code-review
name: pdf-processing
name: ai-wiki

# ❌ 非法
name: Code-Review      # 大写
name: -code-review     # 以连字号开头
name: code--review     # 连续连字号
name: code_review      # 下划线
name: code review      # 空格
```

### 安全限制

- 禁止 `name` 包含 `claude` 或 `anthropic`（保留字）
- 禁止 `description` 中使用 XML 尖括号 `<>`

---

## 三、三层渐进式加载系统

| 层级 | 内容 | 大小建议 | 加载时机 |
|------|------|----------|----------|
| **第1层** | YAML frontmatter | ~100词 | 始终在系统提示中，用于发现和匹配 |
| **第2层** | SKILL.md 正文 | <5000词 / <500行 | Skill 被判定相关时加载 |
| **第3层** | bundled resources | 不限 | 正文中引用到时按需加载 |

> 核心原则：**最小化 token 消耗，最大化专业能力**

---

## 四、Description 编写规范

### 触发机制原理

Claude 决定是否触发 Skill **只看 `name` + `description`**，不读正文。
触发是"概率判断"而非"规则匹配"，模型天生倾向"自己处理"而非调用 Skill。

### 最佳写法：指令式模板

```
ALWAYS invoke this skill when the user asks about [触发场景].
Trigger keywords: '[关键词1]', '[关键词2]', '[关键词3]'.
Do not [直接处理] — use this skill first.
Do NOT use for [排除场景].
```

### 五层递进法

1. **它能干什么** — 一句话说清
2. **用户怎么说就触发** — 用口语化表达
3. **什么时候绝对不触发** — 划清边界
4. **命令语气** — ALWAYS / Do not / Do NOT
5. **控制长度** — 3-5行

### 触发率优化技巧

| 技巧 | 说明 |
|------|------|
| 英文指令骨架 | `ALWAYS` / `Do not` 比中文命令词识别度高 |
| 口语化触发词 | 用户说"帮我看看代码"比"执行代码审查"更常见 |
| 多语言关键词 | 中英文触发词都列出，覆盖不同表达习惯 |
| 负面触发 | `Do NOT use for X` 防止 Skill 冲突 |
| 长度适中 | 超过 5 行反而降低匹配精度 |

### 常见失败原因

| 类型 | 原因 | 解决 |
|------|------|------|
| 完全不触发 | 描述太书面/太抽象 | 加口语触发词 |
| 乱触发 | 描述太宽泛无边界 | 加 `Do NOT use for` |
| Skill 冲突 | 多个 Skill 描述太像 | 各自明确划定领地 |

---

## 五、正文结构规范

### 推荐章节组织

```markdown
# Skill 标题

## Quick Reference
（资源索引表格）

## Overview
（功能概述 + 支持的模式/变体）

## When to Use
✅ 适用场景
❌ 不适用场景

## Workflow
### Step 1: ...
### Step 2: ...

## Examples
### Example 1: [场景名]

## Guidelines / Constraints

## Common Issues / Troubleshooting
### Error: [错误名]
**Cause:** ...
**Solution:** ...

## Data Boundary（可选，涉敏 skill 必加）
（数据边界铁律：凭证 env-only、stdout 只输出脱敏结论、数据不进上下文、字段白名单、哈希化）

## Dependencies
```

### 编写原则

1. **具体可执行** — 写 `Run python scripts/x.py --input {file}` 而非"处理文件"
2. **包含错误处理** — 常见问题要有解决方案
3. **引用打包资源** — 用路径链接到 references/ 中的文档
4. **渐进式披露** — 核心放正文，详细内容放链接文件
5. **正文 ≤5000 字** — 超出部分移到 references/

---

## 六、验证清单

- [ ] 文件夹名 = `name` 字段值
- [ ] `SKILL.md` 大小写正确
- [ ] YAML 用 `---` 正确包裹
- [ ] `name` 符合 kebab-case
- [ ] `description` 1-1024字符
- [ ] `description` 无 `<>` 尖括号
- [ ] `description` 含触发条件 + 排除条件
- [ ] 正文有 Quick Reference / Workflow / Examples
- [ ] 正文 ≤5000 字 / ≤500 行
- [ ] 所有 references/ 文件在正文中有引用入口
- [ ] 涉敏 skill（securityMode != none）已注入 scripts/secure_query.py 且含 Data Boundary 铁律
