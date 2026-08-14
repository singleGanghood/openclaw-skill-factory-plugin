#!/usr/bin/env python3
"""Generate a split plan for a large skill based on analysis report.

Usage:
    python3 generate_split_plan.py \
        --analysis analysis.json \
        --mode {functional|pipeline|runtime|datasource} \
        [--output split_plan.json]

The plan is a PROPOSAL. The Agent must review it and confirm before applying.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def _slugify(name: str) -> str:
    """Convert any name to kebab-case."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "skill"


def _kebab(name: str) -> str:
    return _slugify(name)


def _build_sub_skill(module_key: str, stats: dict) -> dict:
    """Build a sub-skill draft from a module directory key."""
    # module_key 形如 "modules/pipeline" 或 "modules/candidate_filter"
    parts = Path(module_key).parts
    module_name = parts[-1] if len(parts) > 0 else "core"
    name = _kebab(module_name)
    return {
        "name": name,
        "source_module": module_key,
        "includes": [module_key],
        "files": stats.get("files", 0),
        "lines": stats.get("lines", 0),
        "estimated_duration_minutes": _estimate_duration(stats),
        "status": "proposal",
    }


def _estimate_duration(stats: dict) -> int:
    """Rough duration estimate from lines of code."""
    lines = stats.get("lines", 0)
    if lines >= 2000:
        return 15
    if lines >= 800:
        return 8
    if lines >= 300:
        return 4
    return 2


# 非业务模块：不生成独立子 Skill，归类为共享层/工具层
_SHARED_KEYS = {"(root)"}
_TOOL_KEYS = {"scripts", "tools"}


def _classify(module_key: str, stats: dict | None = None) -> str:
    """返回模块类别: sub（子 Skill）/ shared（共享层）/ tool（工具层）。"""
    if module_key in _SHARED_KEYS:
        return "shared"
    if module_key in _TOOL_KEYS:
        return "tool"
    # modules/ 顶层（如 modules/_path_setup.py）通常是路径引导等公共文件，
    # 当其为薄层（≤2 文件）时归入共享层，不生成独立子 Skill。
    if module_key == "modules" and stats and stats.get("files", 0) <= 2:
        return "shared"
    return "sub"


def _plan_functional(analysis: dict) -> dict:
    """模式 A: 按功能域拆 — 每个模块目录独立成一个子 Skill。"""
    subs = []
    for module_key, stats in sorted(analysis.get("modules", {}).items()):
        if _classify(module_key, stats) != "sub":
            continue
        subs.append(_build_sub_skill(module_key, stats))
    return {
        "mode": "functional",
        "description": "按功能域拆解：每个模块目录成为一个独立子 Skill，互不依赖，可独立触发。",
        "sub_skills": subs,
    }


def _plan_pipeline(analysis: dict) -> dict:
    """模式 B: 按流水线阶段拆 — 依赖 DAG 线性化，加薄编排器。"""
    graph = analysis.get("dependency_graph", {})
    # 拓扑排序（简化：按模块名顺序，实际应由 Agent 依数据流确认）
    subs = []
    for module_key, stats in sorted(analysis.get("modules", {}).items()):
        if _classify(module_key, stats) != "sub":
            continue
        subs.append(_build_sub_skill(module_key, stats))
    return {
        "mode": "pipeline",
        "description": "按流水线阶段拆解：按数据依赖链线性化，首阶段为入口，末阶段为出口，新增薄编排器串联。",
        "orchestrator": {
            "name": _kebab(Path(analysis.get("skill_dir", "")).name) + "-orchestrator",
            "role": "薄编排器：仅负责子 Skill 串联、超时与失败重试，不含业务逻辑",
            "pipeline_order": [s["name"] for s in subs],
        },
        "sub_skills": subs,
    }


