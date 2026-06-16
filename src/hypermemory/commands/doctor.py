"""hm doctor — 系統自我診斷"""

import sys
import os
import json
import re
from pathlib import Path
from datetime import datetime, timezone
from importlib.metadata import version as pkg_version, PackageNotFoundError

from hypermemory.core.pool import resolve_pool, index_path, list_nodes
from hypermemory.core.index import parse_index
from hypermemory.core.node import parse_frontmatter
from hypermemory.commands.daemon import _pid_path
from hypermemory.core.muscle_memory import SKILL_READY_EXPIRE_DAYS


def run_doctor(pool_path=None) -> dict:
    """執行系統自我診斷，回傳結構化結果 dict。

    檢查項目：
    - HM 版本（from importlib.metadata）
    - Python 版本（>= 3.10）
    - 記憶池是否存在
    - index.md 是否存在
    - node 檔案完整性（index 條目對應的檔案是否都存在）
    - dead refs 數量（index 指向不存在的 node）
    - orphan nodes 數量（存在但不在 index 中的 node 檔案）
    - archive_index.md 是否存在 + 歸檔數量
    - background/ 目錄是否存在 + 分類
    - skill_ready 過期標記（超過 SKILL_READY_EXPIRE_DAYS 未轉換）
    - daemon 是否在執行（check PID file + kill(0)）
    """
    # Convert str to Path
    if isinstance(pool_path, str):
        pool_path = Path(pool_path)

    # ── Version ────────────────────────────────────────
    try:
        ver = pkg_version("hypermemory")
    except PackageNotFoundError:
        ver = "unknown"

    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    # ── Pool existence ─────────────────────────────────
    pool_exists = pool_path is not None and pool_path.exists()

    # ── Index ──────────────────────────────────────────
    index_exists = False
    idx = None
    if pool_exists:
        idx = index_path(pool_path)
        index_exists = idx.exists()

    entries = []
    if index_exists:
        content = idx.read_text(encoding="utf-8")
        entries = parse_index(content)

    # ── Nodes ──────────────────────────────────────────
    nodes = []
    if pool_exists:
        nodes = list_nodes(pool_path)
    node_count = len(nodes)

    # ── Dead refs ──────────────────────────────────────
    dead_ref_nodes = []
    for _kw_list, node_file in entries:
        np = pool_path / node_file
        if not np.exists():
            dead_ref_nodes.append(node_file)
    dead_refs = len(dead_ref_nodes)

    # ── Orphan nodes ───────────────────────────────────
    indexed_files = {node_file for _, node_file in entries}
    orphan_nodes_list = []
    for n in nodes:
        if n.name not in indexed_files:
            orphan_nodes_list.append(n.name)
    orphan_nodes = len(orphan_nodes_list)

    # ── Archive ────────────────────────────────────────
    archive_exists = False
    archived_nodes = 0
    if pool_exists:
        archive_path = pool_path / "archive_index.md"
        archive_exists = archive_path.exists()
        if archive_exists:
            archive_content = archive_path.read_text(encoding="utf-8")
            archived_entries = parse_index(archive_content)
            archived_nodes = len(archived_entries)

    # ── Background ─────────────────────────────────────
    background_exists = False
    background_categories = {}
    if pool_exists:
        bg_dir = pool_path / "background"
        background_exists = bg_dir.exists()
        if background_exists:
            for f in sorted(bg_dir.glob("*.json")):
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    entries_list = data.get("entries", [])
                    cat = data.get("category", f.stem)
                    background_categories[cat] = len(entries_list)
                except (json.JSONDecodeError, OSError):
                    pass

    # ── Stale skill_ready ──────────────────────────────
    stale_skill_ready = 0
    now = datetime.now(timezone.utc)
    for n in nodes:
        try:
            content = n.read_text(encoding="utf-8")
            fm = parse_frontmatter(content)

            # Check if skill_ready is set — search frontmatter first,
            # then raw content (e.g. if appending after ---)
            skill_ready = fm.get("skill_ready")
            if not skill_ready:
                # Check raw content: 'skill_ready: true' anywhere
                if re.search(r"skill_ready:\s*true", content):
                    skill_ready = True

            if not skill_ready:
                continue

            # Extract skill_ready_at — frontmatter first, then raw content
            ready_at = fm.get("skill_ready_at")
            if not ready_at:
                m = re.search(r"skill_ready_at:\s*(.+)", content)
                if m:
                    ready_at = m.group(1).strip()

            should_expire = False

            # Primary: skill_ready_at
            if ready_at:
                try:
                    ts = datetime.fromisoformat(ready_at)
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                    if (now - ts).days >= SKILL_READY_EXPIRE_DAYS:
                        should_expire = True
                except (ValueError, TypeError):
                    pass

            # Secondary: node's own timestamp
            if not should_expire:
                node_ts = fm.get("timestamp")
                if node_ts:
                    try:
                        ts = datetime.fromisoformat(node_ts)
                        if ts.tzinfo is None:
                            ts = ts.replace(tzinfo=timezone.utc)
                        if (now - ts).days >= SKILL_READY_EXPIRE_DAYS:
                            should_expire = True
                    except (ValueError, TypeError):
                        pass

            if should_expire:
                stale_skill_ready += 1
        except (OSError, Exception):
            pass

    # ── Daemon status ──────────────────────────────────
    daemon_running = False
    try:
        pid_path = _pid_path()
        if pid_path.exists():
            pid = int(pid_path.read_text().strip())
            os.kill(pid, 0)
            daemon_running = True
    except (OSError, ValueError, FileNotFoundError):
        pass

    # ── Issues ─────────────────────────────────────────
    issues = []
    if not pool_exists:
        issues.append(f"Pool does not exist: {pool_path}")
    if not index_exists:
        issues.append("index.md not found")
    if dead_refs > 0:
        refs_str = ", ".join(dead_ref_nodes[:5])
        if len(dead_ref_nodes) > 5:
            refs_str += f" ... (and {len(dead_ref_nodes) - 5} more)"
        issues.append(
            f"Dead refs: {dead_refs} index entries point to missing nodes ({refs_str})"
        )
    if stale_skill_ready > 0:
        issues.append(
            f"{stale_skill_ready} stale skill_ready mark(s) "
            f"(expired > {SKILL_READY_EXPIRE_DAYS} days)"
        )
    if node_count == 0 and pool_exists:
        issues.append("Pool has no nodes")

    healthy = (
        pool_exists
        and index_exists
        and dead_refs == 0
        and stale_skill_ready == 0
        and node_count > 0
    )

    return {
        "healthy": healthy,
        "version": ver,
        "python": py_ver,
        "pool_exists": pool_exists,
        "pool_path": str(pool_path) if pool_path else "",
        "index_exists": index_exists,
        "node_count": node_count,
        "dead_refs": dead_refs,
        "orphan_nodes": orphan_nodes,
        "archive_exists": archive_exists,
        "archived_nodes": archived_nodes,
        "background_exists": background_exists,
        "background_categories": background_categories,
        "stale_skill_ready": stale_skill_ready,
        "daemon_running": daemon_running,
        "issues": issues,
    }


