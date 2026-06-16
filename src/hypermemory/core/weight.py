"""HyperMemory 核心 — 權重計算 v2

公式：weight = engagement × recency + solidification

engagement = intensity × (1 + 0.1 × total_mentions) + ref_by_count × 0.3 + max(0, chain_length - 1) × 0.2
recency   = node_type-aware 半衰期指數模型
solidification = intensity × 0.05（永不衰減的固化基底，確保高 intensity node 永遠有基本 recall 機會）
"""

import math
from datetime import datetime, timezone

# Node type → half-life (days)
HALF_LIFE_MAP = {
    "經驗": 30,
    "決策": 30,
    "骨骼": 90,
    "方法": 30,
    "自動刻錄": 7,
}
DEFAULT_HALF_LIFE = 30


def calc_weight(
    intensity: int,
    total_mentions: int,
    timestamp_str: str | None = None,
    node_type: str = "經驗",
    ref_by_count: int = 0,
    chain_length: int = 1,
    days_since_last_hit: int | None = None,
) -> float:
    """計算 node 權重（v2：engagement × recency）。

    Parameters
    ----------
    intensity : int
        經驗強度 1-10
    total_mentions : int
        累計引用次數
    timestamp_str : str | None
        ISO 格式時間戳（days_since_last_hit 優先於此）
    node_type : str
        節點類型（決定 half-life）：經驗/決策/骨骼/方法/自動刻錄
    ref_by_count : int
        被引用次數（+0.3 per ref）
    chain_length : int
        鏈長度（+0.2 per extra node beyond 1）
    days_since_last_hit : int | None
        距上次命中的天數（若提供則直接使用，跳過 timestamp 計算）

    Returns
    -------
    float
        最終權重
    """
    # ── Engagement ──────────────────────────────────────
    engagement = float(intensity) * (1 + 0.1 * total_mentions)
    engagement += ref_by_count * 0.3
    engagement += max(0, chain_length - 1) * 0.2

    # ── Recency ─────────────────────────────────────────
    # days_since_last_hit 優先於 timestamp_str
    if days_since_last_hit is not None:
        days = days_since_last_hit
    elif timestamp_str:
        try:
            ts = datetime.fromisoformat(timestamp_str)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            days = max(0, (now - ts).days)
        except (ValueError, TypeError):
            days = None
    else:
        days = None

    if days is not None:
        half_life = HALF_LIFE_MAP.get(node_type, DEFAULT_HALF_LIFE)
        if days < half_life:
            recency = 1.0
        else:
            excess = days - half_life
            recency = max(0.05, math.exp(-excess / half_life))
    else:
        recency = 1.0

    # Solidification bonus: high-intensity nodes never fully decay
    return engagement * recency + float(intensity) * 0.05


def format_score(score):
    """格式化分數顯示"""
    return f"{score:.2f}"