def _plan_runtime(analysis: dict) -> dict:
    """模式 C: 按运行类型拆 — 秒级同步 vs 分钟级异步。"""
    # 依据耗时热点文件与 lines 粗分：大模块 → 异步，小模块 → 同步
    hotspot_files = analysis.get("hotspot_files", {})
    heavy_modules = {
        str(Path(f).parent) for f in hotspot_files if hotspot_files[f] >= 3
    }
    subs_sync, subs_async = [], []
    for module_key, stats in sorted(analysis.get("modules", {}).items()):
        if _classify(module_key, stats) != "sub":
            continue
        sub = _build_sub_skill(module_key, stats)
        if module_key in heavy_modules or sub["estimated_duration_minutes"] >= 10:
            sub["execution"] = "async (sessions_spawn 隔离执行)"
            subs_async.append(sub)
        else:
            sub["execution"] = "sync (exec 直接执行)"
            subs_sync.append(sub)
    return {
        "mode": "runtime",
        "description": "按运行类型拆解：短同步任务与长异步任务分离，避免互相阻塞。",
        "sub_skills": subs_sync + subs_async,
    }


def _plan_datasource(analysis: dict) -> dict:
    """模式 D: 按数据源拆 — 不同外部接口域各自独立。"""
    return _plan_functional(analysis) | {
        "mode": "datasource",
        "description": "按数据源拆解：以外部接口/服务域为边界划分（Agent 需核对各模块对接的接口域）。",
    }


PLANNERS = {
    "functional": _plan_functional,
    "pipeline": _plan_pipeline,
    "runtime": _plan_runtime,
    "datasource": _plan_datasource,
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a skill split plan.")
    parser.add_argument("--analysis", required=True, help="analysis.json from analyze_skill.py")
    parser.add_argument("--mode", required=True, choices=sorted(PLANNERS), help="split mode")
    parser.add_argument("--output", default="split_plan.json", help="Output plan JSON path")
    args = parser.parse_args()

    analysis_path = Path(args.analysis)
    if not analysis_path.is_file():
        print(f"ERROR: analysis file not found: {analysis_path}", file=sys.stderr)
        return 2
    analysis = json.loads(analysis_path.read_text(encoding="utf-8"))

    if not analysis.get("split_recommended"):
        print("⚠️ 分析报告未提示拆解必要，仍生成方案供参考。", file=sys.stderr)

    plan = PLANNERS[args.mode](analysis)
    plan["source_skill_dir"] = analysis.get("skill_dir", "")
    plan["shared_dependencies"] = _detect_shared(analysis)
    # 共享层（(root) 下的公共文件）与工具层（scripts/）信息
    plan["shared_layer"] = {
        module_key: stats
        for module_key, stats in analysis.get("modules", {}).items()
        if _classify(module_key, stats) == "shared"
    }
    plan["tool_layer"] = {
        module_key: stats
        for module_key, stats in analysis.get("modules", {}).items()
        if _classify(module_key, stats) == "tool"
    }
    plan["review_required"] = True

    out = Path(args.output)
    out.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"拆解方案已生成: {out}")
    print(f"模式: {plan['mode']} | 子 Skill 数: {len(plan['sub_skills'])}")
    for s in plan["sub_skills"]:
        print(f"  - {s['name']} (模块 {s['source_module']}, ~{s['estimated_duration_minutes']} 分钟)")
    if plan.get("shared_layer"):
        print(f"共享层（保留，不拆分）: {list(plan['shared_layer'].keys())}")
    if plan.get("tool_layer"):
        print(f"工具层（保留，不拆分）: {list(plan['tool_layer'].keys())}")
    if plan.get("shared_dependencies"):
        print(f"共享依赖: {plan['shared_dependencies']}")
    print("\n⚠️ 方案为提案，请 Agent 审阅数据契约、共享依赖与依赖顺序后再执行迁移。")
    return 0


def _detect_shared(analysis: dict) -> list[str]:
    """Detect shared dependencies: files imported by multiple modules."""
    graph = analysis.get("dependency_graph", {})
    importer_count: dict[str, int] = {}
    for importer, deps in graph.items():
        for dep in deps:
            importer_count[dep] = importer_count.get(dep, 0) + 1
    return sorted(k for k, v in importer_count.items() if v >= 2)


if __name__ == "__main__":
    raise SystemExit(main())
