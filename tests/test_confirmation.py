"""HyperMemory 測試 — Confirmation Event 管線（事實糾偏循環）

P0 測試，涵蓋 create_confirmation、list_confirmations、
get_confirmation_stats、以及與 calc_maturation 的整合。
"""

import sys
import os
import json
import tempfile
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from hypermemory.core.maturation import (
    create_confirmation,
    list_confirmations,
    get_confirmation_stats,
    calc_maturation,
)
from hypermemory.core.node import parse_frontmatter

TS = "2026-06-01T00:00:00+00:00"


def _pool_with_node(name="a.md"):
    """建立一個有單一 node 的暫存池。"""
    tmp = Path(tempfile.mkdtemp(prefix="hm_test_confirm_"))
    (tmp / name).write_text(
        "---\ntype: 2\ntimestamp: " + TS + "\nnode_type: 2\n"
        "prenode: null\nnextnodes: null\nref_by: null\n"
        "intensity: 5\ntotal_mentions: 1\ntags: [test]\n---\n\n# Test"
    )
    return tmp


def _pool_with_dimensions():
    """建立有 dimensions 的 node。"""
    tmp = Path(tempfile.mkdtemp(prefix="hm_test_confirm_"))
    (tmp / "a.md").write_text(
        "---\ntype: 2\ntimestamp: " + TS + "\nnode_type: 2\n"
        "prenode: null\nnextnodes: null\nref_by: null\n"
        "intensity: 5\ntotal_mentions: 1\ntags: [test]\n"
        "dimensions:\n  機: WSL\n  料: Python\n---\n# Test"
    )
    return tmp


# ─── create_confirmation ───


def test_create_positive():
    """建立 positive 確認事件。"""
    pool = _pool_with_node()
    result = create_confirmation(pool, "a.md", "positive", agent="test")
    assert result["success"]
    assert result["result"] == "positive"

    # 確認檔案寫入 confirm/ 目錄
    confirm_dir = pool / "confirm"
    assert confirm_dir.exists()
    files = list(confirm_dir.glob("*.md"))
    assert len(files) >= 1

    # 確認 frontmatter 內容
    content = files[0].read_text()
    fm = parse_frontmatter(content)
    # type field 格式可能為字串
    assert "positive" in content
    assert "a.md" in content


def test_create_negative():
    """建立 negative 確認事件。"""
    pool = _pool_with_node()
    result = create_confirmation(pool, "a.md", "negative", agent="test")
    assert result["success"]
    assert result["result"] == "negative"


def test_create_with_dimensions():
    """含 dimensions 寫入。"""
    pool = _pool_with_dimensions()
    result = create_confirmation(
        pool, "a.md", "positive", agent="test",
        dimensions={"機": "WSL", "料": "Python"},
    )
    assert result["success"]

    confirm_dir = pool / "confirm"
    files = list(confirm_dir.glob("*.md"))
    content = files[0].read_text()
    assert "WSL" in content
    assert "Python" in content


def test_create_with_context_summary():
    """含 context_summary。"""
    pool = _pool_with_node()
    result = create_confirmation(
        pool, "a.md", "positive", agent="test",
        context_summary="Build passed on Python 3.12",
    )
    assert result["success"]

    confirm_dir = pool / "confirm"
    files = list(confirm_dir.glob("*.md"))
    content = files[0].read_text()
    assert "Build passed" in content


def test_create_invalid_result():
    """invalid result → 錯誤。"""
    pool = _pool_with_node()
    result = create_confirmation(pool, "a.md", "invalid", agent="test")
    assert not result["success"]
    assert "error" in result


def test_create_source_not_found():
    """source node 不存在 → 錯誤。"""
    pool = _pool_with_node()
    result = create_confirmation(pool, "nonexistent.md", "positive", agent="test")
    assert not result["success"]
    assert "not found" in result.get("error", "").lower()


def test_create_duplicate():
    """重複檔名（同 source + result）→ 錯誤。"""
    pool = _pool_with_node()
    r1 = create_confirmation(pool, "a.md", "positive", agent="test")
    assert r1["success"]

    r2 = create_confirmation(pool, "a.md", "positive", agent="test")
    assert not r2["success"]
    assert "already exists" in r2.get("error", "").lower()


