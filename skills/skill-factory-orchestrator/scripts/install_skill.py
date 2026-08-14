#!/usr/bin/env python3
"""
install_skill.py — Skill 幂等安装（idempotent install）。

以 (name, version, contentHash) 为幂等键，做「内容寻址的原子转正 + 查重式治理登记」，
四态收敛：install / noop / upgrade / conflict。多次执行结果收敛到同一状态，
不产生重复副本、不静默覆盖不同内容、绝不触碰运行时 eligible。

对齐插件既有设计：纯标准库、零第三方依赖；contentHash 口径与
governance-registry.md 的 `find -print0 | sort -z | shasum` 语义一致
（此处用 Python 复刻，保证跨平台且无需 shell/xargs）。

四态决策：
    候选 (name, version, hash_new)   目标现状              → action
    ─────────────────────────────────────────────────────────────
    目标不存在                                             → install
    目标存在, hash 相同                                    → noop
    目标存在, hash 不同, version 相同                      → conflict（拒绝，除非 --force）
    目标存在, hash 不同, version 更高                      → upgrade（记 rollbackRef）
    （目标存在, version 更低 → 也判 conflict，防降级覆盖）

用法：
    python3 install_skill.py --staging .skill-factory/staging/<name> \\
        --dest .codebuddy/skills \\
        [--registry .skill-factory/registry.json] \\
        [--assessor-score 85] [--eval-precision 1.0] [--eval-recall 0.9] \\
        [--verified-by orchestrator] [--notes "..."] \\
        [--dry-run] [--force]

退出码：
    0  install / noop / upgrade 成功（或 dry-run 预测为这三者）
    2  conflict（同版本内容漂移或降级），未加 --force
    3  用法/输入错误（路径不存在、name 非法等）
"""
import argparse
import errno
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

KEBAB = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
# 计算 hash 时忽略的噪声文件/目录，保证「同内容永远同 hash」
IGNORE_DIRS = {"__pycache__", ".git", ".DS_Store", "node_modules"}
IGNORE_SUFFIX = {".pyc", ".pyo"}


# ----------------------------- 工具函数 -----------------------------

def die(msg: str, code: int = 3):
    print(json.dumps({"action": "error", "error": msg}, ensure_ascii=False), file=sys.stderr)
    sys.exit(code)


def read_name_from_skill_md(skill_dir: Path) -> str:
    """从 SKILL.md frontmatter 读取 name，作为安装目标名（防止靠目录名猜测）。"""
    md = skill_dir / "SKILL.md"
    if not md.is_file():
        die(f"staging 目录缺少 SKILL.md: {md}")
    text = md.read_text(encoding="utf-8")
    m = re.match(r"^---\n([\s\S]*?)\n---", text)
    if not m:
        die("SKILL.md 缺少/非法 YAML frontmatter")
    nm = re.search(r"^name:\s*(.+)$", m.group(1), re.M)
    if not nm:
        die("SKILL.md frontmatter 缺少 name")
    return nm.group(1).strip()


def iter_content_files(root: Path):
    """稳定顺序遍历 skill 目录内容文件（排除噪声），用于计算 contentHash。"""
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        # 原地过滤忽略目录，保证遍历稳定
        dirnames[:] = sorted(d for d in dirnames if d not in IGNORE_DIRS)
        for fn in filenames:
            if fn in IGNORE_DIRS or Path(fn).suffix in IGNORE_SUFFIX:
                continue
            files.append(Path(dirpath) / fn)
    # 相对路径排序，保证顺序与内容双稳定
    files.sort(key=lambda p: str(p.relative_to(root)).replace(os.sep, "/"))
    return files


