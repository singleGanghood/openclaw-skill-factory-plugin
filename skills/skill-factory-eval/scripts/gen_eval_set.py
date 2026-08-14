#!/usr/bin/env python3
"""
gen_eval_set.py — 从 SKILL.md 生成 TDD eval set 骨架（正例 + 反例）。

零第三方依赖。它不"编造"最终 eval，而是从 description / When to Use / Do NOT use for
抽取信号，产出一个待补全的骨架，提示作者/subagent 补齐真实问法。

输出 JSON 数组，元素形如：
  {"query": "...", "should_trigger": true,  "source": "trigger_keyword"}
  {"query": "...", "should_trigger": false, "source": "exclusion_boundary"}

用法：
    python3 gen_eval_set.py <path/to/SKILL.md> [--min-pos 3] [--min-neg 3]
"""
import argparse
import json
import re
import sys
from pathlib import Path


def parse_frontmatter(text: str):
    if not text.startswith("---"):
        return {}, text
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.DOTALL)
    if not m:
        return {}, text
    fm_raw, body = m.group(1), m.group(2)
    fm = {}
    name_m = re.search(r"^name:\s*(.+)$", fm_raw, re.MULTILINE)
    if name_m:
        fm["name"] = name_m.group(1).strip().strip('"').strip("'")
    desc_block = re.search(r"^description:\s*[|>]\s*\n((?:[ \t]+.*\n?)+)", fm_raw, re.MULTILINE)
    desc_line = re.search(r"^description:\s*(?![|>])(.+)$", fm_raw, re.MULTILINE)
    if desc_block:
        lines = [ln.strip() for ln in desc_block.group(1).splitlines()]
        fm["description"] = " ".join([l for l in lines if l])
    elif desc_line:
        fm["description"] = desc_line.group(1).strip().strip('"').strip("'")
    else:
        fm["description"] = ""
    return fm, body


def extract_quoted(desc: str):
    q = re.findall(r"'([^']+)'", desc) + re.findall(r'"([^"]+)"', desc)
    return [x for x in q if 1 <= len(x) <= 40]


def extract_exclusions(desc: str, body: str):
    """抓取 'Do NOT use for X' / '不适用：X' 后面的短语作为反例线索。"""
    text = desc + "\n" + body
    hints = []
    for pat in [
        r"[Dd]o NOT use (?:this skill )?for ([^.\n;]+)",
        r"[Dd]on't use (?:this skill )?for ([^.\n;]+)",
        r"不适用[:：]?\s*([^。\n;]+)",
        r"不要用于\s*([^。\n;]+)",
        r"而不是\s*([^。\n;]+)",
    ]:
        for m in re.findall(pat, text):
            frag = m.strip().strip("、,")
            if 2 <= len(frag) <= 60:
                hints.append(frag)
    return hints


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("skill_md")
    ap.add_argument("--min-pos", type=int, default=3)
    ap.add_argument("--min-neg", type=int, default=3)
    args = ap.parse_args()

    p = Path(args.skill_md)
    if p.is_dir():
        p = p / "SKILL.md"
    if not p.exists():
        print(f"Error: {p} not found", file=sys.stderr)
        sys.exit(2)

    fm, body = parse_frontmatter(p.read_text(encoding="utf-8"))
    name = fm.get("name", p.parent.name)
    desc = fm.get("description", "")

    positives = []
    for kw in dict.fromkeys(extract_quoted(desc)):  # 去重保序
        positives.append({
            "query": kw if len(kw) > 6 else f"帮我{kw}",
            "should_trigger": True,
            "source": "trigger_keyword",
            "_needs_review": True,
        })

    negatives = []
    for ex in dict.fromkeys(extract_exclusions(desc, body)):
        negatives.append({
            "query": ex,
            "should_trigger": False,
            "source": "exclusion_boundary",
            "_needs_review": True,
        })

    eval_set = positives + negatives
    warnings = []
    if len(positives) < args.min_pos:
        warnings.append(f"正例不足（{len(positives)}<{args.min_pos}）：请补足真实用户会说的多样问法。")
    if len(negatives) < args.min_neg:
        warnings.append(f"反例不足（{len(negatives)}<{args.min_neg}）：请为 'Do NOT use for' 的每条边界补相邻易混淆问法。")

    out = {
        "skill": name,
        "eval_set": eval_set,
        "counts": {"positive": len(positives), "negative": len(negatives)},
        "warnings": warnings,
        "note": "这是骨架。_needs_review=true 的条目需人工/subagent 改写为自然、真实的用户问法后再跑动态 eval。",
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