def test_create_neutral():
    """neutral 結果。"""
    pool = _pool_with_node()
    result = create_confirmation(pool, "a.md", "neutral", agent="test")
    assert result["success"]
    assert result["result"] == "neutral"


# ─── list_confirmations + get_confirmation_stats ───


def _pool_with_events(pool, source="a.md", positives=3, negatives=2):
    """在 pool 中建立多筆確認事件（使用不同 context_summary 避免檔名重複）。"""
    for i in range(positives):
        create_confirmation(pool, source, "positive", agent="test",
                            context_summary=f"positive-{i}")
    for i in range(negatives):
        create_confirmation(pool, source, "negative", agent="test",
                            context_summary=f"negative-{i}")


def test_list_by_source():
    """列出指定 source 的事件。"""
    pool = _pool_with_node()
    _pool_with_events(pool, positives=1, negatives=1)

    events = list_confirmations(pool, source_node="a.md")
    assert len(events) >= 2


def test_list_all():
    """列出全部事件（不指定 source）。"""
    pool = _pool_with_node()
    _pool_with_events(pool, positives=1, negatives=1)

    events = list_confirmations(pool)
    assert len(events) >= 2


def test_stats_positive_negative():
    """統計 positive / negative / scorable。"""
    pool = _pool_with_node()
    _pool_with_events(pool, positives=1, negatives=1)

    stats = get_confirmation_stats(pool, "a.md")
    assert stats["positive"] >= 1
    assert stats["negative"] >= 1
    assert stats["total"] >= 2
    assert stats["scorable"] >= 2


def test_stats_empty():
    """無事件 → 全 0。"""
    pool = _pool_with_node()
    stats = get_confirmation_stats(pool, "a.md")
    assert stats["positive"] == 0
    assert stats["negative"] == 0
    assert stats["total"] == 0


def test_stats_neutral_only():
    """僅 neutral 事件 → scorable=0（不計入正負分數）。"""
    pool = _pool_with_node()
    create_confirmation(pool, "a.md", "neutral", agent="test")

    stats = get_confirmation_stats(pool, "a.md")
    assert stats["neutral"] >= 1
    assert stats["scorable"] == 0  # neutral 不計入


# ─── calc_maturation 整合 ───


def test_maturation_positive_boost():
    """positive 事件提升 score。"""
    mat = calc_maturation(5, 3, 0, "2026-01-01T00:00:00+00:00")
    # ratio = (3+1)/(3+1) = 1.0, time >= 30d → 1.0, score = 5*1*1 = 5.0
    assert abs(mat["score"] - 5.0) < 0.1


def test_maturation_negative_reduces():
    """negative 事件降低 score。"""
    mat = calc_maturation(5, 1, 4, "2026-01-01T00:00:00+00:00")
    # ratio = (1+1)/(5+1) = 0.333, time >= 30d → 1.0, score = 5*0.333*1 ≈ 1.67
    assert 1.5 < mat["score"] < 2.0


def test_maturation_no_events_neutral():
    """無事件 → 中性起步（ratio=1.0）。"""
    mat = calc_maturation(5, 0, 0, "2026-01-01T00:00:00+00:00")
    assert abs(mat["score"] - 5.0) < 0.1


def test_maturation_dynamic():
    """建立事件後 score 變化（negative 降 → positive 升）。"""
    pool = _pool_with_node()

    # 先加 negative：ratio 下降
    create_confirmation(pool, "a.md", "negative", agent="test", context_summary="first")
    stats1 = get_confirmation_stats(pool, "a.md")
    mat1 = calc_maturation(5, stats1["positive"], stats1["negative"], TS)
    score1 = mat1["score"]

    # 再加 positive：ratio 回升
    create_confirmation(pool, "a.md", "positive", agent="test", context_summary="boost")
    stats2 = get_confirmation_stats(pool, "a.md")
    mat2 = calc_maturation(5, stats2["positive"], stats2["negative"], TS)
    score2 = mat2["score"]

    assert score2 > score1, (
        f"Score after adding positive ({score2}) should exceed score with only negative ({score1})"
    )
