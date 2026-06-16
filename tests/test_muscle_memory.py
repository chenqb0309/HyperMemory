"""HyperMemory 測試 — Muscle Memory Loop（經驗 → Skill）

測試 skill_ready 偵測、frontmatter 標記、pending 鉤子、skill 註冊、過期。
"""

import sys
import os
import json
import tempfile
from pathlib import Path
from datetime import datetime, timezone, timedelta

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from hypermemory.core.muscle_memory import (
    is_skill_ready,
    mark_skill_ready,
    check_candidates,
    register_skill,
    expire_stale_marks,
    pending_skill_count,
    SKILL_DIR,
    SKILL_READY_EXPIRE_DAYS,
    MIN_SKILL_WEIGHT,
    MIN_SKILL_MENTIONS,
    MIN_SKILL_REF_BY,
    MIN_SKILL_MATURATION,
)


# ─── 條件偵測（純函數） ───


def test_skill_ready_high_maturation():
    """maturation ≥ 門檻 + 輔助門檻皆滿足 → skill_ready。"""
    fm = {"total_mentions": MIN_SKILL_MENTIONS, "ref_by": ["a.md", "b.md"]}
    assert is_skill_ready(fm, MIN_SKILL_WEIGHT + 1.0, maturation_score=MIN_SKILL_MATURATION)


def test_skill_ready_low_maturation():
    """maturation < 門檻 → 不 ready。"""
    fm = {"total_mentions": MIN_SKILL_MENTIONS, "ref_by": ["a.md"]}
    assert not is_skill_ready(fm, MIN_SKILL_WEIGHT + 1.0, maturation_score=MIN_SKILL_MATURATION - 0.1)


def test_skill_ready_low_weight_high_maturation():
    """weight 低但有 maturation ≥ 門檻 → ready（maturation 為主要門檻）。"""
    fm = {"total_mentions": MIN_SKILL_MENTIONS, "ref_by": ["a.md", "b.md"]}
    assert is_skill_ready(fm, 1.0, maturation_score=MIN_SKILL_MATURATION)


def test_skill_ready_no_maturation_fallback():
    """無 maturation_score → 向下相容使用 weight-based 門檻（15.0）。"""
    fm = {"total_mentions": MIN_SKILL_MENTIONS, "ref_by": ["a.md", "b.md"]}
    assert not is_skill_ready(fm, 1.0)       # weight 太低 → False
    assert is_skill_ready(fm, 15.0)           # weight >= 15.0 → True


def test_skill_ready_low_mentions():
    """mentions < 門檻 → 不 ready。"""
    fm = {"total_mentions": 0, "ref_by": ["a.md", "b.md"]}
    assert not is_skill_ready(fm, MIN_SKILL_WEIGHT + 1.0, maturation_score=MIN_SKILL_MATURATION)


def test_skill_ready_low_ref_by():
    """ref_by < 門檻 → 不 ready。"""
    fm = {"total_mentions": MIN_SKILL_MENTIONS, "ref_by": []}
    assert not is_skill_ready(fm, MIN_SKILL_WEIGHT + 1.0, maturation_score=MIN_SKILL_MATURATION)


def test_skill_ready_no_ref_by_field():
    """ref_by 欄位不存在（None）→ 視為 0。"""
    fm = {"total_mentions": MIN_SKILL_MENTIONS}
    assert not is_skill_ready(fm, MIN_SKILL_WEIGHT + 1.0, maturation_score=MIN_SKILL_MATURATION)


def test_skill_ready_already_converted():
    """已轉換過的 node（has_skill: true）→ 不重複 ready。"""
    fm = {
        "total_mentions": MIN_SKILL_MENTIONS,
        "ref_by": ["a.md", "b.md"],
        "has_skill": True,
    }
    assert not is_skill_ready(fm, MIN_SKILL_WEIGHT + 1.0, maturation_score=MIN_SKILL_MATURATION)


def test_skill_ready_auto_imprint_skipped():
    """自動刻錄 node 跳過（低品質）。"""
    fm = {
        "total_mentions": MIN_SKILL_MENTIONS,
        "ref_by": ["a.md", "b.md"],
        "node_type": 1,  # 自動刻錄 type=1
    }
    assert not is_skill_ready(fm, MIN_SKILL_WEIGHT + 1.0, maturation_score=MIN_SKILL_MATURATION)


# ─── 標記（需要 temp pool） ───


def _make_pool_one_node(**overrides):
    """建立單一 node 的暫存 pool。"""
    tmp = Path(tempfile.mkdtemp(prefix="hm_test_muscle_"))

    attrs = {
        "intensity": 8,
        "total_mentions": 10,
        "timestamp": (datetime.now(timezone.utc) - timedelta(days=60)).isoformat(),
        "ref_by": "  - [[b.md]]\n  - [[c.md]]",
        "node_type": 3,
        "tags": ["test", "skill"],
        "body": "This node describes a repeatable workflow for debugging.",
    }
    attrs.update(overrides)

    content = f"""---
type: 2
timestamp: {attrs['timestamp']}
node_type: {attrs['node_type']}
prenode: null
nextnodes: null
ref_by:
{attrs['ref_by']}
intensity: {attrs['intensity']}
total_mentions: {attrs['total_mentions']}
tags: [{', '.join(f'"{t}"' for t in attrs['tags'])}]
---

# Test Skill Node

{attrs['body']}
"""
    filename = "2026-01-01-test-skill.md"
    (tmp / filename).write_text(content)

    index = "# HyperMemory Pool Index\n"
    index += f"《cluster: [test, skill]》 → [[{filename}]]\n"
    (tmp / "index.md").write_text(index)

    return tmp, filename


