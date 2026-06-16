"""HyperMemory 測試 — Domain Invariant 驗證

確保核心不變性原則永遠成立。
"""

import sys
import os
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from hypermemory.core.maturation import calc_maturation
from hypermemory.core.dimensions import is_compatible
from hypermemory.core.hm_tools import HMTools

TS_OLD = "2025-01-01T00:00:00+00:00"
TS_NEW = "2026-06-16T00:00:00+00:00"


# ─── I1 / F2: Recency-first 排序 ────────────────────


def _pool_two_clusters():
    """兩個獨立 cluster：舊高權重 vs 新低權重。"""
    tmp = Path(tempfile.mkdtemp(prefix="hm_test_recency_"))

    # z-old: intensity=9, mentions=20 → 高 weight
    (tmp / "z-old.md").write_text(
        "---\ntype: 2\ntimestamp: " + TS_OLD + "\nnode_type: 2\n"
        "prenode: null\nnextnodes: null\nref_by: null\n"
        "intensity: 9\ntotal_mentions: 20\ntags: [test]\n---\n\n# Old\nOld."
    )
    # a-new: intensity=3, mentions=0 → 低 weight
    (tmp / "a-new.md").write_text(
        "---\ntype: 2\ntimestamp: " + TS_NEW + "\nnode_type: 2\n"
        "prenode: null\nnextnodes: null\nref_by: null\n"
        "intensity: 3\ntotal_mentions: 0\ntags: [test]\n---\n\n# New\nNew."
    )

    index = "# Index\n《cluster: [test, old]》 → [[z-old.md]]\n"
    index += "《cluster: [test, new]》 → [[a-new.md]]\n"
    (tmp / "index.md").write_text(index)
    return tmp


def test_recall_recency_first():
    """recall 回傳結果按 timestamp 降冪（最新在前）。"""
    pool = _pool_two_clusters()
    tools = HMTools(str(pool))
    result = tools.recall("test")

    assert result["found"]
    timestamps = [r["timestamp"] for r in result["results"]]
    assert timestamps == sorted(timestamps, reverse=True), (
        "Results should be sorted newest-first: " + str(timestamps)
    )
    assert result["results"][0]["node"] == "a-new.md"
    assert result["results"][-1]["node"] == "z-old.md"


def test_think_returns_newest():
    """think 回傳最新 node（非最高 weight）。"""
    pool = _pool_two_clusters()
    tools = HMTools(str(pool))
    result = tools.think("test")

    assert result["found"]
    assert result["result"]["node"] == "a-new.md", (
        "Think should return newest (a-new), not highest-weight, got "
        + result["result"]["node"]
    )


def test_recall_newest_first_ignores_weight():
    """recency-first 排序成立（同 test_recall_recency_first）。"""
    pool = _pool_two_clusters()
    tools = HMTools(str(pool))
    result = tools.recall("test")
    assert result["found"]
    assert result["results"][0]["node"] == "a-new.md"


# ─── I2: Imprint 不覆寫 ─────────────────────────


def _pool_with_index():
    tmp = Path(tempfile.mkdtemp(prefix="hm_test_imprint_"))
    (tmp / "index.md").write_text("# Index\n")
    return tmp


def test_imprint_refuses_overwrite():
    """imprint 不覆蓋已存在的 node。"""
    pool = _pool_with_index()
    # 先寫入一個完整的 node
    (pool / "exists.md").write_text(
        "---\ntype: 2\ntimestamp: " + TS_OLD
        + "\nnode_type: 2\nprenode: null\nnextnodes: null\nref_by: null\n"
        "intensity: 5\ntotal_mentions: 1\ntags: [test]\n---\n\n# Existing"
    )
    tools = HMTools(str(pool))

    # 試著用同檔名 imprint
    content = (
        "---\ntype: 2\ntimestamp: " + TS_NEW
        + "\nnode_type: 2\nprenode: null\nnextnodes: null\nref_by: null\n"
        "intensity: 3\ntotal_mentions: 1\ntags: [test]\n---\n\n# New"
    )
    result = tools.imprint(content, filename="exists.md")

    assert not result["success"], "Should refuse to overwrite existing"
    err = (", ").join(result.get("errors", [])) + " " + result.get("error", "")
    assert "exists" in err.lower(), "Should mention 'exists' but got: " + err


