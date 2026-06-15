"""HyperMemory 核心 — 權重計算"""

from datetime import datetime, timezone


def calc_weight(intensity, total_mentions, timestamp_str=None):
    """計算 node 權重。

    公式：score = intensity × (1 + 0.1 × total_mentions) × decay(t)

    decay 使用 intensity-adaptive 線性衰減：
      base_rate = 1 / 365
      decay_rate = base_rate × (11 - intensity) / 10
      decay = max(0.05, 1 - decay_rate × days_since)
    """
    base = float(intensity) * (1 + 0.1 * total_mentions)
    
    if not timestamp_str:
        return base

    try:
        ts = datetime.fromisoformat(timestamp_str)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return base

    now = datetime.now(timezone.utc)
    days_since = max(0, (now - ts).days)  # clamp negative days

    # Intensity-adaptive linear decay
    base_rate = 1.0 / 365.0
    decay_rate = base_rate * (11 - intensity) / 10
    decay = max(0.05, 1 - decay_rate * days_since)

    return base * decay


def format_score(score):
    """格式化分數顯示"""
    return f"{score:.2f}"
