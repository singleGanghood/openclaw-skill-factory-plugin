---
name: skill-factory-orchestrator
description: |
  ALWAYS invoke this skill when the user wants an END-TO-END skill production pipeline:
  from a requirement (or a screenshot / design mock) all the way to a validated, governed Skill.
  从需求（或截图）一站式产出、评估、（可选）拆分并治理登记一个高质量 Skill。
  Trigger keywords: 'skill factory', 'produce a skill', 'make a skill end to end', '造技能',
  '技能工厂', '一站式做skill', '从截图做skill', '批量产skill', '持续生产skill',
  'skill pipeline', 'generate then assess skill'.
  Do NOT use for a single isolated step — use skill-generator / skill-assessor / skill-splitter
  / skill-factory-screenshot directly for one-off actions.
metadata:
  openclaw:
    emoji: "🏗️"
    skillKey: "skill-factory"
---

# Skill Factory Orchestrator — 龙虾持续生产新 Skill 的薄编排器

把 `skill-factory-screenshot`（可选看屏输入）、`skill-generator`（生成）、
`skill-factory-eval`（TDD/eval 动态跑分 + description 自动优化）、`skill-assessor`（静态评估）、
`skill-splitter`（可选拆分）串成一条闭环流水线，并完成 **OpenClaw 路径与授权边界改造**。

本编排器**只做路由与治理登记，不含业务逻辑**——每一步都委托给对应的子 skill。

> **对标 Anthropic 官方 `skill-creator`**：本编排器 = 官方"元 Skill 入口"的对齐补齐，
> 并通过 `skill-factory-eval` 的**快路径短路**（0 模型调用的静态预检）实现**更快创建**，
> 通过 `metadata.openclaw` + 治理注册表实现官方没有的**生态注册**。
> 逐条对比见 [skill-factory-eval/references/vs-skill-creator.md](../skill-factory-eval/references/vs-skill-creator.md)。

## Quick Reference

| 任务 | 指引 |
|------|------|
| **幂等安装**（内容寻址四态收敛 + 原子转正 + 查重登记） | Run [scripts/install_skill.py](scripts/install_skill.py) |
| 治理注册表 Schema 与登记规则（含幂等键） | Read [references/governance-registry.md](references/governance-registry.md) |
| eligible vs 治理：两个事实源边界 | Read [references/two-sources-of-truth.md](references/two-sources-of-truth.md) |

---

## Overview：九步闭环（在原七步中插入快路径 + eval 双引擎）

| # | 步骤 | 委托给 | 门禁 |
|---|------|--------|------|
| 01 | 需求（功能/边界/输入输出） | 用户 / screenshot | — |
| 02 | 暂存创建（隔离候选，不影响线上） | `skill-generator` | 只写暂存区，不自动安装、不覆盖同名 skill |
| **03** | **快路径静态预检（0 模型调用，秒级）** | **`skill-factory-eval` Phase 0** | **<70 分直接回喂 generator，不进后续昂贵步骤** |
| 04 | 静态质量评估（结构/安全/规范 7 维） | `skill-assessor` | 静态高分 ≠ 运行时可用 |
| **05** | **TDD 动态跑分 + description 自动优化** | **`skill-factory-eval` Phase 1–4** | **precision/recall < 目标则回喂优化，按 test 集选最优** |
| 06 | 授权**幂等安装**（用户同意后执行） | `install_skill.py` | 需用户明确同意；四态收敛，conflict 拒绝 |
| 07 | 运行验证（info + eligible） | eligibility 判定 | OS/bins/env 真实就绪才算可用 |
| 08 | 新会话测试（正例触发、反例不误触） | 新 session | 触发词命中 + 排除有效 |
| 09 | 治理**幂等登记**（版本、hash、eval 证据、回滚） | `install_skill.py` | 幂等键查重，只写注册表，不改 eligible |

> **快路径优先（提速核心）**：Step 03 用零模型调用的静态分析先淘汰弱候选，
> 约 80% 的低质 description 在此秒级拦截并回喂，**根本不进入 Step 04/05 的昂贵评估**——
> 这是相对官方"逢改必真实跑模型"的最大速度优势。
>
> **两个事实源不能混**：OpenClaw 的 per-agent eligible 清单决定"现在能不能用"；
> 治理注册表记录"哪个版本通过过什么验证（含 eval 的 precision/recall 证据）"。注册表不能替代运行时。

> **两个事实源不能混**：OpenClaw 的 per-agent eligible 清单决定"现在能不能用"；治理注册表记录"哪个版本通过过什么验证"。注册表不能替代运行时。

---

## When to Use

✅ **适用**：
- 从一句话需求 / 一张截图，一路产出可用且经过质量把关的 Skill
- 需要"生成 → 评估 → 不达标回喂重生成"的自动迭代闭环
- 需要在产出后做治理登记（版本/hash/回滚证据）以便审计

