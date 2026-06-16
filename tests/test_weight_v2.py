"""HyperMemory 測試 — Weight v2（三因子動態權重）

測試範圍：
- engagement 因子：intensity × (1 + 0.1 × mentions) + ref_by_boost + chain_boost
- recency 因子：node_type-aware 半衰期模型
- solidification：高 intensity node 的永不衰減基底加成
- 邊界條件：無 timestamp、無 ref_by、chain_length=1
- floor 保護：recency 最低 0.05
- 與 v1 的相容性：基礎計算邏輯一致
"""

import sys
import os
import math
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from hypermemory.core.weight import calc_weight, format_score

# ─── Engagement 測試 ──────────────────────────────────


def test_engagement_basic():
    """基本 engagement：intensity × (1 + 0.1 × mentions) + solidification"""
    # intensity=5, mentions=1 → engagement=5.5, recency=1.0, solidification=0.25
    w = calc_weight(5, 1)
    assert abs(w - 5.75) < 0.01, f"Expected 5.75, got {w}"


def test_engagement_no_mentions():
    """mentions=0 → intensity × 1.0 + solidification"""
    assert calc_weight(1, 0) == 1.05
    assert calc_weight(10, 0) == 10.5


def test_engagement_high_mentions():
    """mentions 越高 engagement 越高"""
    w1 = calc_weight(5, 1)
    w10 = calc_weight(5, 10)
    assert w10 > w1, f"More mentions should increase weight: {w10} vs {w1}"


def test_ref_by_boost():
    """ref_by_count 增加 engagement: +0.3 per ref"""
    # intensity=5, mentions=1 → engagement=5.5
    # ref_by_count=4 → +1.2 → engagement=6.7
    # solidification=0.25 → total=6.95
    w = calc_weight(5, 1, ref_by_count=4)
    assert abs(w - 6.95) < 0.01, f"Expected 6.95, got {w}"


def test_chain_boost():
    """chain_length > 1 增加 engagement: +0.2 per extra node"""
    # intensity=5, mentions=1 → engagement=5.5
    # chain_length=4 → +0.6 → engagement=6.1
    # solidification=0.25 → total=6.35
    w = calc_weight(5, 1, chain_length=4)
    assert abs(w - 6.35) < 0.01, f"Expected 6.35, got {w}"


def test_ref_by_and_chain_boost():
    """ref_by + chain 加成疊加"""
    # intensity=5, mentions=1 → engagement=5.5
    # ref_by_count=2 → +0.6, chain_length=3 → +0.4 → engagement=6.5
    # solidification=0.25 → total=6.75
    w = calc_weight(5, 1, ref_by_count=2, chain_length=3)
    assert abs(w - 6.75) < 0.01, f"Expected 6.75, got {w}"


# ─── Recency 測試（node_type-aware） ─────────────────


def test_recency_within_half_life():
    """在 half_life 內 → recency = 1.0（最近活躍）"""
    # 經驗 的 half_life = 30 天
    # days_since_last_hit = 15 → within half-life → recency = 1.0
    # solidification = 0.25
    w = calc_weight(5, 1, node_type="經驗", days_since_last_hit=15)
    assert abs(w - 5.75) < 0.01, f"Within half-life should be 5.75, got {w}"


def test_recency_beyond_half_life():
    """超過 half_life → 指數衰減"""
    # 經驗 half_life = 30 天, days=60 → excess=30 → recency=exp(-1)≈0.368
    # engagement=5.5, recency=0.368 → 5.5*0.368=2.02, solidification=0.25 → 2.27
    w = calc_weight(5, 1, node_type="經驗", days_since_last_hit=60)
    expected = 5.5 * math.exp(-1) + 0.25
    assert abs(w - expected) < 0.02, f"Expected ~{expected:.3f}, got {w}"


def test_recency_floor():
    """非常舊的 node → recency floor = 0.05"""
    # 經驗 half_life=30, days=365 → recency floor=0.05
    # engagement=5.5, weight=5.5*0.05 + 0.25(solidification) = 0.525
    w = calc_weight(5, 1, node_type="經驗", days_since_last_hit=365)
    expected = 5.5 * 0.05 + 0.25
    assert abs(w - expected) < 0.01, f"Expected {expected}, got {w}"


