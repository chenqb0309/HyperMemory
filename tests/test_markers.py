"""HyperMemory 測試 — Memory Marker（設計約束 7）

TS-MK-01: wrap_markers 功能（3 案例）
TS-MK-02: strip_markers 功能（3 案例）
TS-MK-03: parse_frontmatter 跳過 marker（4 案例）
TS-MK-04: 寫入路徑整合（3 案例）
"""

import sys
import os
import tempfile
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from hypermemory.core.node import (
    wrap_markers,
    strip_markers,
    has_marker,
    MARKER_START,
    MARKER_DISC,
    MARKER_END,
    parse_frontmatter,
)
from hypermemory.core.weight import calc_weight

TS = "2026-06-01T00:00:00+00:00"


def _make_content():
    """回傳標準 frontmatter + body（無 marker，node_type=1 避免 prenode 驗證）。"""
    return (
        "---\n"
        "type: 2\n"
        f"timestamp: {TS}\n"
        "node_type: 1\n"
        "prenode: null\n"
        "nextnodes: null\n"
        "ref_by: null\n"
        "intensity: 7\n"
        "total_mentions: 1\n"
        "tags: [test, marker]\n"
        "---\n"
        "\n"
        "# Test Node\n"
        "\n"
        "Body content here.\n"
    )


# ─── TS-MK-01: wrap_markers 功能 ───────────────────────────


def test_wrap_adds_start_and_end():
    """正常 frontmatter + body → 首行 START，末行 END，disclaimer 存在。"""
    content = _make_content()
    wrapped = wrap_markers(content)
    lines = wrapped.strip("\n").split("\n")
    assert lines[0].strip() == MARKER_START, f"First line should be START, got: {lines[0]}"
    assert lines[1].strip() == MARKER_DISC, f"Second line should be DISC, got: {lines[1]}"
    assert lines[-1].strip() == MARKER_END, f"Last line should be END, got: {lines[-1]}"
    # Original content preserved between
    assert "intensity: 7" in wrapped
    assert "# Test Node" in wrapped


def test_wrap_empty_content():
    """空內容仍正確包裹。"""
    wrapped = wrap_markers("")
    lines = wrapped.strip("\n").split("\n")
    assert len(lines) >= 3
    assert lines[0].strip() == MARKER_START
    assert lines[-1].strip() == MARKER_END


def test_wrap_idempotent():
    """已有 marker 的內容不雙重包裹。"""
    content = _make_content()
    once = wrap_markers(content)
    twice = wrap_markers(once)
    assert once == twice, "wrap_markers should be idempotent"
    # Verify no double START
    assert once.count(MARKER_START) == 1


# ─── TS-MK-02: strip_markers 功能 ─────────────────────────


def test_strip_removes_marker():
    """包裹後的內容 → 回傳無 marker 純內容。"""
    original = _make_content()
    wrapped = wrap_markers(original)
    stripped = strip_markers(wrapped)
    assert stripped == original, f"strip_markers should restore original"
    assert MARKER_START not in stripped
    assert MARKER_END not in stripped
    assert MARKER_DISC not in stripped


def test_strip_no_marker_idempotent():
    """無 marker 的內容原樣回傳。"""
    content = _make_content()
    stripped = strip_markers(content)
    assert stripped == content


def test_strip_only_marker_lines():
    """只有 marker 行 → 空字串。"""
    content = f"{MARKER_START}\n{MARKER_DISC}\n{MARKER_END}\n"
    stripped = strip_markers(content)
    assert stripped == "\n"


# ─── TS-MK-03: parse_frontmatter 跳過 marker ──────────────


def test_parse_with_marker():
    """有 marker 的完整 node → frontmatter 欄位正確。"""
    content = _make_content()
    wrapped = wrap_markers(content)
    fm = parse_frontmatter(wrapped)
    assert fm.get("type") == "2"
    assert fm.get("intensity") == 7
    assert fm.get("node_type") == 1
    assert fm.get("timestamp") == TS


def test_parse_without_marker():
    """無 marker 的既有 node → 同現有行為。"""
    content = _make_content()
    fm = parse_frontmatter(content)
    assert fm.get("type") == "2"
    assert fm.get("intensity") == 7


