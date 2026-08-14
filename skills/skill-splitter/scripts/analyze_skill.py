#!/usr/bin/env python3
"""Analyze a large skill package: size, module boundaries, import graph, hot spots.

Usage:
    python3 analyze_skill.py --path {TARGET_SKILL_DIR} [--output analysis.json]

Output:
    JSON report with size metrics, per-module stats, import dependencies,
    latency hot spots, and threshold alarms.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

THRESHOLDS = {
    "file_count": 20,
    "code_lines": 5000,
    "skill_md_lines": 500,
    "min_runtime_minutes": 10,
}

# 耗时热点模式：sleep / 批处理循环 / 外部调用
HOTSPOT_PATTERNS = [
    (re.compile(r"\btime\.sleep\s*\("), "sleep 调用"),
    (re.compile(r"for\s+\w+\s+in\s+(range|tqdm)"), "批处理循环"),
    (re.compile(r"(urlopen|requests\.(get|post|put|delete)|get\(|post\()"), "外部 HTTP 调用"),
    (re.compile(r"(分钟|分钟\s*$|hours?|minutes?)"), "耗时描述"),
    (re.compile(r"sessions_spawn|runTimeoutSeconds"), "异步执行"),
    (re.compile(r"BATCH_SIZE|batch_size|chunk"), "分批处理"),
]

EXCLUDE_DIRS = {"__pycache__", ".git", "node_modules"}
EXCLUDE_FILES = {"__init__.py"}


def _iter_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for name in filenames:
            p = Path(dirpath) / name
            if p.name in EXCLUDE_FILES:
                continue
            files.append(p)
    return files


def _count_lines(path: Path) -> int:
    try:
        return sum(1 for _ in path.open(encoding="utf-8", errors="ignore"))
    except OSError:
        return 0


def _imports_of(path: Path) -> set[str]:
    """Extract top-level module names this file imports."""
    imports: set[str] = set()
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except (SyntaxError, OSError):
        return imports
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
    return imports


def _scan_hotspots(path: Path) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return dict(counts)
    for pattern, label in HOTSPOT_PATTERNS:
        counts[label] += len(pattern.findall(text))
    return dict(counts)


def _relative(root: Path, p: Path) -> str:
    return str(p.relative_to(root))


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze a large skill package.")
    parser.add_argument("--path", required=True, help="Target skill directory")
    parser.add_argument("--output", default=None, help="Output JSON path")
    args = parser.parse_args()

    root = Path(args.path).resolve()
    if not root.is_dir():
        print(f"ERROR: {root} is not a directory", file=sys.stderr)
        return 2

    files = _iter_files(root)
    if not files:
        print(f"ERROR: no files found under {root}", file=sys.stderr)
        return 2

    skill_md = root / "SKILL.md"
    skill_md_exists = skill_md.is_file()

    # 1. 规模统计
    total_lines = sum(_count_lines(f) for f in files)
    py_files = [f for f in files if f.suffix == ".py"]
    py_lines = sum(_count_lines(f) for f in py_files)

    # 2. 按目录分组统计模块规模
    # 规则：只有"目录"才作为模块分组（含其子目录递归）；
    # 单文件（如 modules/_path_setup.py、scripts/deploy.sh）归入其父目录组或 (root)。
    module_stats: dict[str, dict] = {}
    for f in files:
        rel = _relative(root, f)
        parts = Path(rel).parts
        # 找到第一个"目录"层级作为模块边界：parts[0] 是顶级目录（modules/scripts/references）
        if len(parts) >= 2:
            # 若 parts[1] 也是目录（如 modules/pipeline/xx.py），模块 = parts[0]/parts[1]
            top_dir = root / parts[0]
            second_is_dir = len(parts) >= 2 and (root / parts[0] / parts[1]).is_dir()
            if second_is_dir:
                module_key = str(Path(parts[0]) / parts[1])
            else:
                # 单文件直接挂在顶级目录下（modules/_path_setup.py → modules）
                module_key = parts[0]
        else:
            module_key = "(root)"
        if module_key not in module_stats:
            module_stats[module_key] = {"files": 0, "lines": 0, "py_files": 0}
        module_stats[module_key]["files"] += 1
        module_stats[module_key]["lines"] += _count_lines(f)
        if f.suffix == ".py":
            module_stats[module_key]["py_files"] += 1

    # 3. import 依赖图（Python 文件之间）
    py_relative = [_relative(root, f) for f in py_files]
    dep_graph: dict[str, list[str]] = {}
    for f in py_files:
        rel = _relative(root, f)
        own_imports = _imports_of(f)
        deps = sorted(
            i for i in own_imports if i in {Path(r).stem for r in py_relative} or i in {Path(r).name for r in py_relative}
        )
        # 也匹配同包内模块名
        deps = sorted(
            dep for dep in own_imports
            if any(Path(r).stem == dep or Path(r).parent.name == dep for r in py_relative)
        )
        dep_graph[rel] = deps

    # 4. 耗时热点聚合
    hot_spots: Counter = Counter()
    hotspot_files: dict[str, int] = {}
    for f in files:
        if f.suffix != ".py":
            continue
        counts = _scan_hotspots(f)
        total = sum(counts.values())
        if total > 0:
            hot_spots.update(counts)
            hotspot_files[_relative(root, f)] = total

    # 5. 阈值告警
    alarms: list[str] = []
    if len(files) > THRESHOLDS["file_count"]:
        alarms.append(f"文件数 {len(files)} > {THRESHOLDS['file_count']}")
    if py_lines > THRESHOLDS["code_lines"]:
        alarms.append(f"代码行数 {py_lines} > {THRESHOLDS['code_lines']}")
    if skill_md_exists and _count_lines(skill_md) > THRESHOLDS["skill_md_lines"]:
        alarms.append(f"SKILL.md {_count_lines(skill_md)} 行 > {THRESHOLDS['skill_md_lines']}")
    if sum(hot_spots.values()) >= 3:
        alarms.append(f"耗时热点命中 {sum(hot_spots.values())} 次（sleep/批处理/外部调用）")

    report = {
        "skill_dir": str(root),
        "has_skill_md": skill_md_exists,
        "size": {
            "total_files": len(files),
            "total_lines": total_lines,
            "py_files": len(py_files),
            "py_lines": py_lines,
            "skill_md_lines": _count_lines(skill_md) if skill_md_exists else 0,
        },
        "modules": {
            k: v for k, v in sorted(module_stats.items(), key=lambda x: -x[1]["lines"])
        },
        "dependency_graph": dep_graph,
        "hot_spots": dict(hot_spots.most_common()),
        "hotspot_files": dict(sorted(hotspot_files.items(), key=lambda x: -x[1])),
        "alarms": alarms,
        "thresholds": THRESHOLDS,
        "split_recommended": len(alarms) > 0,
    }

    if args.output:
        out = Path(args.output)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"分析报告已写入: {out}")
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))

    print(f"\n结论: {'⚠️ 建议拆解（' + str(len(alarms)) + ' 项超阈值）' if report['split_recommended'] else '✅ 规模合理，不建议拆分'}")
    return 0 if report["split_recommended"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
