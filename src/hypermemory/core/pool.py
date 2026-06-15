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