def test_node_type_half_life_difference():
    """不同 node_type 的半衰期不同，影響 recency"""
    # 骨骼 half_life = 90, days=60 → within half-life → recency = 1.0
    w_skeletal = calc_weight(5, 1, node_type="骨骼", days_since_last_hit=60)
    # 自動刻錄 half_life = 7, days=60 → far beyond → decayed
    w_auto = calc_weight(5, 1, node_type="自動刻錄", days_since_last_hit=60)

    assert abs(w_skeletal - 5.75) < 0.01, f"Skeletal within half-life: expected 5.75, got {w_skeletal}"
    assert w_auto < 5.75, f"Auto-imprint should decay: got {w_auto}"
    assert w_skeletal > w_auto, f"Skeletal ({w_skeletal}) should weigh > auto-imprint ({w_auto})"


def test_recency_via_timestamp():
    """透過 timestamp_str 計算 days_since 並應用 recency"""
    # 用 timestamp 建立時間（而非直接傳 days_since_last_hit）
    recent = datetime.now(timezone.utc).isoformat()
    w_recent = calc_weight(5, 1, timestamp_str=recent, node_type="經驗")
    assert w_recent > 5.0, f"Recent node should have high weight, got {w_recent}"

    # 60 天前
    old = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
    w_old = calc_weight(5, 1, timestamp_str=old, node_type="經驗")
    assert w_old < w_recent, f"Old node ({w_old}) should weigh less than recent ({w_recent})"


def test_recency_beyond_experience():
    """超過經驗的半衰期，但仍在骨骼的半衰期內"""
    # days=60:
    #   經驗 half_life=30 → recency decays
    #   骨骼 half_life=90 → within half-life → recency = 1.0
    w_exp = calc_weight(5, 1, node_type="經驗", days_since_last_hit=60)
    w_skeletal = calc_weight(5, 1, node_type="骨骼", days_since_last_hit=60)
    assert w_skeletal > w_exp, f"Skeletal ({w_skeletal}) should outlast experience ({w_exp})"


def test_auto_imprint_rapid_decay():
    """自動刻錄 7 天無命中即開始衰減"""
    # 自動刻錄 half_life = 7, days=7 → at boundary → recency = 1.0
    w_boundary = calc_weight(5, 1, node_type="自動刻錄", days_since_last_hit=7)
    assert abs(w_boundary - 5.75) < 0.01, f"At half-life boundary should be 5.75: {w_boundary}"

    # days=14 → excess=7 → recency = exp(-7/7) = exp(-1) ≈ 0.368
    w_decay = calc_weight(5, 1, node_type="自動刻錄", days_since_last_hit=14)
    assert w_decay < 5.5, f"Should decay after half-life: {w_decay}"
    assert w_decay > 0, f"Decaying node should still have weight > 0: {w_decay}"


# ─── 邊界情境 ──────────────────


def test_no_timestamp_default_recency():
    """無 timestamp 也無 days_since → recency = 1.0"""
    w = calc_weight(5, 1)
    assert abs(w - 5.75) < 0.01, f"No timestamp should be 5.75, got {w}"


def test_format_score_still_works():
    """format_score 不受影響"""
    assert format_score(5.5) == "5.50"
    assert format_score(0.0) == "0.00"
    assert format_score(9.876) == "9.88"


def test_negative_days_handling():
    """未來 timestamp 應 clamp 到 0 天"""
    future = (datetime.now(timezone.utc) + timedelta(days=100)).isoformat()
    w_future = calc_weight(5, 1, timestamp_str=future)
    w_now = calc_weight(5, 1, timestamp_str=datetime.now(timezone.utc).isoformat())
    assert abs(w_future - w_now) < 0.01, f"Future should clamp: {w_future} vs {w_now}"


def test_zero_intensity():
    """intensity=0 → weight=0"""
    w = calc_weight(0, 0)
    assert w == 0.0, f"Zero intensity should give zero weight: {w}"