def content_hash(root: Path) -> str:
    """
    内容寻址哈希：对「相对路径 + 文件字节」逐个喂入 sha256，最后取总摘要。
    语义等价于 governance-registry.md 的 find|sort|shasum，但纯 Python、跨平台、
    且把路径纳入哈希，避免「文件改名但内容相同」被误判为等价。
    """
    h = hashlib.sha256()
    for f in iter_content_files(root):
        rel = str(f.relative_to(root)).replace(os.sep, "/")
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(hashlib.sha256(f.read_bytes()).digest())
    return "sha256:" + h.hexdigest()


def parse_version(v: str):
    """宽松语义化版本解析，返回可比较元组；非法则返回 None。"""
    if not v:
        return None
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)", v.strip())
    if not m:
        return None
    return tuple(int(x) for x in m.groups())


def version_from_skill(skill_dir: Path, cli_version: str) -> str:
    """版本优先取 CLI，其次取 SKILL.md metadata.openclaw.version，最后默认 0.0.0。"""
    if cli_version:
        return cli_version
    text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    m = re.match(r"^---\n([\s\S]*?)\n---", text)
    if m:
        vm = re.search(r"^\s*version:\s*['\"]?([0-9][^'\"\n]*)", m.group(1), re.M)
        if vm:
            return vm.group(1).strip()
    return "0.0.0"


# ----------------------------- 文件锁 -----------------------------

class DirLock:
    """
    跨平台目录级建议锁：优先 fcntl.flock（POSIX），退化为原子创建 lockfile。
    防止多个会话并发转正同一 skill 造成竞态——幂等在多 agent 场景的必要条件。
    """

    def __init__(self, lock_path: Path):
        self.lock_path = lock_path
        self._fh = None
        self._fd = None
        self._mode = None

    def __enter__(self):
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            import fcntl
            self._fh = open(self.lock_path, "w")
            fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX)
            self._mode = "flock"
        except (ImportError, OSError):
            # 退化：O_CREAT|O_EXCL 原子创建作为互斥标记
            self._fd = os.open(str(self.lock_path), os.O_CREAT | os.O_EXCL | os.O_RDWR)
            self._mode = "excl"
        return self

    def __exit__(self, *exc):
        try:
            if self._mode == "flock" and self._fh is not None:
                import fcntl
                fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
                self._fh.close()
            elif self._mode == "excl" and self._fd is not None:
                os.close(self._fd)
                try:
                    os.unlink(self.lock_path)
                except OSError:
                    pass
        except OSError:
            pass
        return False


# ----------------------------- 原子转正 -----------------------------

