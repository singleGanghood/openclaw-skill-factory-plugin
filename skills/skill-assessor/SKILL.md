---
name: skill-assessor
description: "ALWAYS invoke this skill when the user asks to evaluate, assess, audit, score, or review the quality of an existing Skill (技能/skill). Trigger keywords: 'evaluate skill', 'assess skill', 'audit skill', 'score skill', '评估skill', '评分skill', '检查skill质量', 'skill质量', '技能评估', '技能打分', '审查技能', 'review skill quality', 'skill audit', 'rate skill'. Do not evaluate code quality in general — use this skill only for Agent Skill packages. Do NOT use for creating new skills (use skill-generator instead) or installing skills (use find-skills instead)."
metadata:
  openclaw:
    emoji: "📊"
    skillKey: "skill-factory"
    requires:
      bins: ["bash"]
---

# Skill Assessor — Agent Skill 质量评估工具

## Quick Reference

| Task | Guide |
|------|-------|
| 完整评分标准与权重 | Read [references/scoring-rubric.md](references/scoring-rubric.md) |
| 评估报告输出格式 | Read [references/report-format.md](references/report-format.md) |
| 结构检查脚本 | Run [scripts/check_structure.sh](scripts/check_structure.sh) |

---

## Overview

本 Skill 对目标 Skill 包进行**全方位质量评估**，依据 Anthropic Agent Skills Specification V1.0 标准和业界最佳实践，从 7 个维度进行打分，输出百分制评估报告，并给出可直接衔接 `skill-generator` 进行优化的改进建议。

**评估维度**（总分 100 分）：

| # | 维度 | 分值 | 核心关注点 |
|---|------|------|-----------|
| 1 | 目录结构规范 | 10分 | 文件组织、命名、禁止事项 |
| 2 | Frontmatter 质量 | 15分 | name/description 字段规范性 |
| 3 | Description 触发效能 | 20分 | 触发率、覆盖面、排除边界 |
| 4 | 正文结构完整性 | 15分 | 标准章节是否齐全 |
| 5 | 内容质量与可执行性 | 20分 | 指令具体性、示例、错误处理 |
| 6 | Token 效率与渐进加载 | 10分 | 分层合理性、正文长度 |
| 7 | 生态兼容性 | 10分 | 与其他 Skill 边界清晰、可组合 |

---

## 静态评估 vs 动态触发测试（重要：补齐短板）

本 skill 做的是**静态评估**（读文件、按 rubric 打分），它**不能**证明 description 在真实
用户 query 下是否真的会触发。**动态触发测试（precision/recall/accuracy）属于 `skill-factory-eval`**。

| 层面 | 谁负责 | 产出 |
|------|--------|------|
| 静态：结构/规范/可读性/token 效率 | **本 skill（assessor）** | 7 维 100 分制报告 |
| 动态：真实 query 下触发率 / 误触发 | **`skill-factory-eval`** | precision/recall + 自动优化后的 description |

**推荐用法**：先用本 skill 做静态门禁（≥80 分），再交给 `skill-factory-eval` 做 TDD 动态跑分。
两者结论都留档，才是"静态高分 + 动态可触发"的完整质量证据。图片对比表里"缺动态触发测试"
的短板，正是由 `skill-factory-eval` 补齐。

---

## When to Use

✅ **适用场景**：
- 评估一个已有 Skill 的质量是否达标
- 对比多个 Skill 找出最佳实践
- 在发布/共享 Skill 前进行质量把关
- 诊断为什么一个 Skill 触发不稳定
- 优化已有 Skill 前获取改进方向

❌ **不适用**：
- 创建新 Skill → 使用 `skill-generator`
- 安装外部 Skill → 使用 `find-skills`
- 评估代码质量（非 Skill 包） → 常规 code review

---

## Workflow

### Phase 1: 确定评估目标

1. 确认用户指定的目标 Skill 路径（如 `.codebuddy/skills/<skill-name>/`）
2. 如未指定，列出当前工作区所有 Skill 供用户选择

### Phase 2: 全面检索 Skill 包内容

对目标 Skill 包执行完整扫描：