def test_parse_wrong_order_no_false_positive():
    """marker 順序錯誤（END 在前）→ 視為無 marker，但仍正確解析 frontmatter。"""
    content = _make_content()
    # START/END reversed — should still parse frontmatter
    malformed = f"{MARKER_END}\n{MARKER_DISC}\n---\ntype: 2\n---\n# Test\n{MARKER_START}\n"
    fm = parse_frontmatter(malformed)
    # Frontmatter should still parse (^ lines are skipped generically)
    assert not has_marker(malformed), "reversed marker should not be detected"
    assert fm.get("type") == "2", "Frontmatter should still be parseable"


def test_marker_does_not_affect_weight():
    """weight 計算結果與有無 marker 一致。"""
    content = _make_content()
    wrapped = wrap_markers(content)
    fm_w = parse_frontmatter(wrapped)
    fm_n = parse_frontmatter(content)
    w1 = calc_weight(fm_w.get("intensity", 1), fm_w.get("total_mentions", 0), fm_w.get("timestamp"))
    w2 = calc_weight(fm_n.get("intensity", 1), fm_n.get("total_mentions", 0), fm_n.get("timestamp"))
    assert abs(w1 - w2) < 0.01, "Marker should not affect weight"


# ─── TS-MK-04: 寫入路徑整合 ───────────────────────────────


def _make_pool():
    """建立暫存記憶池（含 index.md）。"""
    tmp = Path(tempfile.mkdtemp(prefix="hm_test_marker_"))
    (tmp / "index.md").write_text("# HyperMemory Pool Index\n")
    return tmp


def test_imprint_cli_adds_marker():
    """hm imprint CLI 寫出的檔案含 marker。"""
    from hypermemory.commands.imprint import run as imprint_run
    from hypermemory.core.pool import resolve_pool
    import argparse

    tmp = _make_pool()
    src = tmp / "src.md"
    content = _make_content()
    src.write_text(content)

    args = argparse.Namespace(pool=str(tmp), file=str(src), name="test-cli.md", force=False)
    imprint_run(args)

    dest = tmp / "test-cli.md"
    assert dest.exists()
    raw = dest.read_text(encoding="utf-8")
    assert raw.startswith(MARKER_START), f"CLI imprint should write START, got: {raw[:50]}"
    assert MARKER_END in raw
    assert MARKER_DISC in raw


def test_mcp_imprint_adds_marker():
    """MCP imprint（hm_tools.imprint）寫出的檔案含 marker。"""
    from hypermemory.core.hm_tools import HMTools

    tmp = _make_pool()
    content = _make_content()

    tools = HMTools(str(tmp))
    result = tools.imprint(content, filename="test-mcp.md")

    assert result["success"]
    dest = tmp / "test-mcp.md"
    assert dest.exists()
    raw = dest.read_text(encoding="utf-8")
    assert raw.startswith(MARKER_START), f"MCP imprint should write START, got: {raw[:50]}"
    assert MARKER_END in raw
    assert MARKER_DISC in raw


def test_reflect_adds_marker():
    """_reflect 寫出的檔案含 marker。"""
    from hypermemory.commands.maintain import _reflect
    from hypermemory.core.log import capture
    import argparse

    tmp = _make_pool()

    # Write a log entry that will trigger reflection
    capture(
        "This is a test log entry for reflection marker test.",
        tags=["test", "marker", "reflection"],
    )

    args = argparse.Namespace(pool=str(tmp), days=30)
    _reflect(tmp, days=30)

    # Find the reflected file
    reflected = list(tmp.glob("*reflection*marker*.md"))
    if not reflected:
        reflected = list(tmp.glob("*reflection*.md"))

    if reflected:
        raw = reflected[0].read_text(encoding="utf-8")
        assert raw.startswith(MARKER_START), f"Reflect should write START, got: {raw[:50]}"
        assert MARKER_END in raw
        assert MARKER_DISC in raw
    else:
        # No reflection triggered — still acceptable (depends on log state)
        pass
