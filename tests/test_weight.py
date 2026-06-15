"""HyperMemory 核心測試 — weight"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from hypermemory.core.weight import calc_weight, format_score


def test_calc_weight_basic():
    """基本權重計算：intensity × (1 + 0.1 × mentions) × decay"""
    w = calc_weight(5, 1, None)
    assert w == 5.5, f"Expected 5.5, got {w}"


def test_calc_weight_without_timestamp():
    """無 timestamp 時回傳 intensity × (1 + 0.1 × mentions)"""
    assert calc_weight(1, 0, None) == 1.0
    assert calc_weight(10, 0, None) == 10.0
    assert calc_weight(5, 10, None) == 5 * (1 + 0.1 * 10) == 10.0


def test_format_score():
    assert format_score(5.5) == "5.50"
    assert format_score(0.0) == "0.00"
    assert format_score(9.876) == "9.88"


def test_decay_recent():
    """今天寫入的 node，decay 接近 1"""
    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).isoformat()
    w = calc_weight(5, 1, ts)
    assert w > 5.0, f"Recent node should have high weight, got {w}"


def test_decay_old():
    """一年前的 node，decay 應低於近期 node"""
    from datetime import datetime, timedelta, timezone
    old = (datetime.now(timezone.utc) - timedelta(days=300)).isoformat()
    recent = datetime.now(timezone.utc).isoformat()
    w_old = calc_weight(5, 1, old)
    w_recent = calc_weight(5, 1, recent)
    assert w_old < w_recent, f"Old node ({w_old}) should weigh less than recent ({w_recent})"


def test_intensity_affects_decay():
    """高 intensity node 衰減更慢"""
    from datetime import datetime, timedelta, timezone
    old = (datetime.now(timezone.utc) - timedelta(days=200)).isoformat()
    w_high = calc_weight(9, 1, old)
    w_low = calc_weight(3, 1, old)
    # Both have intensity in base, so compare ratio-adjusted
    ratio_high = w_high / (9 * 1.1)  # decay factor for high intensity
    ratio_low = w_low / (3 * 1.1)   # decay factor for low intensity
    assert ratio_high > ratio_low, f"High intensity should decay slower. high={ratio_high:.4f} low={ratio_low:.4f}"


def test_mentions_increase_weight():
    """total_mentions 越高權重越高"""
    w1 = calc_weight(5, 1, None)
    w5 = calc_weight(5, 5, None)
    assert w5 > w1, f"More mentions should increase weight: {w5} vs {w1}"


def test_negative_days_handling():
    """未來 timestamp 應 clamp 到 0 天，不產生負 decay"""
    from datetime import datetime, timedelta, timezone
    future = (datetime.now(timezone.utc) + timedelta(days=100)).isoformat()
    w = calc_weight(5, 1, future)
    # Should be same as today (clamped to 0 days)
    now = datetime.now(timezone.utc).isoformat()
    w_now = calc_weight(5, 1, now)
    assert abs(w - w_now) < 0.01, f"Future timestamp should clamp to 0 days: {w} vs {w_now}"