```bash
# 1. 检查目录结构
find .codebuddy/skills/<target-skill>/ -type f | sort

# 2. 读取 SKILL.md 全文
cat .codebuddy/skills/<target-skill>/SKILL.md

# 3. 读取所有 references/ 文件
find .codebuddy/skills/<target-skill>/references/ -name "*.md" -exec cat {} \;

# 4. 读取所有 assets/ 文件列表
find .codebuddy/skills/<target-skill>/assets/ -type f

# 5. 读取所有 scripts/ 文件
find .codebuddy/skills/<target-skill>/scripts/ -type f -exec cat {} \;
```

### Phase 3: 逐维度评分

按照 [references/scoring-rubric.md](references/scoring-rubric.md) 中的详细评分标准，逐项打分。

**每个维度必须输出**：
- 得分（x/满分）
- 扣分原因（具体指出问题）
- 亮点（如有）

### Phase 4: 生成评估报告

按照 [references/report-format.md](references/report-format.md) 的标准格式输出报告，包含：

1. **评估概要**（一句话总结 + 总分）
2. **各维度详细评分表**
3. **关键问题列表**（按严重程度排序）
4. **改进建议**（可直接用于 `skill-generator` 优化）

### Phase 5: 输出优化指令

生成一段**可直接传递给 `skill-generator`** 的优化指令，格式如下：

```
请使用 skill-generator 对 <skill-name> 进行以下优化：
1. [具体优化项1]
2. [具体优化项2]
...
目标语言模式：[纯英文/纯中文/中英混合]
保留现有功能，仅修复评估中发现的问题。
```

### Phase 6: 衔接动态触发测试（静态达标后）

静态评分 ≥ 80 后，**建议**交给 `skill-factory-eval` 做动态触发跑分与 description 自动优化，
以获得 precision/recall 证据。若发现静态高分但触发不稳，回到 Phase 5 输出优化指令继续迭代。

---

## Examples

### Example 1: 评估一个质量较好的 Skill

**用户说：**「帮我评估 ai-wiki 这个 skill」

**执行：**
1. 扫描 `.codebuddy/skills/ai-wiki/` 全部内容
2. 逐维度打分
3. 输出评分报告

**结果示例摘要：**
```
📊 评估报告：ai-wiki
总分：87/100（优秀）

✅ 亮点：description 触发覆盖面广、正文结构完整、Quick Reference 清晰
⚠️ 改进：description 略超长度建议（当前约8行，建议5行内）
```

### Example 2: 评估一个质量欠佳的 Skill

**用户说：**「检查一下 my-tool 的 skill 质量」

**执行：**同上

**结果示例摘要：**
```
📊 评估报告：my-tool
总分：42/100（需重构）

❌ 关键问题：
1. description 无触发关键词（-12分）
2. 缺少 When to Use 章节（-8分）
3. 无 Examples 和 Troubleshooting（-15分）

🔧 优化指令（可直接用于 skill-generator）：
请使用 skill-generator 对 my-tool 进行以下优化：
1. 重写 description，加入 ALWAYS 指令和口语化触发词
2. 补充 When to Use（适用 + 不适用）
3. 补充 2-3 个 Examples
4. 补充 Common Issues 章节
目标语言模式：中英混合
```

---

## Guidelines

- **客观公正**：严格按评分标准打分，不因 Skill 复杂度加减分
- **具体到行**：扣分必须指出具体位置和原因
- **建设性优先**：改进建议必须具体可操作
- **衔接性**：优化建议必须兼容 `skill-generator` 的输入格式
- **完整性**：即使 Skill 质量极高，也要完成全部 7 个维度的评估

---

## Common Issues

### 问题：目标 Skill 路径不存在

**Cause:** 用户提供了错误的 Skill 名称或路径
**Solution:** 列出当前 `.codebuddy/skills/` 下所有可用 Skill，让用户选择

### 问题：Skill 只有 SKILL.md 没有子目录

**Cause:** 这是合法的最小 Skill 结构
**Solution:** 正常评估，子目录相关的评分项按"不适用"处理（不扣分也不加分）

### 问题：SKILL.md 的 YAML 解析失败

**Cause:** frontmatter 格式错误（缺少 `---` 分隔符、缩进错误等）
**Solution:** 在 Frontmatter 维度给 0 分，详细说明格式错误，建议修复

---

## Dependencies

- 目标 Skill 目录必须位于当前工作区可访问路径
- 评估标准引用 `skill-generator` 的规范（`.codebuddy/skills/skill-generator/references/spec-reference.md`）
- 无外部依赖
