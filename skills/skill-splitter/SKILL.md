---
name: skill-splitter
description: |
  ALWAYS invoke this skill when the user asks to split, decompose, refactor a large skill,
  reduce skill runtime, 拆解大skill, 拆分技能, 技能瘦身.
  Trigger keywords: '拆解skill', '拆分skill', '拆大skill', 'skill太大', '运行太慢', '耗时太长',
  'split skill', 'decompose skill', 'skill too large', 'reduce latency', '性能优化', '瘦身'.
  Do not 直接拆解或重构 Skill 包 — use this skill first.
  Do NOT use for 创建新 Skill（用 skill-generator）、评估 Skill 质量（用 skill-assessor）、安装 Skill.
metadata:
  openclaw:
    emoji: "🪓"
    skillKey: "skill-factory"
    requires:
      bins: ["python3"]
---

# Skill Splitter — 大 Skill 自动拆解工具

将运行耗时过长、规模过大的单一 Skill 包，按数据依赖和功能域拆解为多个高内聚子 Skill + 薄编排器，降低单次运行成本。

## Quick Reference

| 任务 | 指引 |
|------|------|
| 拆解策略与决策树 | Read [references/splitting-strategy.md](references/splitting-strategy.md) |
| 数据契约模板 | Read [references/data-contract-template.md](references/data-contract-template.md) |
| 拆解后验证清单 | Read [references/verification-checklist.md](references/verification-checklist.md) |
| 分析目标 Skill（诊断） | Run [scripts/analyze_skill.py](scripts/analyze_skill.py) |
| 生成拆解方案 | Run [scripts/generate_split_plan.py](scripts/generate_split_plan.py) |

---

## Overview

大 Skill 常因承载过多功能域、串行执行长流程、代码与规则全量加载，导致单次运行耗时达数十分钟。本 Skill 依据 **Anthropic Agent Skills Specification V1.0** 与 skill-generator 规范，将大 Skill 拆解为：

```
大 Skill（胖）                         拆解后（瘦）
┌──────────────────┐          ┌──────────────────────────┐
│ 筛选→查询→信号→标签 │  ────→   │ orchestrator（薄编排器）  │
│ →洞察→评分→推送    │          │   ├── skill-筛选（短）     │
│ 43文件/40分钟      │          │   ├── skill-查询（中）     │
└──────────────────┘          │   └── skill-推送（短）     │
                              └──────────────────────────┘
```

支持四种拆解模式（见 [splitting-strategy.md](references/splitting-strategy.md)）：按功能域（横向）、按流水线阶段（纵向）、按运行类型（同步/异步）、按数据源。

---

## When to Use

✅ **适用**：
- 单个 Skill 运行耗时 > 10 分钟（如 40 分钟的全链路）
- 代码文件 > 20 个或总行数 > 5000，单一 SKILL.md 承载 ≥ 3 个独立功能域
- 部分模块需要独立部署/独立触发，但被大 Skill 捆绑
- 长耗时任务（预计算类）与短任务（查询类）混在同一个 Skill 中
- 模块间存在清晰的数据依赖边界，可拆为链式调用

❌ **不适用**：
- 创建新 Skill → 使用 `skill-generator`
- 评估 Skill 质量 → 使用 `skill-assessor`
- Skill 本身规模小（< 10 分钟、< 5 个文件）→ 拆分反而增加复杂度，不要拆
- 安装/共享 Skill → 使用 `find-skills`

---

## Workflow

### Phase 1: 诊断（Analyze）

运行分析脚本扫描目标 Skill，产出规模/模块/耗时热点报告：

```bash
python3 {SKILL_DIR}/scripts/analyze_skill.py --path {TARGET_SKILL_DIR} --output analysis.json
```

脚本输出：
- 文件总数、代码行数、各模块规模
- 模块间 import 依赖图
- 耗时热点（`time.sleep`、批处理循环、外部调用次数）
- 超阈值提示（文件数 > 20、行数 > 5000、耗时 > 10 分钟）

**判定**：若分析报告无任何超阈值信号，告知用户"该 Skill 规模合理，不建议拆分"，流程终止。

### Phase 2: 规划（Plan）

用拆解方案生成脚本 + 人工/Agent 审阅确定方案：

```bash
python3 {SKILL_DIR}/scripts/generate_split_plan.py \
  --analysis analysis.json \
  --mode {functional|pipeline|runtime|datasource} \
  --output split_plan.json
```

方案 JSON 包含：
- 子 Skill 划分（名称、包含模块、预估耗时）
- 模块间数据契约（输入/输出 JSON Schema 字段）
- 共享依赖清单（common.py 等需保留的公共模块）
- 编排器职责（串联顺序、失败处理）

**必须由 Agent 审阅方案并确认**，重点核对：
1. 数据契约字段是否与代码实际输入/输出一致
2. 共享依赖是否正确识别（避免拆后 import 断裂）
3. 拆分后是否有循环依赖

### Phase 3: 生成（Generate）

按 skill-generator 规范为每个子 Skill 生成标准结构（纯文件骨架，不改代码）：

```
<new-skill-name>/
├── SKILL.md          ← 命令式 description + 触发词 + 数据契约声明
├── references/       ← 拆解后的规则/文档（从原 Skill 迁移）
├── scripts/          ← 迁移的脚本（只移所属模块）
└── assets/           ← 迁移的资源
```

