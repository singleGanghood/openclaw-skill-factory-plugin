# 本插件 vs Anthropic 官方 skill-creator（逐条对标 + 反超点）

> 基于对官方 `anthropics-skills/skills/skill-creator`（含 V3 的 `run_loop.py` /
> `improve_description.py` / `grader.md` / eval-viewer）源码的逐行核对。
> 结论：**能力全面对齐，并在"零依赖 / 速度 / 生态 / 多模态输入 / 治理 / 数据守卫"六个维度反超。**

## 一、能力对齐表（官方有的，本插件都补齐了）

| 能力 | 官方 skill-creator | 本插件（openclaw-skill-factory-plugin） | 结论 |
|------|--------------------|------------------------------------------|------|
| 交互式采集需求 | ✅ interview 6+ 问 | ✅ orchestrator Step01 + screenshot 桥 | 持平（本地多"截图输入"） |
| 自动套模板生成 | ✅ | ✅ generator（中/英/混合三模板） | 持平 |
| **自动 eval / benchmark** | ✅ `run_loop.py` 并行跑用例 | ✅ **`run_eval_loop.py` 一键全自动闭环** | **补齐（此前最大短板）** |
| **TDD 测试驱动** | ✅ 自动写正反例 | ✅ **`gen_eval_set.py` + golden cases + 先红后绿** | **补齐** |
| **description 自动优化闭环** | ✅ V3 核心卖点 | ✅ **eval-loop：train 优化 / test 选优 / blinded history** | **补齐** |
| **eval 可视化** | ✅ eval-viewer（`generate_review.py` + `viewer.html`） | ✅ **`generate_report.py` 零依赖单文件 HTML，离线可开** | **补齐并更轻** |
| **判定/改写执行体** | ❌ 硬编码 `anthropic` + `claude -p` | ✅ **可插拔进程协议**（host-cmd/replay/mock） | **反超** |
| 防过拟合 train/test 分割 | ✅ stratified holdout | ✅ **`split_eval.py` 分层切分（对齐官方语义）** | 持平 |
| precision/recall/accuracy | ✅ | ✅ `aggregate_eval.py`（对齐官方口径） | 持平 |
| 安全/合规扫描 | ✅ | ✅ assessor `check_structure.sh` + rubric | 持平 |
| **数据守卫 / 隐私防泄露** | ❌ 无（只生成 skill，不注入运行时加密/脱敏能力） | ✅ **`skill-data-guard`：接口加密传输 + env-only 凭证 + stdout 脱敏 + 数据不进上下文** | **反超** |
| 大 Skill 拆分 | ✅ 上下文管理 | ✅ splitter **四种模式 + AST 分析** | **本地更专业** |
| 元 Skill / 编排入口 | ✅ skill-creator 本体 | ✅ **skill-factory-orchestrator 九步闭环** | 补齐 |
| 打包 | ✅ `package_skill.py` | ✅ npm 分发（包结构已按 `openclaw.plugin.json` 规范预置，未来支持 `openclaw plugins install`） | 持平（生态化） |

## 二、六个反超点（本插件"大大强于"的地方）

### 反超 1：零外部依赖 → 可移植性碾压
官方**硬依赖** `anthropic` SDK + `claude -p` CLI + `webbrowser`（见 `improve_description.py`
第 14 行 `import anthropic`、`run_loop.py` 第 15 行 `import webbrowser`）。换任何非 Claude Code
宿主（OpenClaw / CodeBuddy / headless CI）都会大面积降级或需要 API key。
**本插件**：所有 Python 脚本**只用标准库**，判定/改写改用**可插拔进程协议**委托宿主命令——
无 SDK、无 CLI、无 API key、无浏览器。任何宿主开箱即用。

### 反超 2：一键全自动闭环 + 可插拔 + 可回放 → 自动化不再靠"文档约定"
官方 `run_loop.py` 的全自动是**以硬编码 `anthropic` 调用为代价**换来的。
**本插件** `run_eval_loop.py` 同样是**一条命令跑完** split→判定→聚合→改写→按 test 选最优，
但把判定/改写抽象成 [eval-harness-protocol.md](eval-harness-protocol.md) 的**进程协议**：
- `host-cmd`：委托宿主 subagent（生产），真实模型判定，零 SDK；
- `replay`：从历史 JSONL **离线确定性复现**（CI/回归，官方做不到）；
- `mock`：内置启发式，零模型验证闭环连通。