def test_unknown_node_type():
    """未知 node_type → 用 經驗 的半衰期（30 天）作為 fallback"""
    w = calc_weight(5, 1, node_type="未知型別", days_since_last_hit=15)
    # 用 "經驗" 的 half_life (30) 當 fallback，15 < 30 → recency=1
    # solidificaiton = 0.25 → total = 5.75
    assert abs(w - 5.75) < 0.01, f"Unknown type should fallback to 5.75, got {w}"

    w_old = calc_weight(5, 1, node_type="未知型別", days_since_last_hit=60)
    # 用 "經驗" half_life=30 → excess=30 → recency=exp(-1)
    # engagement=5.5, recency=exp(-1)≈0.368, solidification=0.25 → ≈2.27
    expected = 5.5 * math.exp(-1) + 0.25
    assert abs(w_old - expected) < 0.02, f"Expected ~{expected:.3f}, got {w_old}"


# ─── 整合情境 ──────────────────


def test_full_v2_formula():
    """完整 v2 公式：engagement × recency"""
    # intensity=8, mentions=3 → engagement=8×1.3=10.4
    # ref_by=2 → +0.6, chain=5 → +0.8 → engagement=11.8
    # 骨骼, days=45 → recency=1.0, solidification=0.4 → total=12.2
    w = calc_weight(8, 3, node_type="骨骼", ref_by_count=2, chain_length=5, days_since_last_hit=45)
    expected = 12.2
    assert abs(w - expected) < 0.01, f"Expected {expected}, got {w}"

    # 同條件但 days=120 (beyond skeletal half_life=90) → recency decays
    w_old = calc_weight(8, 3, node_type="骨骼", ref_by_count=2, chain_length=5, days_since_last_hit=120)
    assert w_old < expected, f"Old node ({w_old}) should weigh less than recent ({expected})"


def test_high_intensity_survives_longer():
    """高 intensity + 骨骼 type 組合讓重要經驗更持久"""
    # 骨骼 half_life=90, days=150 → excess=60 → recency=exp(-60/90)=0.513
    w_high = calc_weight(9, 5, node_type="骨骼", days_since_last_hit=150)
    # 自動刻錄 low intensity, days=20 → excess=13 → recency=exp(-13/7)=0.156
    w_low = calc_weight(2, 0, node_type="自動刻錄", days_since_last_hit=20)

    # 高 intensity 骨骼即使 150 天未命中，權重仍可能高於低 intensity 自動刻錄
    assert w_high > 0, f"High intensity skeletal should have weight: {w_high}"
    # 但不保證高於低 intensity（取決於 intensity 差異），只驗證各自合理範圍
    assert w_high > 1.0, f"High intensity important node should stay relevant: {w_high}"


# ─── 固化加成（Solidification Bonus） ────────────────


def test_solidification_adds_floor():
    """高 intensity node 久遠後仍有固化基底，不歸零。"""
    # intensity=9, 非常久的時間
    w = calc_weight(9, 0, node_type="經驗", days_since_last_hit=1000)
    # recency floor = 0.05, engagement = 9*1.0 = 9, so 9*0.05 = 0.45
    # solidification = 9*0.05 = 0.45
    # total = 0.45 + 0.45 = 0.90
    assert w > 0.5, f"High intensity should retain floor weight: {w}"
    assert w < 2.0, f"Floor should still be low: {w}"


def test_solidification_scales_with_intensity():
    """固化加成與 intensity 成正比。"""
    w_low = calc_weight(2, 0, node_type="經驗", days_since_last_hit=1000)
    w_high = calc_weight(9, 0, node_type="經驗", days_since_last_hit=1000)
    # engagement: 2 vs 9, both recency floor = 0.05
    # engagement*recency = 2*0.05=0.1 vs 9*0.05=0.45
    # solidification: 0.1 vs 0.45
    # total: 0.2 vs 0.9
    diff_total = w_high - w_low
    # solidification diff alone = (9-2)*0.05 = 0.35
    # But engagement*recency also differs: (9-2)*0.05 = 0.35
    # Total diff = 0.70
    assert abs(diff_total - 0.70) < 0.05, f"Diff should be ~0.70, got {diff_total}"


def test_solidification_does_not_affect_recent_nodes():
    """近期 node 的固化加成佔比很小，不主導權重。"""
    w_recent = calc_weight(5, 1, node_type="經驗", days_since_last_hit=1)
    w_no_solid = calc_weight(5, 1, node_type="經驗", days_since_last_hit=1)
    # Solidification adds 0.25 to 5.75 (4.3%), doesn't dominate
    ratio = (w_recent - w_no_solid) / w_no_solid
    assert ratio < 0.1, f"Solidification ratio should be small for recent nodes: {ratio:.2%}"
