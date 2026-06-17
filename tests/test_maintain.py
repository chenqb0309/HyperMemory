"""HyperMemory 測試 — 維護循環（Recalc / DreamLoop / Body Link / Sync Parent）"""

import sys
import os
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from hypermemory.core.index import parse_index, update_index_entry, format_index_entry
from hypermemory.core.node import parse_frontmatter, strip_body_links, generate_body_links, extract_body_link_section
from hypermemory.commands.maintain import _recalc, _dreamloop

TS = "2026-06-01T00:00:00+00:00"


def _chain_pool(pointer="b.md"):
    """鏈 A→B→C，B 權重最高（intensity=9）。"""
    tmp = Path(tempfile.mkdtemp(prefix="hm_test_maintain_"))
    (tmp / "a.md").write_text(
        "---\ntype: 2\ntimestamp: 2026-01-01T00:00:00+00:00\nnode_type: 2\n"
        "prenode: null\nnextnodes:\n  - [[b.md]]\nref_by: null\n"
        "intensity: 3\ntotal_mentions: 1\ntags: [test]\n---\n\n# A"
    )
    (tmp / "b.md").write_text(
        "---\ntype: 2\ntimestamp: 2026-03-01T00:00:00+00:00\nnode_type: 2\n"
        "prenode: [[a.md]]\nnextnodes:\n  - [[c.md]]\nref_by: null\n"
        "intensity: 9\ntotal_mentions: 1\ntags: [test]\n---\n\n# B"
    )
    (tmp / "c.md").write_text(
        "---\ntype: 2\ntimestamp: 2026-06-01T00:00:00+00:00\nnode_type: 2\n"
        "prenode: [[b.md]]\nnextnodes: null\nref_by: null\n"
        "intensity: 5\ntotal_mentions: 1\ntags: [test]\n---\n\n# C"
    )
    # index 指向指定的 node
    (tmp / "index.md").write_text(
        "# Index\n《cluster: [test, chain]》 → [[" + pointer + "]]\n"
    )
    return tmp


# ─── Recalc ───


def test_recalc_updates_pointer():
    """recalc 從尾端回溯找到整鏈，執行不 crash。"""
    pool = _chain_pool(pointer="c.md")
    _recalc(pool)

    entries = parse_index((pool / "index.md").read_text())
    found = any("test" in kw and "chain" in kw for kw, _ in entries)
    assert found, "Cluster should still exist"


def test_recalc_no_change_when_correct():
    """pointer 已正確 → 不修改。"""
    pool = _chain_pool(pointer="b.md")
    original = (pool / "index.md").read_text()
    _recalc(pool)
    assert (pool / "index.md").read_text() == original


def test_recalc_graceful_missing_node():
    """指向不存在的 node → 不 crash。"""
    pool = _chain_pool(pointer="ghost.md")
    try:
        _recalc(pool)
    except Exception as e:
        assert False, f"Should not crash: {e}"


def test_recalc_empty_index():
    """空 index → 不 crash。"""
    tmp = Path(tempfile.mkdtemp(prefix="hm_test_recalc_"))
    (tmp / "index.md").write_text("# HyperMemory Pool Index\n")
    try:
        _recalc(tmp)
    except Exception as e:
        assert False, f"Should not crash: {e}"


# ─── DreamLoop ───


def _dreamloop_pool():
    """有重複關鍵字的 index。"""
    tmp = Path(tempfile.mkdtemp(prefix="hm_test_dream_"))
    (tmp / "node.md").write_text(
        "---\ntype: 2\ntimestamp: " + TS + "\nnode_type: 2\n"
        "prenode: null\nnextnodes: null\nref_by: null\n"
        "intensity: 5\ntotal_mentions: 1\ntags: [test]\n---\n\n# Node"
    )
    (tmp / "index.md").write_text(
        "# Index\n"
        "《cluster: [debug, debug, mcp]》 → [[node.md]]\n"
    )
    return tmp


def test_dreamloop_dedup():
    """關鍵字去重。"""
    pool = _dreamloop_pool()
    _dreamloop(pool)

    content = (pool / "index.md").read_text()
    # "debug" 應只出現一次
    count = content.count("debug")
    assert count == 1, f"debug should appear once, got {count}"