def atomic_install(staging: Path, target: Path):
    """
    原子转正：先把内容复制到目标父目录下的临时目录，再 os.replace 整目录替换。
    避免半写状态与「边读边覆盖」。若目标已存在，替换后清理旧目录。
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=f".{target.name}.tmp-", dir=str(target.parent)))
    try:
        # 复制内容到 tmp/<name>
        staged_copy = tmp / target.name
        shutil.copytree(str(staging), str(staged_copy),
                        ignore=shutil.ignore_patterns(*IGNORE_DIRS, "*.pyc", "*.pyo"))
        old_backup = None
        if target.exists():
            old_backup = target.parent / f".{target.name}.old-{os.getpid()}"
            os.replace(str(target), str(old_backup))  # 原子挪走旧的
        os.replace(str(staged_copy), str(target))     # 原子放入新的
        if old_backup and old_backup.exists():
            shutil.rmtree(str(old_backup), ignore_errors=True)
    finally:
        shutil.rmtree(str(tmp), ignore_errors=True)


# ----------------------------- 注册表 -----------------------------

def load_registry(path: Path) -> dict:
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            die(f"registry.json 解析失败: {path}")
        if not isinstance(data, dict) or "records" not in data:
            die("registry.json 结构非法（缺少 records）")
        return data
    return {"version": 1, "records": []}


def find_record(reg: dict, name: str, version: str):
    """返回同 (name, version) 的最新一条 record（或 None）。"""
    matches = [r for r in reg["records"] if r.get("name") == name and r.get("version") == version]
    return matches[-1] if matches else None


def latest_verified(reg: dict, name: str):
    """返回该 name 最近一条 record（用于 rollbackRef）。"""
    matches = [r for r in reg["records"] if r.get("name") == name]
    return matches[-1] if matches else None


def has_identical_record(reg: dict, name: str, version: str, chash: str) -> bool:
    """幂等键查重：是否已存在完全相同的 (name, version, contentHash)。"""
    return any(
        r.get("name") == name and r.get("version") == version and r.get("contentHash") == chash
        for r in reg["records"]
    )


def now_iso() -> str:
    import datetime
    return datetime.datetime.now().astimezone().replace(microsecond=0).isoformat()


def build_record(name, version, chash, args, rollback_ref):
    rec = {
        "name": name,
        "version": version,
        "contentHash": chash,
        "verifiedAt": now_iso(),
        "verifiedBy": args.verified_by,
    }
    if args.assessor_score is not None:
        rec["assessorScore"] = args.assessor_score
    if args.eval_precision is not None:
        rec["evalPrecision"] = args.eval_precision
    if args.eval_recall is not None:
        rec["evalRecall"] = args.eval_recall
    if rollback_ref:
        rec["rollbackRef"] = rollback_ref
    if args.notes:
        rec["notes"] = args.notes
    return rec


# ----------------------------- 决策 -----------------------------

def decide(name, new_version, new_hash, dest_dir: Path, reg: dict, force: bool):
    """内容寻址四态决策。返回 (action, detail)。"""
    target = dest_dir / name
    target_exists = target.exists()

    if not target_exists:
        return "install", {"reason": "目标不存在"}

    # 目标已存在 → 用磁盘现内容算 hash 做内容寻址比对
    existing_hash = content_hash(target)
    if existing_hash == new_hash:
        return "noop", {"reason": "内容一致，已到目标态", "hash": new_hash}

    # 内容不同 → 看版本
    v_new = parse_version(new_version)
    # 现有磁盘版本从其 SKILL.md 读
    existing_version = version_from_skill(target, "")
    v_old = parse_version(existing_version)

    if v_new is None or v_old is None:
        # 版本不可比 → 视为 conflict（除非 force）
        return ("upgrade" if force else "conflict"), {
            "reason": "内容不同且版本不可比较",
            "existing_version": existing_version, "new_version": new_version,
            "existing_hash": existing_hash,
        }

    if v_new == v_old:
        return ("upgrade" if force else "conflict"), {
            "reason": "同版本内容漂移（应 bump 版本）",
            "existing_version": existing_version, "new_version": new_version,
            "existing_hash": existing_hash,
        }
    if v_new > v_old:
        return "upgrade", {
            "reason": "版本升级",
            "existing_version": existing_version, "new_version": new_version,
            "existing_hash": existing_hash,
        }
    # v_new < v_old：降级
    return ("upgrade" if force else "conflict"), {
        "reason": "试图降级安装（版本更低）",
        "existing_version": existing_version, "new_version": new_version,
        "existing_hash": existing_hash,
    }


# ----------------------------- 主流程 -----------------------------

def main():
    ap = argparse.ArgumentParser(description="Skill 幂等安装（内容寻址 + 原子转正 + 查重登记）")
    ap.add_argument("--staging", required=True, help="暂存候选目录（含 SKILL.md）")
    ap.add_argument("--dest", required=True, help="生效目录（skills 根，如 .codebuddy/skills）")
    ap.add_argument("--registry", default=".skill-factory/registry.json", help="治理注册表路径")
    ap.add_argument("--version", default="", help="覆盖版本号；默认取 SKILL.md 或 0.0.0")
    ap.add_argument("--assessor-score", type=int, default=None)
    ap.add_argument("--eval-precision", type=float, default=None)
    ap.add_argument("--eval-recall", type=float, default=None)
    ap.add_argument("--verified-by", default="orchestrator")
    ap.add_argument("--notes", default="")
    ap.add_argument("--dry-run", action="store_true", help="只输出决策，零副作用")
    ap.add_argument("--force", action="store_true", help="仅在 conflict 时允许显式覆盖")
    ap.add_argument("--no-register", action="store_true", help="只转正磁盘，不写注册表")
    args = ap.parse_args()

    staging = Path(args.staging).resolve()
    if not staging.is_dir():
        die(f"staging 目录不存在: {staging}")

    name = read_name_from_skill_md(staging)
    if not KEBAB.match(name):
        die(f"skill name 非 kebab-case，拒绝安装: {name}")

    dest_dir = Path(args.dest).resolve()
    # 路径安全：目标必须落在 dest_dir 内，防目录穿越
    target = (dest_dir / name).resolve()
    if os.path.commonpath([str(dest_dir), str(target)]) != str(dest_dir):
        die(f"目标路径越界（疑似目录穿越）: {target}")

    version = version_from_skill(staging, args.version)
    new_hash = content_hash(staging)

    registry_path = Path(args.registry).resolve()
    reg = load_registry(registry_path)

    action, detail = decide(name, version, new_hash, dest_dir, reg, args.force)

    result = {
        "action": action,
        "name": name,
        "version": version,
        "contentHash": new_hash,
        "dest": str(target),
        "registry": str(registry_path),
        "dry_run": bool(args.dry_run),
        "detail": detail,
    }

    # conflict：拒绝落盘
    if action == "conflict":
        result["hint"] = "内容与已安装版本不同：请 bump 版本号后重试，或显式加 --force 覆盖。"
        print(json.dumps(result, indent=2, ensure_ascii=False))
        sys.exit(2)

    # noop：已到目标态，做幂等登记查重后直接退出
    if action == "noop":
        result["registered"] = False
        if not args.dry_run and not args.no_register:
            if not has_identical_record(reg, name, version, new_hash):
                # 磁盘一致但注册表缺记录 → 补一条（仍幂等：内容相同不会重复）
                rec = build_record(name, version, new_hash, args, None)
                reg["records"].append(rec)
                registry_path.parent.mkdir(parents=True, exist_ok=True)
                registry_path.write_text(
                    json.dumps(reg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                result["registered"] = True
                result["record"] = rec
        print(json.dumps(result, indent=2, ensure_ascii=False))
        sys.exit(0)

    # install / upgrade（或 force）
    if args.dry_run:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        sys.exit(0)

    lock = dest_dir / f".{name}.lock"
    with DirLock(lock):
        # 加锁后重新决策一次，防 TOCTOU 竞态
        action2, detail2 = decide(name, version, new_hash, dest_dir, reg, args.force)
        if action2 == "noop":
            result.update({"action": "noop", "detail": detail2,
                           "note": "并发下另一进程已安装相同内容"})
            print(json.dumps(result, indent=2, ensure_ascii=False))
            sys.exit(0)
        if action2 == "conflict":
            result.update({"action": "conflict", "detail": detail2})
            print(json.dumps(result, indent=2, ensure_ascii=False))
            sys.exit(2)

        rollback_ref = None
        if action2 == "upgrade":
            prev = latest_verified(reg, name)
            if prev:
                rollback_ref = f"{prev['name']}@{prev['version']}"

        atomic_install(staging, target)
        result["action"] = action2
        result["installed"] = True

        # 幂等登记：查重后追加
        result["registered"] = False
        if not args.no_register:
            if not has_identical_record(reg, name, version, new_hash):
                rec = build_record(name, version, new_hash, args, rollback_ref)
                reg["records"].append(rec)
                registry_path.parent.mkdir(parents=True, exist_ok=True)
                registry_path.write_text(
                    json.dumps(reg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                result["registered"] = True
                result["record"] = rec

    print(json.dumps(result, indent=2, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()
