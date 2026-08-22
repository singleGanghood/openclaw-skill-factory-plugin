#!/usr/bin/env python3
"""
static_trigger_score.py — 快路径：零模型调用的静态触发力分析。

这是本插件相对 Anthropic 官方 skill-creator 的核心提速点：官方每轮都要真实起
`claude -p` 子进程跑 eval，而本脚本用纯静态启发式在毫秒内估算一个 description 的
"触发力"，先淘汰绝大多数弱候选，只有得分足够高的才值得进入昂贵的动态跑分。

零第三方依赖：自行解析 frontmatter（不依赖 pyyaml），只用标准库。

用法：
    python3 static_trigger_score.py <path/to/SKILL.md>
输出：JSON，含 score(0-100)、各维度明细、optimization_hints。
退出码：score>=70 => 0（建议进慢路径）；否则 1（建议先回喂优化）。
"""
import json
import re
import sys
from pathlib import Path

PASS_THRESHOLD = 70

# 口语化 / 意图导向触发信号（中英）
IMPERATIVE_HINTS = [
    "use this skill", "always invoke", "always use", "trigger when", "use when",
    "帮我", "请", "怎么", "如何", "想要", "需要", "给我",
]
# 明确的排除边界信号（含“不用于 / Do NOT use for”等中英措辞）
EXCLUSION_HINTS = [
    "do not use", "do not use for", "don't use", "not for", "not intended for",
    "不适用", "不要用", "禁止用于", "不用于", "而不是",
]
# 中英文引号：ASCII 单双引号 + 中文全角引号 + 直角引号
QUOTE_PATTERNS = [
    r"'([^']+)'",
    r'"([^"]+)"',
    r"\u201c([^\u201d]+)\u201d",
    r"\u2018([^\u2019]+)\u2019",
    r"「([^」]+)」",
    r"『([^』]+)』",
]


def parse_frontmatter(text: str):
    """返回 (frontmatter_dict_like, body)。极简解析，够本脚本用。"""
    if not text.startswith("---"):
        return {}, text
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.DOTALL)
    if not m:
        return {}, text
    fm_raw, body = m.group(1), m.group(2)
    fm = {}
    # 抓取顶层 name / description（description 可能是单行引号或 | 块）
    name_m = re.search(r"^name:\s*(.+)$", fm_raw, re.MULTILINE)
    if name_m:
        fm["name"] = name_m.group(1).strip().strip('"').strip("'")
    # description: 单行
    desc_line = re.search(r"^description:\s*(?![|>-])(.+)$", fm_raw, re.MULTILINE)
    # description: | / |- / > / >- 块（兼容 YAML 折叠标记 -）
    desc_block = re.search(r"^description:\s*[|>]-?\s*\n((?:[ \t]+.*\n?)+)", fm_raw, re.MULTILINE)
    if desc_block:
        block = desc_block.group(1)
        # 去掉每行前导缩进
        lines = [ln.strip() for ln in block.splitlines()]
        fm["description"] = " ".join([l for l in lines if l])
    elif desc_line:
        fm["description"] = desc_line.group(1).strip().strip('"').strip("'")
    else:
        fm["description"] = ""
    return fm, body


def count_trigger_keywords(desc: str) -> int:
    """统计 description 里被引号包裹的触发短语，兼容中英文引号（如 'create skill'、\"评估skill\"、“分析这个客户”）。"""
    quoted = []
    for pattern in QUOTE_PATTERNS:
        quoted += re.findall(pattern, desc)
    # 过滤掉太长的（那通常不是触发词而是句子）
    kws = [q for q in quoted if 1 <= len(q) <= 40]
    return len(set(k.lower() for k in kws))


def has_any(text: str, needles) -> bool:
    low = text.lower()
    return any(n.lower() in low for n in needles)


def score_skill(skill_md: Path) -> dict:
    text = skill_md.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(text)
    name = fm.get("name", "")
    desc = fm.get("description", "") or ""

    details = {}
    hints = []
    score = 0

    # 维度1：触发关键词数量（0-30）—— 越多可命中的问法越广
    kw = count_trigger_keywords(desc)
    d1 = min(30, kw * 3)
    details["trigger_keywords"] = {"count": kw, "score": d1, "max": 30}
    if kw < 6:
        hints.append(f"触发关键词偏少（{kw} 个）：在 description 里用引号列出 6+ 个真实用户会说的问法（中英混合），覆盖不同表述。")
    score += d1

    # 维度2：祈使/意图导向措辞（0-20）
    imp = has_any(desc, IMPERATIVE_HINTS)
    d2 = 20 if imp else 0
    details["imperative_intent"] = {"present": imp, "score": d2, "max": 20}
    if not imp:
        hints.append("缺少祈使/意图导向措辞：用 'Use this skill when...' / 'ALWAYS invoke...' / '帮我/如何...' 等表达用户意图，而非描述实现。")
    score += d2

    # 维度3：排除边界（0-20）—— 决定 precision，防误触发
    exc = has_any(desc, EXCLUSION_HINTS) or has_any(body, EXCLUSION_HINTS)
    d3 = 20 if exc else 0
    details["exclusion_boundary"] = {"present": exc, "score": d3, "max": 20}
    if not exc:
        hints.append("缺少排除边界：加入 'Do NOT use for ...' / '不适用：...'，明确相邻但不该触发的场景，这是降低误触发（提升 precision）的关键。")
    score += d3

    # 维度4：长度合规（0-15）—— 太短信息不足、太长稀释注意力/超限
    dl = len(desc)
    if dl == 0:
        d4 = 0
    elif dl > 1024:
        d4 = 0
        hints.append(f"description 超硬上限（{dl}>1024 字符），必须压缩。")
    elif dl < 60:
        d4 = 5
        hints.append(f"description 过短（{dl} 字符），信息不足以稳定触发。")
    elif 60 <= dl <= 700:
        d4 = 15
    else:  # 700-1024
        d4 = 10
        hints.append(f"description 偏长（{dl} 字符），建议压到 ~100-200 词以聚焦注意力。")
    details["length"] = {"chars": dl, "score": d4, "max": 15}
    score += d4

    # 维度5：无非法字符 & 命名规范（0-15）
    d5 = 15
    if "<" in desc or ">" in desc:
        d5 -= 8
        hints.append("description 含尖括号 < >（规范禁止），请移除。")
    if name and not re.match(r"^[a-z0-9-]+$", name):
        d5 -= 7
        hints.append(f"name '{name}' 非 kebab-case（应为小写字母/数字/连字符）。")
    d5 = max(0, d5)
    details["hygiene"] = {"score": d5, "max": 15}
    score += d5

    score = min(100, score)
    return {
        "skill": name or skill_md.parent.name,
        "path": str(skill_md),
        "score": score,
        "threshold": PASS_THRESHOLD,
        "pass": score >= PASS_THRESHOLD,
        "recommendation": "proceed_to_dynamic_eval" if score >= PASS_THRESHOLD else "refeed_generator_first",
        "details": details,
        "optimization_hints": hints,
        "description_char_count": len(desc),
    }


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 static_trigger_score.py <path/to/SKILL.md>", file=sys.stderr)
        sys.exit(2)
    p = Path(sys.argv[1])
    if p.is_dir():
        p = p / "SKILL.md"
    if not p.exists():
        print(f"Error: {p} not found", file=sys.stderr)
        sys.exit(2)
    result = score_skill(p)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    sys.exit(0 if result["pass"] else 1)


if __name__ == "__main__":
    main()
