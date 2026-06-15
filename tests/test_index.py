"""HyperMemory 核心測試 — index"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from hypermemory.core.index import parse_index, match_cluster, format_index_entry, update_index_entry


SAMPLE_INDEX = """# HyperMemory Pool Index

《cluster: [deadlock, concurrency, transaction, lock]》 → [[2026-06-10-deadlock.md]]
《cluster: [door-lock, key, stuck]》 → [[2026-06-09-door-lock.md]]
"""


def test_parse_index():
    entries = parse_index(SAMPLE_INDEX)
    assert len(entries) == 2
    assert entries[0] == (["deadlock", "concurrency", "transaction", "lock"], "2026-06-10-deadlock.md")
    assert entries[1] == (["door-lock", "key", "stuck"], "2026-06-09-door-lock.md")


def test_parse_empty():
    assert parse_index("") == []
    assert parse_index("# No clusters") == []


def test_match_cluster_exact():
    entries = parse_index(SAMPLE_INDEX)
    kw, node, score = match_cluster(["deadlock", "concurrency"], entries)
    assert node == "2026-06-10-deadlock.md"
    assert score > 0


def test_match_cluster_partial():
    entries = parse_index(SAMPLE_INDEX)
    kw, node, score = match_cluster(["lock"], entries)
    # "lock" appears as a keyword in the first cluster
    assert node is not None
    assert score > 0


def test_match_cluster_no_match():
    entries = parse_index(SAMPLE_INDEX)
    kw, node, score = match_cluster(["python", "javascript"], entries)
    assert node is None
    assert score == 0


def test_format_entry():
    result = format_index_entry(["a", "b", "c"], "node.md")
    assert "a, b, c" in result
    assert "node.md" in result


def test_update_index_entry():
    result = update_index_entry(
        SAMPLE_INDEX,
        "2026-06-10-deadlock.md",
        "2026-06-11-new-deadlock.md",
        new_keywords=["sql"],
    )
    # Old node should not appear
    assert "2026-06-10-deadlock.md" not in result, "Old node should be replaced"
    # New node should be there
    assert "2026-06-11-new-deadlock.md" in result
    # New keywords should be merged
    assert "sql" in result