❌ **不适用**：
- 只想做单步（只生成 / 只评估 / 只拆 / 只截图）→ 直接用对应子 skill
- 安装外部 skill → 用 `find-skills`

---

## Workflow

### Step 01 — 需求收集
若用户提供的是**截图/设计稿/现有工具界面**，先委托 `skill-factory-screenshot` 产出 `requirementDraft`；
否则直接从用户描述提炼：功能、边界、输入/输出、触发词、是否需要脚本/依赖。

**同时判定 `securityMode`**：扫描需求文本，命中涉敏关键词（内部知识库/私有数据/加密/脱敏/
防泄露/内部接口等）则 `securityMode = data-guard` 或 `basic-guard`，否则 `none`。
映射表见 `skill-data-guard/references/keyword-trigger-map.md`。

### Step 02 — 暂存创建（隔离候选）
委托 `skill-generator` 生成骨架，并**显式传入 Step 01 判定的 `securityMode`**。**门禁**：
- 只写入**暂存目录**（如 `.skill-factory/staging/<name>/`），不写入生效目录
- **不自动安装**、**不覆盖同名已有 skill**（同名冲突则改名或提示）
- `securityMode != none` 时，generator 需注入数据守卫骨架 + Data Boundary 铁律（见 `skill-data-guard`）

### Step 03 — 快路径静态预检（0 模型调用，秒级）★提速核心
委托 `skill-factory-eval` 的 Phase 0：
```bash
python3 <eval-skill>/scripts/static_trigger_score.py .skill-factory/staging/<name>/SKILL.md
```
- **<70 分**：**立即**用输出的 `optimization_hints` 回喂 `skill-generator` 改写，
  改完再跑本步——**全程 0 次模型调用**。绝大多数弱候选在此被秒级拦截，**不进入后续昂贵步骤**。
- **≥70 分**：进入 Step 04。

### Step 04 — 静态质量评估（结构/安全/规范）
委托 `skill-assessor` 对暂存候选做**静态 7 维**打分（结构/frontmatter/正文/token 效率/生态兼容等），
并对 `securityMode != none` 的候选启用**第 8 维「数据隔离与安全」门禁**（< 6 分一票否决）。
**门禁**：静态高分 ≠ 运行时可用、≠ 触发准确。低于阈值（建议 ≥ 80）则拿"优化指令"回喂 Step 02。
（可选）若候选超阈值过大（>10 分钟 / >20 文件 / ≥3 功能域），委托 `skill-splitter` 拆分。

### Step 05 — TDD 动态跑分 + description 自动优化 ★补齐官方核心
委托 `skill-factory-eval` 的**一键全自动闭环**：
1. `gen_eval_set.py` 生成正/反例骨架 → 补足 **≥3 正例 + ≥3 反例**（TDD golden cases）
2. `run_eval_loop.py` 一条命令跑完：分层切 train/test → 用**进程协议**委托宿主 subagent 判定
   （`--grader-backend host-cmd`）→ `aggregate` 算 precision/recall/accuracy →
   未达标自动改写 description（`--rewriter-backend host-cmd`，隐藏 test 分防过拟合）→ 循环 →
   **按 test 集选最优**
3. `generate_report.py` 产出**单文件 HTML 可视化报告**供人工复核

**门禁**：动态 `verdict=PASS` 才算"触发质量合格"，把 `eval_results.json` + `eval_report.html`
作为**动态验证证据**留档。

### Step 06 — 授权幂等安装（需用户明确同意）★内容寻址、可反复执行
**必须由用户明确同意后**，才把暂存候选转正到生效目录。转正走**幂等安装脚本**——
以 `contentHash` 为幂等键做**内容寻址的原子转正**，四态收敛（install/noop/upgrade/conflict）：

```bash
python3 <orchestrator>/scripts/install_skill.py \
  --staging .skill-factory/staging/<name> \
  --dest <skills 生效根> \
  --registry .skill-factory/registry.json \
  --assessor-score <Step04分> --eval-precision <Step05> --eval-recall <Step05> \
  [--dry-run]   # 先预演决策，零副作用
```

- **noop**：内容已一致 → 什么都不做（重复安装安全，退出码 0）。
- **conflict**（同版本内容漂移 / 降级，退出码 2）：**拒绝落盘**，提示 bump 版本；确需覆盖才显式 `--force`。
- **install / upgrade**：原子转正（临时目录 + `os.replace`），并发下加文件锁防竞态；upgrade 自动记 `rollbackRef`。
- 也可经 `npm install`（`openclaw-skill-factory-plugin` 包）/ 未来 `openclaw plugins install` 走分发。
- 未同意前一律停留在暂存区。**安装绝不修改 eligible / per-agent skills**（见 two-sources-of-truth.md）。

