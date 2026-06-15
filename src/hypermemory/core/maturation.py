"""HyperMemory 核心 — Maturation Score（經驗成熟度）

三因子累積公式：

  maturation = base_intensity × confirmation_ratio × time_matured

  confirmation_ratio = (positive_events + 1) / (total_events + 1)
  total_events = positive_events + negative_events (in matched context only)

  time_matured:
    1.0  → 存在 >= 30 天
    0.8  → 存在 >= 14 天
    0.5  → 存在 < 14 天

確認事件 (confirmation event) 儲存在 pool 的 confirm/ 子目錄中，
作為獨立的 node 檔案，透過 frontmatter 中的 source 指向被確認的源 node。

只有通過 5M1E 維度匹配的事件才會計入 confirmation_ratio。
"""

import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from hypermemory.core.node import parse_frontmatter, extract_title
from hypermemory.core.dimensions import (
    DIMENSION_KEYS,
    is_compatible,
    parse_dimensions,
    format_dimensions,
)

# ─── 確認事件檔案格式 ──────────────────────────────────

CONFIRM_DIR = "confirm"

CONFIRM_TEMPLATE = """---
type: confirmation_event
timestamp: {timestamp}
source: {source_node}
result: {result}
agent: {agent}
dimensions:
{dimensions_yaml}
context_summary: {context_summary}
---
"""


def _dimensions_to_yaml(dims):
    """將 dimensions dict 轉為 YAML 子區塊"""
    if not dims:
        return ""
    lines = []
    for key in DIMENSION_KEYS:
        val = dims.get(key)
        if val:
            lines.append(f"  {key}: {val}")
    return "\n".join(lines)


def _confirm_dir(pool_path):
    """確認事件儲存目錄"""
    d = Path(pool_path) / CONFIRM_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def _parse_dimensions_from_fm_text(fm_text):
    """從 frontmatter 文字中解析 dimensions 子 dict。

    格式：
    ```
    dimensions:
      機: WSL
      料: Python 3.11
    ```
    """
    dims = {}
    m = re.search(r"^dimensions:\s*$", fm_text, re.MULTILINE)
    if not m:
        return dims
    after = fm_text[m.end():]
    for line in after.split("\n"):
        em = re.match(r"^\s+(\S):\s*(.+)$", line)
        if em:
            dims[em.group(1)] = em.group(2).strip()
        elif line.strip() and not line.startswith(" ") and ":" in line:
            # 已離開 dimensions 區塊
            break
    return dims


