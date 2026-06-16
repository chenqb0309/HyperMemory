"""HyperMemory 測試 — hm doctor 自我診斷"""

import sys
import os
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from hypermemory.commands.doctor import run_doctor


def _healthy_pool():
    """建立一個健康的記憶池。"""
    tmp = Path(tempfile.mkdtemp(prefix="hm_test_doctor_"))
    (tmp / "index.md").write_text(
        "# HyperMemory Pool Index\n"
        "《cluster: [test, alpha]》 → [[alpha.md]]\n"
    )
    (tmp / "alpha.md").write_text("""---
type: 2
timestamp: 2026-06-01T00:00:00+00:00
node_type: 2
prenode: null
nextnodes: []
ref_by: []
intensity: 5
total_mentions: 3
tags: [test]
---

# Alpha
""")
    return tmp


def _pool_with_dead_ref():
    """記憶池有 dead ref（index 指向不存在的檔案）。"""
    tmp = Path(tempfile.mkdtemp(prefix="hm_test_doctor_"))
    (tmp / "index.md").write_text(
        "# HyperMemory Pool Index\n"
        "《cluster: [dead]》 → [[ghost.md]]\n"
    )
    return tmp


def _pool_with_archive():
    """記憶池有歸檔 node。"""
    tmp = _healthy_pool()
    archive = tmp / "archive_index.md"
    archive.write_text(
        "# HyperMemory Pool Index (Archived)\n"
        "《cluster: [old, cold]》 → [[old.md]]\n"
    )
    return tmp


def _pool_with_background():
    """記憶池有背景資料。"""
    tmp = _healthy_pool()
    bg = tmp / "background"
    bg.mkdir()
    import json
    (bg / "機.json").write_text(
        json.dumps({"category": "機", "entries": []}, ensure_ascii=False, indent=2)
    )
    return tmp


def test_doctor_healthy_pool():
    """健康池 → 全部 pass。"""
    pool = _healthy_pool()
    result = run_doctor(pool)

    assert result["healthy"] is True
    assert result["pool_exists"] is True
    assert result["index_exists"] is True
    assert result["dead_refs"] == 0
    assert result["orphan_nodes"] == 0


def test_doctor_dead_ref():
    """有 dead ref 的 pool → healthy=False + 列出問題。"""
    pool = _pool_with_dead_ref()
    result = run_doctor(pool)

    assert result["healthy"] is False
    assert result["dead_refs"] == 1
    assert "ghost.md" in str(result.get("issues", []))


def test_doctor_missing_pool():
    """不存在的 pool 路徑 → 問題回報。"""
    result = run_doctor(Path("/tmp/nonexistent_pool_xyz"))
    assert result["healthy"] is False
    assert result["pool_exists"] is False


def test_doctor_missing_index():
    """index.md 不存在 → 問題回報。"""
    tmp = Path(tempfile.mkdtemp(prefix="hm_test_doctor_"))
    result = run_doctor(tmp)
    assert result["healthy"] is False
    assert result["index_exists"] is False


def test_doctor_archive_exists():
    """歸檔存在時應顯示。"""
    pool = _pool_with_archive()
    result = run_doctor(pool)
    assert result["archive_exists"] is True
    assert result["archived_nodes"] >= 1


def test_doctor_background_exists():
    """背景資料存在時應顯示。"""
    pool = _pool_with_background()
    result = run_doctor(pool)
    assert result["background_exists"] is True
    assert "機" in result.get("background_categories", {})


def test_doctor_skill_ready_check():
    """檢查過期的 skill_ready 標記。"""
    from datetime import datetime, timezone, timedelta
    pool = _healthy_pool()

    # 新增一個有過期 skill_ready 的 node
    ts = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat()
    content = (pool / "alpha.md").read_text()
    content += f"\nskill_ready: true\nskill_ready_at: {ts}\n"
    (pool / "alpha.md").write_text(content)

    result = run_doctor(pool)
    assert result.get("stale_skill_ready", 0) >= 1 or not result["healthy"]


def test_doctor_empty_pool():
    """空池（只有 index，無 node）不算完全健康。"""
    tmp = Path(tempfile.mkdtemp(prefix="hm_test_doctor_"))
    (tmp / "index.md").write_text("# HyperMemory Pool Index\n")
    result = run_doctor(tmp)
    assert result["pool_exists"] is True
    assert result["index_exists"] is True
    assert result["node_count"] == 0


def test_doctor_version_check():
    """檢查 HM 版本（從 package metadata）。"""
    pool = _healthy_pool()
    result = run_doctor(pool)
    assert "version" in result
    assert len(result["version"]) > 0
