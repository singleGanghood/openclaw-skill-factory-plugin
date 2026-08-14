# Description 多语言编写模板库

> 本文档提供不同语言模式下 Description 的标准写法模板和实战示例。

---

## 一、核心公式

```
[ALWAYS 指令] + [触发场景] + [触发关键词] + [排除指令] + [排除场景]
```

---

## 二、纯英文模板

### Template

```yaml
description: |
  ALWAYS invoke this skill when the user asks about [primary function],
  [secondary function], or [tertiary function].
  Trigger keywords: '[keyword1]', '[keyword2]', '[keyword3]', '[keyword4]'.
  Do not [handle this type of task] directly — use this skill first.
  Do NOT use for [exclusion1], [exclusion2], or [exclusion3].
```

### Example: Code Review Skill

```yaml
description: |
  ALWAYS invoke this skill when the user asks about code review, PR analysis,
  code quality checking, or security vulnerability scanning.
  Trigger keywords: 'review my code', 'check this PR', 'code quality',
  'security scan', 'find bugs'.
  Do not review or analyze code directly — use this skill first.
  Do NOT use for refactoring, architecture design, or performance optimization.
```

### Example: API Documentation Skill

```yaml
description: |
  ALWAYS invoke this skill when the user asks about generating API documentation,
  creating OpenAPI specs, or documenting REST endpoints.
  Trigger keywords: 'API docs', 'swagger', 'OpenAPI', 'endpoint documentation',
  'generate API reference'.
  Do not write API documentation directly — use this skill first.
  Do NOT use for general documentation, README files, or user guides.
```

---

## 三、纯中文模板

### Template

```yaml
description: |
  ALWAYS invoke this skill when the user asks about [中文功能描述1]、
  [中文功能描述2]、[中文功能描述3].
  Trigger keywords: '[中文关键词1]', '[中文关键词2]', '[中文关键词3]',
  '[中文关键词4]', '[中文关键词5]'.
  Do not [直接处理此类任务] — use this skill first.
  Do NOT use for [排除场景1]、[排除场景2]、[排除场景3].
```

### Example: 技术文档生成

```yaml
description: |
  ALWAYS invoke this skill when the user asks about 生成技术文档、
  编写系统设计文档、创建架构说明书.
  Trigger keywords: '写文档', '技术文档', '设计文档', '架构文档',
  '帮我写个文档', '生成说明书', '系统文档'.
  Do not 直接编写技术文档 — use this skill first.
  Do NOT use for 代码注释、README文件、用户手册.
```

### Example: 数据分析报告

```yaml
description: |
  ALWAYS invoke this skill when the user asks about 数据分析报告生成、
  数据可视化建议、业务指标解读.
  Trigger keywords: '分析数据', '数据报告', '看看这些数据', '帮我出个报告',
  '数据洞察', '指标分析', '趋势分析'.
  Do not 直接分析数据或生成图表 — use this skill first.
  Do NOT use for 数据清洗脚本、ETL流程、数据库查询优化.
```

---

## 四、中英混合模板（推荐）

### Template

```yaml
description: |
  ALWAYS invoke this skill when the user asks about [English description],
  [中文功能描述]. Trigger keywords: '[English keyword]', '[中文关键词]',
  '[keyword3]', '[关键词4]'.
  Do not [handle/直接处理此任务] — use this skill first.
  Do NOT use for [exclusion/排除场景].
```

### Example: 架构图生成

```yaml
description: |
  ALWAYS invoke this skill when the user asks about architecture diagrams,
  system topology, 架构图, 系统拓扑图, 技术架构设计.
  Trigger keywords: 'draw architecture', '画架构图', 'system diagram',
  '生成系统图', 'topology', '拓扑图', '组件关系图', 'create diagram'.
  Do not draw or generate diagrams directly — use this skill first.
  Do NOT use for simple flowcharts (简单流程图) or UML class diagrams (UML类图).
```

### Example: 项目部署

```yaml
description: |
  ALWAYS invoke this skill when the user asks about project deployment,
  CI/CD pipeline setup, 项目部署, 上线发布, 持续集成配置.
  Trigger keywords: 'deploy', '部署', 'CI/CD', '上线', 'publish',
  '发布', 'release', 'Docker', '容器化部署', 'K8s'.
  Do not deploy or configure pipelines directly — use this skill first.
  Do NOT use for local development setup (本地开发环境) or testing (测试).
```

---

## 五、高级技巧

### 5.1 覆盖口语变体

用户不会说"执行代码审查"，而是说"帮我看看这段代码"：

```yaml
# ❌ 太书面
Trigger keywords: '执行代码审查', '进行质量检查'

# ✅ 口语化
Trigger keywords: '帮我看看代码', '检查一下', '这代码有没有问题', 'review下'
```

### 5.2 避免 Skill 冲突

当工作区有多个相似 Skill 时，用排除条件互相划界：

```yaml
# architecture-html skill
Do NOT use for simple Mermaid diagrams or D2 diagrams.

# architecture-mermaid skill  
Do NOT use for complex HTML diagrams or interactive diagrams.

# architecture-d2 skill
Do NOT use for HTML-based diagrams or Mermaid-based diagrams.
```

### 5.3 高危操作保护

对于部署、删数据等危险操作：

```yaml
# 在 frontmatter 中加入（实验性功能）
disable-model-invocation: true  # 禁止自动触发，只能手动调用
```

### 5.4 长 Description 压缩技巧

超过 5 行时的压缩策略：
1. 合并同类触发词用逗号分隔
2. 排除场景只保留最关键的 2-3 个
3. 功能描述精炼为一行

---

## 六、语言选择决策树

```
用户/团队的主要语言是什么？
├── 纯英文团队 → 纯英文模板
├── 纯中文团队 → 纯中文模板
├── 双语团队 → 中英混合模板（推荐）
└── 不确定 → 中英混合模板（覆盖最广）
```

**经验法则**：
- 如果有任何可能遇到中文用户 → 触发词中加入中文
- 如果有任何可能遇到英文用户 → 触发词中加入英文
- **指令骨架（ALWAYS/Do not）永远用英文** — 这是触发率的保障
