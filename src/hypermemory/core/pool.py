"""HyperMemory 核心 — 記憶池路徑與目錄操作"""

import os
from pathlib import Path

# 預設記憶池路徑：~/.hypermemory/pools/default/
DEFAULT_POOL = Path.home() / ".hypermemory" / "pools" / "default"


def resolve_pool(pool_path=None):
    """解析記憶池路徑。優先順序：參數 > HYPERMEMORY_POOL 環境變數 > 預設路徑。

    回傳 Path 物件。不檢查目錄是否存在（由 ensure_pool 負責建立）。
    """
    path_str = pool_path or os.environ.get("HYPERMEMORY_POOL")
    if path_str:
        return Path(path_str).resolve()
    return DEFAULT_POOL


def ensure_pool(pool):
    """確保記憶池目錄與 index.md 存在。若不存在則自動建立。"""
    created = False
    if not pool.exists():
        pool.mkdir(parents=True, exist_ok=True)
        created = True

    idx = pool / "index.md"
    if not idx.exists():
        with open(idx, "w", encoding="utf-8") as f:
            f.write("# HyperMemory Pool Index\n\n")
        created = True

    return created


def index_path(pool):
    """回傳 index.md 的完整路徑"""
    return pool / "index.md"


def list_nodes(pool):
    """列出記憶池中所有 node 檔案（排除 index.md）"""
    nodes = []
    for f in sorted(pool.glob("*.md")):
        if f.name == "index.md":
            continue
        nodes.append(f)
    return nodes


def node_path(pool, name):
    """回傳指定 node 的完整路徑"""
    p = pool / name
    if not p.exists():
        p2 = pool / f"{name}.md"
        if p2.exists():
            return p2
        raise FileNotFoundError(f"Node not found: {name}")
    return p


def resolve_chain_length(pool, node_name, fm, max_depth=5):
    """計算 node 在 chain 中的長度（含自身），供 chain_boost 使用。

    往前追溯 prenode，往後走訪 nextnodes（BFS），
    以 max_depth 防止過度 I/O。
    回傳 int >= 1。

    使用方式：
      chain_length = resolve_chain_length(pool, node_name, fm)
      calc_weight(..., chain_length=chain_length)
    """
    from hypermemory.core.node import parse_frontmatter

    pool = Path(pool)
    count = 1

    # 往前追溯
    current = fm.get("prenode")
    d = 0
    while current and d < max_depth:
        count += 1
        d += 1
        try:
            p = node_path(pool, current)
            c = p.read_text(encoding="utf-8")
            f = parse_frontmatter(c)
            current = f.get("prenode")
        except (FileNotFoundError, Exception):
            break

    # 往後走訪（BFS）
    visited = {node_name}
    queue = list(fm.get("nextnodes", []) or [])
    d = 0
    while queue and d < max_depth:
        nxt = queue.pop(0)
        if nxt in visited:
            continue
        visited.add(nxt)
        count += 1
        d += 1
        try:
            p = node_path(pool, nxt)
            c = p.read_text(encoding="utf-8")
            f = parse_frontmatter(c)
            for nn in (f.get("nextnodes", []) or []):
                if nn not in visited and nn not in queue:
                    queue.append(nn)
        except (FileNotFoundError, Exception):
            break

    return count