def test_mark_skill_ready_adds_flag():
    """mark_skill_ready 應在 frontmatter 加入 skill_ready: true。"""
    pool, fname = _make_pool_one_node()
    result = mark_skill_ready(pool, fname)
    assert result["success"]

    content = (pool / fname).read_text()
    assert "skill_ready: true" in content
    assert "skill_ready_at:" in content


def test_mark_twice_does_not_duplicate():
    """已標記的 node 再次標記不應產生重複的 skill_ready 行。"""
    pool, fname = _make_pool_one_node()
    mark_skill_ready(pool, fname)
    r2 = mark_skill_ready(pool, fname)
    assert r2["success"]

    content = (pool / fname).read_text()
    # Count occurrences
    assert content.count("skill_ready: true") == 1


# ─── 掃描 ───


def test_check_candidates_finds_ready_node():
    """check_candidates 應回傳符合條件的 node。"""
    pool, fname = _make_pool_one_node()
    mark_skill_ready(pool, fname)

    candidates = check_candidates(pool)
    assert len(candidates) > 0
    nodes = [c["node"] for c in candidates]
    assert fname in nodes


def test_check_candidates_empty_when_none_ready():
    """無已標記 node → 空列表。"""
    pool, fname = _make_pool_one_node(intensity=1, total_mentions=1, ref_by="")
    # Don't mark — weight too low
    candidates = check_candidates(pool)
    candidates_ready = [c for c in candidates if c["status"] == "ready"]
    assert len(candidates_ready) == 0


def test_check_candidates_returns_context():
    """回傳的每個 candidate 應包含轉換所需的 context。"""
    pool, fname = _make_pool_one_node()
    mark_skill_ready(pool, fname)

    candidates = check_candidates(pool)
    for c in candidates:
        if c["node"] == fname:
            assert "title" in c
            assert "weight" in c
            assert "mentions" in c
            assert "body_preview" in c
            assert "status" in c
            break


# ─── 註冊 ───


def test_register_valid_skill():
    """有效的 skill JSON 應被儲存。"""
    pool, fname = _make_pool_one_node()

    skill = {
        "skill_name": "debug-mcp-transport",
        "trigger": "MCP client timeout / transport error",
        "steps": [
            {"step": 1, "action": "check format", "description": "Verify newline JSON"},
        ],
        "source_node": fname,
    }
    result = register_skill(pool, skill)
    assert result["success"]

    # 檢查 skill 檔案存在
    skill_dir = pool / SKILL_DIR
    assert skill_dir.exists()
    json_files = list(skill_dir.glob("*.json"))
    assert len(json_files) > 0

    # 檢查 frontmatter 有 has_skill
    content = (pool / fname).read_text()
    assert "has_skill: true" in content
    assert "skill_path:" in content


def test_register_skill_missing_name():
    """缺少必要欄位 → 拒絕。"""
    pool, fname = _make_pool_one_node()
    result = register_skill(pool, {"trigger": "something"})
    assert not result["success"]
    assert "error" in result


def test_register_skill_no_source_missing_steps():
    """缺少 steps 和 source_node → 拒絕。"""
    pool, fname = _make_pool_one_node()
    result = register_skill(pool, {"skill_name": "test"})
    assert not result["success"]


def test_register_twice_updates():
    """同一 source node 再次註冊 → 覆蓋 skill 檔案。"""
    pool, fname = _make_pool_one_node()

    skill1 = {
        "skill_name": "v1",
        "trigger": "v1 trigger",
        "steps": [{"step": 1, "action": "v1", "description": "v1"}],
        "source_node": fname,
    }
    r1 = register_skill(pool, skill1)

    skill2 = {
        "skill_name": "v2",
        "trigger": "v2 trigger",
        "steps": [{"step": 1, "action": "v2", "description": "v2"}],
        "source_node": fname,
    }
    r2 = register_skill(pool, skill2)
    assert r2["success"]


# ─── Pending 計數 ───


def test_pending_count():
    """pending_skill_count 應回傳 skill_ready node 數量。"""
    pool, fname = _make_pool_one_node()
    assert pending_skill_count(pool) == 0

    mark_skill_ready(pool, fname)
    count = pending_skill_count(pool)
    assert count >= 1


def test_pending_count_after_register():
    """註冊 skill 後，count 應減少（不再 pending）。"""
    pool, fname = _make_pool_one_node()
    mark_skill_ready(pool, fname)
    assert pending_skill_count(pool) >= 1

    skill = {
        "skill_name": "test",
        "trigger": "test",
        "steps": [{"step": 1, "action": "test", "description": "test"}],
        "source_node": fname,
    }
    register_skill(pool, skill)
    # 註冊後應不再 pending
    assert pending_skill_count(pool) == 0


# ─── 過期 ───


def test_expire_stale_marks():
    """超過 SKILL_READY_EXPIRE_DAYS 未轉換 → 清除標記。"""
    pool, fname = _make_pool_one_node(
        timestamp=(datetime.now(timezone.utc) - timedelta(days=SKILL_READY_EXPIRE_DAYS + 5)).isoformat(),
    )
    mark_skill_ready(pool, fname)

    expired = expire_stale_marks(pool)
    assert len(expired) >= 1, "Stale marks should be expired"
    assert fname in expired

    # 確認已清除
    content = (pool / fname).read_text()
    assert "skill_ready: true" not in content