def _parse_confirm_node(content):
    """解析確認事件 node，回傳 dict。"""
    # 通用解析：提取 frontmatter 中所有簡單 scalar 欄位
    fm = {}
    fm_match = re.search(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
    if fm_match:
        fm_text = fm_match.group(1)
        for line in fm_text.split("\n"):
            m = re.match(r'^(\w+):\s*(.+)$', line)
            if m:
                fm[m.group(1)] = m.group(2).strip()
            elif m is None and ":" in line and not line.startswith(" "):
                # 遇到非 key:value 格式的行（可能是維度區塊結束）
                pass

    # 特別處理 dimensions
    dims = _parse_dimensions_from_fm_text(fm_match.group(1)) if fm_match else {}

    return {
        "source": fm.get("source", ""),
        "result": fm.get("result", ""),
        "agent": fm.get("agent", "unknown"),
        "timestamp": fm.get("timestamp", ""),
        "dimensions": dims,
        "context_summary": fm.get("context_summary", ""),
    }


# ─── 建立確認事件 ──────────────────────────────────


def create_confirmation(pool_path, source_node, result, agent="unknown",
                        context_summary="", dimensions=None):
    """建立一個確認事件 node。

    參數：
    - pool_path: str/Path — 記憶池路徑
    - source_node: str — 被確認的源 node 檔名（如 "2026-06-15-build-env.md"）
    - result: str — "positive" | "negative" | "neutral"
    - agent: str — 回報 agent 名稱
    - context_summary: str — 驗證 context 摘要
    - dimensions: dict — 驗證時的環境維度

    回傳 dict: {success, confirmation_id, error?}
    """
    if result not in ("positive", "negative", "neutral"):
        return {"success": False, "error": f"Invalid result: {result}"}

    # 確認源 node 存在
    source_path = Path(pool_path) / source_node
    if not source_path.exists():
        return {"success": False, "error": f"Source node not found: {source_node}"}

    # 建立檔名
    now = datetime.now(timezone.utc)
    ts_str = now.strftime("%Y-%m-%dT%H:%M:%S+00:00")
    slug = source_node.replace(".md", "").replace(":", "-")
    confirm_filename = f"{now.strftime('%Y-%m-%d')}-confirm-{slug}-{result}.md"

    dims = dimensions or {}
    dim_yaml = _dimensions_to_yaml(dims)
    content = CONFIRM_TEMPLATE.format(
        timestamp=ts_str,
        source_node=source_node,
        result=result,
        agent=agent,
        dimensions_yaml=dim_yaml if dim_yaml else "  # (none)",
        context_summary=context_summary or "(no context)",
    )

    dest = _confirm_dir(pool_path) / confirm_filename
    if dest.exists():
        return {"success": False, "error": f"Confirmation node already exists: {confirm_filename}"}

    with open(dest, "w", encoding="utf-8") as f:
        f.write(content)

    return {
        "success": True,
        "confirmation_id": confirm_filename,
        "source": source_node,
        "result": result,
    }


# ─── 查詢確認事件 ──────────────────────────────────


def list_confirmations(pool_path, source_node=None):
    """列出指定源 node 的確認事件（或全部）。

    回傳 list of dict（依時間排序）。
    """
    confirm_dir = _confirm_dir(pool_path)
    if not confirm_dir.exists():
        return []

    events = []
    for fpath in sorted(confirm_dir.iterdir()):
        if not fpath.name.endswith(".md"):
            continue
        with open(fpath, encoding="utf-8") as f:
            content = f.read()
        event = _parse_confirm_node(content)
        event["id"] = fpath.name
        if source_node is None or event["source"] == source_node:
            events.append(event)
    return events


def get_confirmation_stats(pool_path, source_node):
    """取得指定源 node 的確認統計。

    回傳 dict:
    {positive: N, negative: N, neutral: N, total: N, ratio: float}
    """
    events = list_confirmations(pool_path, source_node)
    positive = sum(1 for e in events if e["result"] == "positive")
    negative = sum(1 for e in events if e["result"] == "negative")
    neutral = sum(1 for e in events if e["result"] == "neutral")

    # 只算有正反饋的事件（neutral 不計入）
    scorable = positive + negative

    return {
        "positive": positive,
        "negative": negative,
        "neutral": neutral,
        "total": len(events),
        "scorable": scorable,
    }


# ─── Maturation Score 計算 ──────────────────────────────────


def calc_maturation(base_intensity, positive_events, negative_events,
                    timestamp_str, context_dims=None, node_dims=None,
                    exclude_unmatched=True):
    """計算 node 的 maturation score。

    公式：
      maturation = base_intensity × confirmation_ratio × time_matured

    confirmation_ratio = (positive + 1) / (positive + negative + 1)
      → 無事件時 ratio=1.0（中性起步）
      → 正事件多時趨近 1.0
      → 負事件多時趨近 0.0

    time_matured：
      >=30 天 → 1.0
      >=14 天 → 0.8
      <14 天  → 0.5

    參數：
    - context_dims: dict — 當前 context 的維度（用於提醒）
    - node_dims: dict — node 的維度
    - exclude_unmatched: bool — 是否排除不匹配維度的事件（預設是）

    回傳 dict 包含 score 以及各項子分數。
    """
    # 計算 confirmation_ratio
    scorable = positive_events + negative_events
    if scorable == 0:
        confirmation_ratio = 1.0  # 無事件 = 中性起步
    else:
        confirmation_ratio = (positive_events + 1) / (scorable + 1)

    # 計算 time_matured
    days_since = _days_since(timestamp_str)
    if days_since is None:
        time_matured = 0.5  # 無時間戳 = 保守
    elif days_since >= 30:
        time_matured = 1.0
    elif days_since >= 14:
        time_matured = 0.8
    else:
        time_matured = 0.5

    # 維度匹配提示（不影響 score，僅供參考）
    dim_hint = ""
    if context_dims and node_dims:
        compatible, reason = _check_compat(node_dims, context_dims)
        if not compatible:
            dim_hint = f"⚠ 維度不匹配: {reason}"

    score = base_intensity * confirmation_ratio * time_matured

    return {
        "score": round(score, 2),
        "base_intensity": base_intensity,
        "confirmation_ratio": round(confirmation_ratio, 3),
        "time_matured": time_matured,
        "days_since": days_since if days_since else 0,
        "positive_events": positive_events,
        "negative_events": negative_events,
        "scorable_events": scorable,
        "dimension_hint": dim_hint,
    }


def _check_compat(node_dims, context_dims):
    """內部相容性檢查（不依賴 dimensions module 的 is_compatible 回傳格式）"""
    from hypermemory.core.dimensions import is_compatible
    return is_compatible(node_dims, context_dims)


def _days_since(timestamp_str):
    """計算 timestamp 到現在的天數。"""
    if not timestamp_str:
        return None
    try:
        ts = datetime.fromisoformat(timestamp_str)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None
    now = datetime.now(timezone.utc)
    return max(0, (now - ts).days)


# ─── 批次統計：掃描所有 node ──────────────────────────────────


def scan_maturation_all(pool_path, context_dims=None):
    """掃描 pool 中所有 node，計算 maturation score。

    回傳 list of dict，按 maturation score 降冪排序。
    """
    from hypermemory.core.pool import list_nodes, node_path

    nodes = list(list_nodes(pool_path))
    results = []

    for nf in nodes:
        npath = node_path(pool_path, nf)
        if not npath or not npath.exists():
            continue
        with open(npath, encoding="utf-8") as f:
            content = f.read()

        fm = parse_frontmatter(content)
        intensity = fm.get("intensity", 1)

        stats = get_confirmation_stats(pool_path, nf)
        node_dims = parse_dimensions(fm)
        title = extract_title(content)

        # 若 context_dims 提供，檢查相容性
        if context_dims and node_dims:
            compat, _ = _check_compat(node_dims, context_dims)
            if not compat:
                # 不匹配 → 不納入結果（不是不計分，是 filter 掉）
                continue

        mat = calc_maturation(
            intensity,
            stats["positive"],
            stats["negative"],
            fm.get("timestamp"),
            context_dims=context_dims,
            node_dims=node_dims,
        )
        mat["node"] = nf
        mat["title"] = title
        results.append(mat)

    results.sort(key=lambda r: r["score"], reverse=True)
    return results


def format_maturation(mat):
    """格式化 maturation 結果為可讀字串。"""
    lines = [
        f"Maturation: {mat['score']}  "
        f"(intensity={mat['base_intensity']} × "
        f"ratio={mat['confirmation_ratio']} × "
        f"time={mat['time_matured']})",
        f"  確認事件: {mat['positive_events']}P / {mat['negative_events']}N / "
        f"{mat['scorable_events']} scorable",
        f"  存在天數: {mat['days_since']}d → time_matured={mat['time_matured']}",
    ]
    if mat.get("dimension_hint"):
        lines.append(f"  {mat['dimension_hint']}")
    return "\n".join(lines)