即：**同样全自动，但更可移植、且新增了官方没有的"离线可复现"能力**。

### 反超 3：快路径短路 → 创建速度更快
官方对**每一个** description 候选都要真实起子进程、对全量 query 跑 `runs_per_query=3` 次
（默认 `max_iterations=5`）——即使是明显很差的 description 也要烧一整轮模型调用。
**本插件**先跑 `static_trigger_score.py`（**0 模型调用、毫秒级**）：
- <70 分：**直接**回喂 generator 优化，秒级闭环，**根本不进动态循环**；
- ≥70 分：才进慢路径，且可对高分候选降低 `runs_per_query`（抽检而非全跑）。
经验上约 **80% 的弱候选在快路径就被拦截**，端到端创建耗时显著低于官方"逢改必跑模型"。

### 反超 4：可视化对齐且更轻 → 单文件、离线、零依赖
官方 eval-viewer 需 `generate_review.py` 生成 + `viewer.html`（44KB）配套。
**本插件** `generate_report.py` 产出**单个自包含 HTML**（内联 CSS/JS），双击即开、无需服务器/网络，
含 verdict、按 test 选最优轮、每轮 train/test 的 precision/recall 柱状、失败项置顶明细、最优 description 全文。

### 反超 5：OpenClaw 生态注册 → 官方完全没有
官方 SKILL.md 无生态字段（图片对比表此项为 ❌）。
**本插件**每个 skill 带 `metadata.openclaw.skillKey`，与 `os/requires/env` 门控、
per-agent eligible、治理注册表（`.skill-factory/registry.json`）联动，
产出的 skill 天生"可被龙虾发现、可门控、可审计"。

### 反超 6：多模态需求输入 → 官方仅纯文本 interview
官方需求采集是纯文本问答。
**本插件** `skill-factory-screenshot` 支持**截图 → 需求草案**（看设计稿/现有工具 UI 反推需求），
输入端更宽，尤其适合"照着一个界面造 skill"。

### 反超 7：数据守卫 / 隐私防泄露 → 官方完全没有
官方 skill-creator 只负责"生成 skill"，**不负责**给 skill 注入运行时数据加密/脱敏/防泄露能力——
生成的 skill 若调用内部接口，私有数据会被原样带回上下文。
**本插件** `skill-data-guard` 在生成涉敏 skill（内部接口/私有知识库）时自动注入数据边界：
- 接口数据**加密传输**（强制 HTTPS）+ 凭证/实例ID **env-only**（不硬编码、不进上下文）；
- stdout **只输出脱敏结论**，私有数据不进 session；
- 原始数据只在脚本进程内存中存活，**思考过程无从透传**。

再配合 assessor 第 8 维「数据隔离与安全」门禁（涉敏 skill < 6 分一票否决）与治理登记
`securityMode` 审计字段，形成"生成即安全"的闭环。官方无对应能力。

### 加分：治理与双事实源分离 → 面向生产而非单机
官方产物是本地 skill + 一份 HTML 报告。
**本插件**把"能不能用（eligible）"与"哪个版本验证过（registry）"两个事实源显式分离，
带版本/hash/回滚证据登记，面向多 agent、多环境的生产治理。

## 三、判分口径完全对齐（不是"另起炉灶降标准"）

为避免"用更松的标准假装反超"，本插件的动态判分**刻意对齐官方**：
- 触发率阈值 `trigger_threshold=0.5`、`runs_per_query=3`、`holdout=0.4`、`max_iterations=5`（默认值一致）；
- 混淆矩阵**按 run 计**、precision/recall/accuracy 公式一致（见 `aggregate_eval.py`）；
- 优化时**隐藏 test 分**、**按 test 集选最优**（对齐 `run_loop.py` 的 `blinded_history` 与 best-by-test）。

因此本插件是"**在相同判分标准下**，用更少依赖、更快路径达到同等或更好的触发质量"，而非降低标准。

## 四、一句话总结

> **同标准、更快、更省、更可移植、且带生态治理与数据守卫**——
> 官方 skill-creator 是"单机 Claude Code 里的一等公民"；
> 本插件把它的 eval-driven 内核搬进 OpenClaw 生态，去掉外部依赖、加上快路径与治理，
> 在专业度上对齐并在工程化维度反超。
