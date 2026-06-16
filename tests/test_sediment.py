"""HyperMemory 測試 — 舊 Node 沈降管線（Sedimentation）

測試冷偵測、歸檔、背景資料儲存三大行為。
"""

import sys
import os
import json
import tempfile
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from hypermemory.core.sediment import (
    is_cold_node,
    COLD_WEIGHT_THRESHOLD,
    MIN_NODE_AGE_DAYS,
    archive_node,
    sediment_pool,
    BACKGROUND_DIR,
)


# ─── 冷偵測（純函數，不需 pool） ───


def _make_fm(ts_days_ago=None, node_type=1, intensity=3):
    """建立模擬 frontmatter dict。"""
    fm = {"node_type": node_type, "intensity": intensity}
    if ts_days_ago is not None:
        ts = (datetime.now(timezone.utc) - timedelta(days=ts_days_ago)).isoformat()
        fm["timestamp"] = ts
    return fm


def test_cold_high_weight():
    """weight > threshold → 不 cold"""
    fm = _make_fm(ts_days_ago=60)
    assert not is_cold_node(fm, COLD_WEIGHT_THRESHOLD + 1.0)


def test_cold_low_weight_old():
    """weight < threshold + 夠老 → cold"""
    fm = _make_fm(ts_days_ago=30)
    assert is_cold_node(fm, COLD_WEIGHT_THRESHOLD - 0.5)


def test_cold_recent_node_skipped():
    """weight < threshold 但太新 → 不 cold"""
    fm = _make_fm(ts_days_ago=3)  # 3 天
    assert not is_cold_node(fm, COLD_WEIGHT_THRESHOLD - 0.5)


def test_cold_no_timestamp():
    """無 timestamp → age check 跳過（保守處理，不 cold）"""
    fm = _make_fm(ts_days_ago=None)
    assert not is_cold_node(fm, COLD_WEIGHT_THRESHOLD - 0.5)


def test_cold_zero_weight():
    """weight=0 → cold（如果夠老）"""
    fm = _make_fm(ts_days_ago=30)
    assert is_cold_node(fm, 0)


def test_cold_boundary_age():
    """剛好等於 MIN_NODE_AGE_DAYS → cold"""
    fm = _make_fm(ts_days_ago=MIN_NODE_AGE_DAYS)
    assert is_cold_node(fm, COLD_WEIGHT_THRESHOLD - 0.5)


def test_cold_just_below_threshold():
    """稍微低於 threshold → cold if old enough"""
    fm = _make_fm(ts_days_ago=60)
    assert is_cold_node(fm, COLD_WEIGHT_THRESHOLD - 0.01)


# ─── 歸檔與背景資料（需實體 pool） ───


def _setup_temp_pool():
    """建立暫存記憶池供測試。"""
    tmp = Path(tempfile.mkdtemp(prefix="hm_test_sediment_"))
    # index.md
    (tmp / "index.md").write_text(
        "# HyperMemory Pool Index\n\n"
        "《cluster: [test, high]》 → [[2026-01-01-high-weight.md]]\n"
        "《cluster: [test, cold]》 → [[2025-06-01-cold-node.md]]\n"
    )
    # High weight node (有 intensity, 有 timestamp)
    high_content = """---
type: 2
timestamp: 2026-01-01T00:00:00+00:00
node_type: 1
prenode: null
nextnodes: []
ref_by: []
intensity: 8
total_mentions: 5
tags: [test, high]
---

# High Weight Node
"""
    (tmp / "2026-01-01-high-weight.md").write_text(high_content)

    # Cold node (low intensity, old)
    cold_content = """---
type: 2
timestamp: 2025-06-01T00:00:00+00:00
node_type: 1
prenode: null
nextnodes: []
ref_by: []
intensity: 1
total_mentions: 0
tags: [test, cold]
dimensions:
  機: WSL
  料: Python 3.11
---

# Cold Node
Some old info about WSL setup.
"""
    (tmp / "2025-06-01-cold-node.md").write_text(cold_content)

    return tmp


