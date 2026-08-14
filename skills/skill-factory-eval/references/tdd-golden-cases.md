# TDD Golden Cases 写法（把 Skill 当代码用测试驱动）

对标官方 skill-creator 的 eval-driven 流派：**先写会失败的用例，再逼 description 通过**。

## eval set 结构

```json
[
  {"query": "帮我创建一个自动填报销的 skill", "should_trigger": true,  "source": "primary_intent"},
  {"query": "生成一个技能脚手架",              "should_trigger": true,  "source": "paraphrase"},
  {"query": "scaffold a new skill for me",     "should_trigger": true,  "source": "english"},
  {"query": "评估我现有 skill 的质量",         "should_trigger": false, "source": "boundary_assessor"},
  {"query": "帮我安装一个开源 skill",          "should_trigger": false, "source": "boundary_install"},
  {"query": "写一段排序算法",                   "should_trigger": false, "source": "unrelated"}
]
```

## 写正例（should_trigger=true）——覆盖"意图的多种表述"

- **主意图**：最典型的一句话需求。
- **同义改写**：换动词/换语序/口语化（"帮我搞个…" vs "生成…"）。
- **跨语言**：中文 + 英文各来一条（本插件三模板支持中/英/混合）。
- **场景化**：带上真实上下文（"这是报销工具截图，帮我做个 skill"）。

至少 **3 条正例**，越贴近真实用户越好，别只抄 description 里的词。

## 写反例（should_trigger=false）——覆盖"相邻但不该触发"

反例决定 **precision**。必须为 `Do NOT use for` 的**每一条**写一个反例：

- **兄弟 skill 边界**：属于 assessor/splitter/find-skills 的活儿。
- **同词不同意**：含相同关键词但意图不同（"skill" 出现但其实是问篮球技巧）。
- **完全无关**：普通编码问题，用来压误触发。

至少 **3 条反例**，且尽量"贴边"——贴边的反例才最能暴露 description 的边界模糊。

## TDD 节奏

1. **先红**：写完正/反例，第一次跑分大概率有 FAIL（description 还没调好）。
2. **再绿**：进优化循环，改 description 直到 train 全过。
3. **防退化**：以后每次改 description，都重跑这套 golden case，确保不回退。

## 反过拟合红线

- **不要**把失败的 query 逐字塞进 description。要**泛化成意图类别**。
- 用 train/test 分割 + 按 test 选最优（见 eval-loop.md）来兜底。