每个子 Skill 的 SKILL.md 必须：
- `description` 使用 `ALWAYS invoke` + 口语触发词 + `Do NOT use for`（遵循 skill-generator 规范）
- 声明输入/输出数据契约（引用 `data-contract-template.md` 规范）
- 预估运行耗时标注在 Overview 中

### Phase 4: 迁移（Migrate）

按 split_plan.json 执行文件迁移：

1. **移动模块代码**：每个子 Skill 只保留自己的模块目录与脚本
2. **公共依赖保留**：`common.py`、`_path_setup.py` 等被多模块引用的文件，保留在原位或提升到共享层，**修改 `sys.path` 而非复制代码**
3. **修复 import**：迁移后逐一检查 `from common import ...` 等跨模块引用
4. **保留数据契约文件**：输出 JSON Schema 到各子 Skill 的 `references/` 供调用方引用

### Phase 5: 验证（Verify）

按 [verification-checklist.md](references/verification-checklist.md) 逐项验证：

1. **独立可运行**：每个子 Skill 单独触发能完成自己的输入→输出
2. **功能等价**：拆解前后对同一输入，全链路输出一致（跑原 Skill 的回归测试）
3. **耗时达标**：每个子 Skill 预估耗时 ≤ 10 分钟，总耗时下降 ≥ 50%
4. **结构合规**：用 skill-assessor 的 `check_structure.sh` 检查每个子 Skill

### Phase 6: 收尾（Finalize）

1. **生成编排器**：原大 Skill 降级为薄编排器（保留 SKILL.md，内容精简为"串联调用各子 Skill"）
2. **更新文档**：编排器 SKILL.md 列出子 Skill 清单、调用顺序、数据流图
3. **清理**：删除迁移后的残留文件、`__pycache__`、临时 JSON
4. **汇报**：输出拆解摘要（子 Skill 清单、耗时对比、验证结果）

---

## Examples

### 示例 1：拆解 40 分钟的销售全链路 Skill

**用户说：**「sales-insight-pipeline 跑一次要 40 分钟，帮我拆开」

**执行过程：**
1. 诊断：`analyze_skill.py --path skills/sales-insight-pipeline` → 43 文件、6 功能域、含长耗时预计算模块
2. 规划：`generate_split_plan.py --mode pipeline` → 拆为 candidate-filter / customer-query / signal-extractor / tag-engine / insight-engine / recommendation-score / erp-pusher 7 个子 Skill + orchestrator
3. 生成 + 迁移：每个子 Skill 获得独立目录与模块代码，`common.py` 保留在共享层
4. 验证：回归测试通过，耗时从 40 分钟降至各子 Skill 2-8 分钟

**结果：** 7 个子 Skill + 1 个薄编排器，可按需独立触发短任务，长任务异步执行。

### 示例 2：按运行类型拆解

**用户说：**「这个 skill 里查询和预计算混在一起，拆开」

**执行过程：**
1. 诊断确认：秒级查询模块与分钟级预计算模块并存
2. 规划：`--mode runtime` → 拆为 sync-query（同步短任务）与 async-precompute（异步长任务）
3. 迁移 + 验证：短任务保持 `exec` 直接执行，长任务改为 `sessions_spawn` 异步

**结果：** 查询类请求不再被长任务阻塞，长任务可后台独立运行。

---

## Guidelines / Constraints

- **先诊断再拆**：不达阈值不拆，避免过度工程化
- **契约先行**：拆解前必须先明确子 Skill 间的数据契约，否则拆后无法串联
- **共享依赖不复制**：被多模块引用的公共代码用 `sys.path` 引用，复制会导致双份状态
- **禁止循环依赖**：拆解方案必须是无环 DAG，出现 A→B→A 需重新划分
- **功能等价是底线**：拆解后必须能通过原 Skill 的回归测试，否则回滚
- **编排器要薄**：编排器只负责路由与失败处理，不包含业务逻辑
- **兼容 skill-generator 规范**：每个子 Skill 需通过 skill-assessor 的 `check_structure.sh` 检查

---

## Common Issues / Troubleshooting

### Error: 拆解后 import 报错（ModuleNotFoundError）

**原因：** 跨模块引用未同步迁移，或共享依赖路径断裂。

**解决：** 检查 `sys.path` 注入（`_path_setup.py`）是否指向正确根目录；将公共模块保留在原位用绝对路径引用，不移动不复制。

### Error: 子 Skill 之间出现循环依赖

**原因：** 按功能域划分时边界不清，A 依赖 B 而 B 又依赖 A。

**解决：** 抽取出公共逻辑到共享模块，或调整划分边界重新规划。

### Error: 拆解后输出与原来不一致

**原因：** 数据契约字段在迁移中被遗漏或改名。

**解决：** 对照 split_plan.json 的契约字段逐一核对；跑原回归测试定位差异，回滚到拆分前状态。

### Error: 用户坚持拆分但诊断显示规模合理

**原因：** 用户基于感性判断，实际规模未超阈值。

**解决：** 展示诊断数据说明当前规模合理，询问是否因"特定模块耗时"而非整体规模触发；若用户仍要拆，可只拆耗时热点模块。

---

## Dependencies

- **python3**（必需）：分析/规划脚本运行环境
- **skill-generator**（协作）：子 Skill 结构生成规范参考（`tools/skill-generator/`）
- **skill-assessor**（协作）：拆解后质量验证（`tools/skill-assessor/scripts/check_structure.sh`）
- **目标 Skill 目录**：必须位于当前工作区可访问路径
- 无第三方 Python 依赖，仅标准库