### Step 07 — 运行验证（info + eligible）
- `info`：读取 SKILL.md 静态元数据（name/description/metadata.openclaw）
- `eligible`：判定运行时是否真正就绪——OS 是否匹配 `os`、`requires.bins` 是否在 PATH、`env`/`config` 是否满足
- 二者同时满足才算"该 agent 现在能用"。**只读判定，不修改 per-agent 白名单。**

### Step 08 — 新会话测试
在新 session 验证：正例（目标触发词能命中并加载）、反例（`Do NOT use for` 场景不误触发）。
这是对 Step 05 动态跑分结论的真实环境复核。

### Step 09 — 治理幂等登记（只写注册表）
`install_skill.py` 在转正时**顺带完成幂等登记**（Step 06/09 合一执行），按
[references/governance-registry.md](references/governance-registry.md) 以 **`(name, version, contentHash)`
为幂等键**追加记录：`name / version / contentHash / assessorScore / evalPrecision / evalRecall /
securityMode / verifiedAt / verifiedBy / rollbackRef`。
- **幂等键查重**：已存在完全相同的 `(name, version, contentHash)` → **不重复追加**（noop）。
- 若只想单独登记而不转正，可对已生效目录再跑一次（noop 分支会补记缺失的 record）。
**约束**：本步骤**只写治理注册表，绝不修改 eligible / per-agent skills 配置**——两个事实源分离。

---

## Examples

### 示例：从截图一路产出并登记
**用户说：**「这是内部报销工具的截图，帮我造个自动填报销的 skill，走完整流程」
1. Step01 委托 screenshot 桥接 → requirementDraft
2. Step02 skill-generator → 暂存 `expense-filler`
3. Step03 快路径静态预检 → 58 分 → 回喂 generator（**0 模型调用**）→ 再检 82 分
4. Step04 skill-assessor 静态 7 维 → 85 分
5. Step05 eval 动态跑分：首轮 precision=0.6（2 个反例误触发）→ 回喂优化 → precision=1.0 / recall=0.9（按 test 集选定）
6. Step06 用户同意 → 转正
7. Step07 eligible 判定（需 peekaboo，os=darwin）通过
8. Step08 新会话正/反例测试通过
9. Step09 登记 `expense-filler@1.0.0 / hash / assessor=85 / precision=1.0 / recall=0.9 / verified`

### 示例：涉敏数据守卫（关键词触发）
**用户说：**「帮我做一个查询内部知识库的 skill，数据要加密、不能泄露到会话和思考过程」
1. Step01 关键词扫描 → 命中 L1 → `securityMode = data-guard`
2. Step02 generator 注入 `secure_query.py` + Data Boundary 铁律 + description 的 DATA-GUARD 声明
3. Step03 快路径静态预检通过
4. Step04 assessor 启用第 8 维「数据隔离与安全」→ 8 分（脚本封装/脱敏/进程内自取/铁律齐备）
5. Step05 eval 动态跑分通过
6. Step06 用户同意 → 转正
7. Step09 登记时追加 `securityMode: "data-guard"`

---

## Guidelines / Constraints

- **编排器要薄**：只路由 + 治理登记，业务全部委托子 skill。
- **暂存优先**：未经用户明确同意，候选永远停在暂存区，不影响线上。
- **回喂闭环**：assessor 低分必须回喂 generator，禁止跳过评估直接安装。
- **两个事实源分离**：治理登记 ≠ 运行时 eligible；登记步骤不改 per-agent 白名单。
- **授权边界**：涉及截图的高风险命令，遵守 `skill-factory-screenshot` 的 arm/disarm 与 TCC 授权。

---

## Common Issues / Troubleshooting

### Error: 候选评估分数上不去
**原因：** description 无触发词 / 缺 When to Use / 缺 Examples。
**解决：** 用 assessor 输出的优化指令回喂 generator，循环至达标。

### Error: 安装后 agent 里看不到该 skill
**原因：** eligible 未通过（OS 不匹配 / bin 缺失 / 不在 per-agent 白名单）。
**解决：** 看 Step05 的 eligible 判定；确认 `requires.bins`；检查 `agents.<id>.skills` 或 `agents.defaults.skills` 白名单。这是 eligible 问题，与治理注册表无关。

### Error: 重复安装是否安全 / 装了两次会怎样
**答：** 安全。`install_skill.py` 是**幂等**的——同内容同版本第二次装是 `noop`（零改动、退出码 0）；
同版本却改了内容会判 `conflict`（拒绝落盘，需 bump 版本），不会静默覆盖。可用 `--dry-run` 先预演决策。

---

## Dependencies

- 子 skill：`skill-factory-screenshot`、`skill-generator`、`skill-factory-eval`、`skill-assessor`、`skill-splitter`（同插件捆绑）
- 幂等安装脚本：`scripts/install_skill.py`（`python3`，仅标准库）
- 治理注册表文件：`.skill-factory/registry.json`（首次自动创建）
- 无第三方依赖（`skill-factory-eval` / `skill-splitter` / `install_skill.py` 需 `python3`，仅标准库）