# ─── I4: 鏈雙向完整性 ─────────────────────────


def _chain_pool():
    tmp = Path(tempfile.mkdtemp(prefix="hm_test_chain_"))
    (tmp / "head.md").write_text(
        "---\ntype: 2\ntimestamp: " + TS_OLD + "\nnode_type: 2\n"
        "prenode: null\nnextnodes:\n  - [[mid.md]]\nref_by: null\n"
        "intensity: 5\ntotal_mentions: 1\ntags: [chain]\n---\n\n# Head\n."
    )
    (tmp / "mid.md").write_text(
        "---\ntype: 2\ntimestamp: " + TS_OLD + "\nnode_type: 2\n"
        "prenode: [[head.md]]\nnextnodes:\n  - [[tail.md]]\nref_by: null\n"
        "intensity: 5\ntotal_mentions: 1\ntags: [chain]\n---\n\n# Mid\n."
    )
    (tmp / "tail.md").write_text(
        "---\ntype: 2\ntimestamp: " + TS_OLD + "\nnode_type: 2\n"
        "prenode: [[mid.md]]\nnextnodes: null\nref_by: null\n"
        "intensity: 5\ntotal_mentions: 1\ntags: [chain]\n---\n\n# Tail\n."
    )
    (tmp / "index.md").write_text("# Index\n《cluster: [chain]》 → [[head.md]]\n")
    return tmp


def test_chain_bidirectional():
    """若 A.nextnodes 有 B，則 B.prenode == A。"""
    pool = _chain_pool()
    from hypermemory.core.node import parse_frontmatter

    for fname in ["head.md", "mid.md"]:
        raw = (pool / fname).read_text()
        fm = parse_frontmatter(raw)
        for nn in (fm.get("nextnodes", []) or []):
            if not (pool / nn).exists():
                continue
            child_raw = (pool / nn).read_text()
            child_fm = parse_frontmatter(child_raw)
            assert child_fm.get("prenode") == fname, (
                nn + ".prenode should be " + fname
                + ", got " + str(child_fm.get("prenode"))
            )


def test_chain_no_dangling_prenode():
    """每個 prenode 指向的檔案必須存在。"""
    pool = _chain_pool()
    from hypermemory.core.node import parse_frontmatter

    for fname in ["head.md", "mid.md", "tail.md"]:
        raw = (pool / fname).read_text()
        fm = parse_frontmatter(raw)
        pre = fm.get("prenode")
        if pre:
            assert (pool / pre).exists(), (
                fname + ".prenode (" + pre + ") points to non-existent"
            )


# ─── I6: Maturation 有界 ─────────────────────────


def test_maturation_never_negative():
    """maturation 永不為負。"""
    mat = calc_maturation(5, 0, 0, TS_OLD)
    assert mat["score"] >= 0
    # Extreme: all negatives
    mat_neg = calc_maturation(5, 0, 100, TS_OLD)
    assert mat_neg["score"] >= 0


def test_maturation_bounded_by_intensity():
    """maturation 不超過 base_intensity。"""
    mat = calc_maturation(8, 100, 0, "2026-01-01T00:00:00+00:00")
    assert mat["score"] <= 8.0, str(mat["score"]) + " should not exceed 8"


# ─── I7: 5M1E 不匹配不懲罰 ────────


def test_5m1e_no_penalty():
    """不匹配的維度不扣分，只是排除。"""
    node_dims = {"機": "Windows", "料": "Python"}
    context_dims = {"機": "Linux"}

    compat, reason = is_compatible(node_dims, context_dims)
    assert not compat
    assert "衝突" in reason, "Should describe conflict, not penalty"

    # 無 context → 全部通過（不扣分）
    assert is_compatible(node_dims, {})[0]
    # 無 node dims → 全部通過
    assert is_compatible({}, {"機": "WSL"})[0]
