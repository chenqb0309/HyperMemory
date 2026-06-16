"""HyperMemory 核心 — 鏈探索（Chain Exploration）

從一個 node 出發，沿 prenode / nextnodes 遞迴遍歷上下游，
支援 depth 限制、min_weight 過濾、circular reference 安全。
"""

from pathlib import Path

from hypermemory.core.node import parse_frontmatter, extract_title
from hypermemory.core.weight import calc_weight
from hypermemory.core.pool import node_path


def explore_chain(pool, start_node, direction="forward", depth=3, min_weight=0.0):
    """從 start_node 出發遍歷鏈。

    Parameters
    ----------
    pool : Path
        記憶池路徑（字串或 Path 皆可）
    start_node : str
        起始 node 檔名
    direction : str
        "forward" (沿 nextnodes), "backward" (沿 prenode), "both"
    depth : int
        最大遍歷層數（1 = 僅 immediate 鄰居）
    min_weight : float
        最低權重過濾（weight < min_weight 的 node 不回傳）

    Returns
    -------
    dict
        {
            "found": True/False,
            "start_node": str,
            "start_title": str,
            "start_weight": float,
            "chain": [...]          # direction="forward" or "backward"
            "prenodes": [...],      # direction="both"
            "nextnodes": [...],     # direction="both"
        }
    """
    pool = Path(pool)

    # ── 讀取 start node ──────────────────────────────────
    try:
        start_path = node_path(pool, start_node)
    except FileNotFoundError:
        return {"found": False}

    content = start_path.read_text(encoding="utf-8")
    fm = parse_frontmatter(content)
    start_title = extract_title(content)
    start_weight = calc_weight(
        fm.get("intensity", 1),
        fm.get("total_mentions", 0),
        fm.get("timestamp"),
        node_type=fm.get("node_type", "經驗"),
    )

    result = {
        "found": True,
        "start_node": start_node,
        "start_title": start_title,
        "start_weight": round(start_weight, 2),
    }

    if direction == "forward":
        result["chain"] = _traverse_forward(pool, start_node, depth, min_weight)

    elif direction == "backward":
        result["chain"] = _traverse_backward(pool, start_node, depth, min_weight)

    elif direction == "both":
        result["prenodes"] = _traverse_backward(pool, start_node, depth, min_weight)
        result["nextnodes"] = _traverse_forward(pool, start_node, depth, min_weight)

    return result


# ─── Helper: 讀取單一 node metadata ─────────────────────────


def _read_node_metadata(pool, node_name):
    """讀取 node 並回傳 (fm, title, weight)"""
    path = node_path(pool, node_name)
    content = path.read_text(encoding="utf-8")
    fm = parse_frontmatter(content)
    title = extract_title(content)
    weight = calc_weight(
        fm.get("intensity", 1),
        fm.get("total_mentions", 0),
        fm.get("timestamp"),
        node_type=fm.get("node_type", "經驗"),
    )
    return fm, title, weight


# ─── 向前遍歷（沿 nextnodes）─────────────────────────────────


def _traverse_forward(pool, start_node, depth, min_weight):
    """BFS 遍歷 nextnodes 鏈"""
    chain = []
    visited = {start_node}
    queue = [(start_node, 0)]  # (node, current_depth)

    while queue:
        node, d = queue.pop(0)
        if d >= depth:
            continue

        try:
            path = node_path(pool, node)
        except FileNotFoundError:
            continue

        content = path.read_text(encoding="utf-8")
        fm = parse_frontmatter(content)
        next_nodes = fm.get("nextnodes", [])

        for next_node in next_nodes:
            if next_node in visited:
                continue
            visited.add(next_node)

            try:
                next_fm, next_title, next_weight = _read_node_metadata(pool, next_node)
            except FileNotFoundError:
                continue

            if next_weight >= min_weight:
                chain.append({
                    "node": next_node,
                    "weight": round(next_weight, 2),
                    "title": next_title,
                    "intensity": next_fm.get("intensity", 1),
                    "direction": "forward",
                })

            queue.append((next_node, d + 1))

    return chain


# ─── 向後遍歷（沿 prenode）─────────────────────────────────


def _traverse_backward(pool, start_node, depth, min_weight):
    """BFS 遍歷 prenode 鏈"""
    chain = []
    visited = {start_node}
    queue = [(start_node, 0)]

    while queue:
        node, d = queue.pop(0)
        if d >= depth:
            continue

        try:
            path = node_path(pool, node)
        except FileNotFoundError:
            continue

        content = path.read_text(encoding="utf-8")
        fm = parse_frontmatter(content)
        pre_node = fm.get("prenode")

        if pre_node is None or pre_node in visited:
            continue

        visited.add(pre_node)

        try:
            pre_fm, pre_title, pre_weight = _read_node_metadata(pool, pre_node)
        except FileNotFoundError:
            continue

        if pre_weight >= min_weight:
            chain.append({
                "node": pre_node,
                "weight": round(pre_weight, 2),
                "title": pre_title,
                "intensity": pre_fm.get("intensity", 1),
                "direction": "backward",
            })

        queue.append((pre_node, d + 1))

    return chain