def test_archive_node_removes_from_active_index():
    """archive_node 應從 active index.md 移除該 node 的條目。"""
    pool = _setup_temp_pool()
    fm = {"node_type": 1, "intensity": 2, "tags": ["test"]}
    result = archive_node(pool, "2025-06-01-cold-node.md", fm)
    assert result["success"]

    # Verify removed from active index
    active = (pool / "index.md").read_text()
    assert "2025-06-01-cold-node.md" not in active, "Should be removed from active index"
    assert "2026-01-01-high-weight.md" in active, "Other nodes should remain"

    # Verify added to archive index
    archive_path = pool / "archive_index.md"
    assert archive_path.exists(), "Archive index should exist"
    archive_content = archive_path.read_text()
    assert "2025-06-01-cold-node.md" in archive_content, "Should appear in archive index"


def test_archive_node_creates_background_json():
    """archive_node 應建立 background JSON 檔案。"""
    pool = _setup_temp_pool()
    fm = {"node_type": 1, "intensity": 2, "tags": ["test", "cold"],
          "dimensions": {"機": "WSL", "料": "Python 3.11"}}
    result = archive_node(pool, "2025-06-01-cold-node.md", fm)
    assert result["success"]

    # Check background directory
    bg_dir = pool / BACKGROUND_DIR
    assert bg_dir.exists(), "Background dir should exist"

    # Should have at least one JSON file
    json_files = list(bg_dir.glob("*.json"))
    assert len(json_files) > 0, "Should have background JSON files"

    # Verify content
    # The node has 機=WSL and 料=Python, so 機.json should exist
    machine_file = bg_dir / "機.json"
    if machine_file.exists():
        data = json.loads(machine_file.read_text())
        assert "entries" in data
        assert len(data["entries"]) > 0
        entry = data["entries"][0]
        assert "source" in entry
        assert "fact" in entry


def test_archive_preserves_node_file():
    """歸檔不應刪除原始 node 檔案。"""
    pool = _setup_temp_pool()
    fm = {"node_type": 1, "intensity": 2, "tags": ["test"]}
    archive_node(pool, "2025-06-01-cold-node.md", fm)
    # File should still exist
    assert (pool / "2025-06-01-cold-node.md").exists(), "Node file should be preserved"


def test_sediment_pool_integration():
    """sediment_pool 應正確掃描並歸檔冷 node。"""
    pool = _setup_temp_pool()
    result = sediment_pool(pool)

    assert result["archived_count"] >= 1, "At least one node should be archived"
    assert "2025-06-01-cold-node.md" in result["archived"], "Cold node should be archived"
    assert "2026-01-01-high-weight.md" not in result["archived"], "High weight node should NOT be archived"

    # Verify archive index
    archive_path = pool / "archive_index.md"
    assert archive_path.exists()
    assert "2025-06-01-cold-node.md" in archive_path.read_text()


def test_sediment_no_double_archive():
    """已歸檔的 node 不應被再次歸檔（已在 archive index 中）。"""
    pool = _setup_temp_pool()
    result1 = sediment_pool(pool)
    assert result1["archived_count"] >= 1

    # Run again
    result2 = sediment_pool(pool)
    assert result2["archived_count"] == 0, "No new nodes should be archived on second run"


def test_sediment_dry_run():
    """dry_run=True 不實際修改任何檔案。"""
    pool = _setup_temp_pool()
    original_index = (pool / "index.md").read_text()

    result = sediment_pool(pool, dry_run=True)
    assert result["candidates"] >= 1, "Should detect candidates"
    assert result["archived_count"] == 0, "Should not archive in dry run"

    # Index unchanged
    assert (pool / "index.md").read_text() == original_index
    assert not (pool / "archive_index.md").exists(), "Should not create archive index"