def _orphan_pool():
    """有孤立 cluster 的 index。"""
    tmp = Path(tempfile.mkdtemp(prefix="hm_test_orphan_"))
    (tmp / "real.md").write_text(
        "---\ntype: 2\ntimestamp: " + TS + "\nnode_type: 2\n"
        "prenode: null\nnextnodes: null\nref_by: null\n"
        "intensity: 5\ntotal_mentions: 1\ntags: [test]\n---\n\n# Real"
    )
    (tmp / "index.md").write_text(
        "# Index\n"
        "《cluster: [real]》 → [[real.md]]\n"
        "《cluster: [ghost]》 → [[ghost.md]]\n"
    )
    return tmp


def test_dreamloop_orphan_removal():
    """孤立 cluster 移除。"""
    pool = _orphan_pool()
    _dreamloop(pool)

    content = (pool / "index.md").read_text()
    assert "ghost" not in content, "Orphan entry should be removed"
    assert "real" in content, "Real entry should remain"


# ─── Body Link ───


def _node_with_prenode():
    content = (
        "---\ntype: 2\ntimestamp: " + TS + "\nnode_type: 2\n"
        "prenode: [[parent.md]]\nnextnodes:\n  - [[child.md]]\n"
        "ref_by:\n  - [[source.md]]\nintensity: 5\n"
        "total_mentions: 1\ntags: [test]\n---\n\n# Title\n\nContent here."
    )
    return content


def test_body_link_generation():
    """frontmatter 的鏈結應鏡像到 body。"""
    content = _node_with_prenode()
    result = generate_body_links(content)
    assert "## 關聯" in result
    assert "前驅" in result
    assert "後繼" in result
    assert "參考來源" in result


def test_body_link_no_links():
    """無鏈結 → 不產生 ##關聯 區塊。"""
    content = (
        "---\ntype: 2\ntimestamp: " + TS + "\nnode_type: 2\n"
        "prenode: null\nnextnodes: null\nref_by: null\n"
        "intensity: 5\ntotal_mentions: 1\ntags: [test]\n---\n\n# Title\n"
    )
    result = generate_body_links(content)
    assert "## 關聯" not in result


def test_body_link_strip_then_regenerate():
    """strip → regenerate 不產生重複。"""
    content = _node_with_prenode()
    stripped = strip_body_links(content)
    regenerated = generate_body_links(stripped)
    # 只應有一個 ##關聯 區塊
    count = regenerated.count("## 關聯")
    assert count == 1, f"Should have exactly 1 關聯 section, got {count}"


# ─── sync_parent_links ───


def _parent_child_pool():
    tmp = Path(tempfile.mkdtemp(prefix="hm_test_sync_"))
    (tmp / "parent.md").write_text(
        "---\ntype: 2\ntimestamp: " + TS + "\nnode_type: 2\n"
        "prenode: null\nnextnodes: null\nref_by: null\n"
        "intensity: 5\ntotal_mentions: 1\ntags: [test]\n---\n\n# Parent"
    )
    (tmp / "child.md").write_text(
        "---\ntype: 2\ntimestamp: " + TS + "\nnode_type: 2\n"
        "prenode: [[parent.md]]\nnextnodes: null\nref_by: null\n"
        "intensity: 5\ntotal_mentions: 1\ntags: [test]\n---\n\n# Child"
    )
    (tmp / "index.md").write_text("# Index\n")
    return tmp


def test_sync_parent_adds_nextnodes():
    """sync 應在 parent 新增 nextnodes。"""
    from hypermemory.core.index import sync_parent_links
    pool = _parent_child_pool()
    sync_parent_links(pool, "parent.md", "child.md")

    content = (pool / "parent.md").read_text()
    assert "child.md" in content, "Parent should list child in nextnodes"


def test_sync_parent_preserves_existing():
    """sync 不破壞既有 nextnodes。"""
    from hypermemory.core.index import sync_parent_links
    pool = _parent_child_pool()
    # 先加入一個
    sync_parent_links(pool, "parent.md", "child.md")

    # 再加入第二個
    (pool / "another.md").write_text("---\ntype: 2\ntimestamp: " + TS + "\nnode_type: 2\nintensity: 3\n"
        "total_mentions: 1\ntags: [test]\n---\n\n# Another")
    # child 的 prenode 指向 parent，但 another 的 prenode 不一定指向 parent
    # 手動設 another 的 prenode
    (pool / "another.md").write_text(
        "---\ntype: 2\ntimestamp: " + TS + "\nnode_type: 2\n"
        "prenode: [[parent.md]]\nnextnodes: null\nref_by: null\n"
        "intensity: 3\ntotal_mentions: 1\ntags: [test]\n---\n\n# Another"
    )
    sync_parent_links(pool, "parent.md", "another.md")

    content = (pool / "parent.md").read_text()
    assert "child.md" in content
    assert "another.md" in content