def run(args):
    """CLI entry point — display formatted doctor report."""
    from hypermemory.core.pool import resolve_pool

    pool = resolve_pool(args.pool)
    result = run_doctor(pool)

    print(f"HyperMemory Doctor Report")
    print(f"========================\n")

    print(f"Version:   {result['version']}  (Python {result['python']})")
    print(f"Pool:      {'✓' if result['pool_exists'] else '✗'} {result['pool_path']}")
    print(f"Index:     {'✓' if result['index_exists'] else '✗'}")
    print(f"  Nodes:   {result['node_count']}")
    print(f"  Dead refs: {result['dead_refs']}")
    print(f"  Orphans: {result['orphan_nodes']}")

    # Archive
    if result.get("archive_exists"):
        print(f"Archived:  {result['archived_nodes']} node(s)")

    # Background
    bg = result.get("background_categories", {})
    if bg:
        cats = ", ".join(f"{k}={v}" for k, v in bg.items())
        print(f"Background: {cats}")

    # Stale skill_ready
    stale = result.get("stale_skill_ready", 0)
    if stale:
        print(f"⚠ Stale skill_ready: {stale}")

    # Daemon
    daemon_status = "running" if result.get("daemon_running") else "stopped"
    print(f"Daemon:    {daemon_status}")

    # Issues
    issues = result.get("issues", [])
    if issues:
        print(f"\nIssues:")
        for issue in issues:
            print(f"  ✗ {issue}")

    # Final verdict
    print(f"\nVerdict: {'HEALTHY ✓' if result['healthy'] else 'ISSUES FOUND ✗'}")
