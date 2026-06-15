"""HyperMemory 核心測試 — cluster"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from hypermemory.core.cluster import match_keywords, find_best_cluster


SAMPLE_ENTRIES = [
    (["deadlock", "concurrency", "transaction", "lock"], "2026-06-10-deadlock.md"),
    (["door-lock", "key", "stuck"], "2026-06-09-door-lock.md"),
    (["hypermemory", "cli", "phase-1", "milestone"], "2026-06-15-hm-cli.md"),
]


def test_match_keywords_exact():
    m, t, s = match_keywords(["deadlock", "lock"], ["deadlock", "concurrency", "lock"])
    assert m == 2
    assert s == 1.0


def test_match_keywords_partial():
    m, t, s = match_keywords(["deadlock", "python"], ["deadlock", "concurrency"])
    assert m == 1
    assert s == 0.5


def test_match_keywords_none():
    m, t, s = match_keywords(["python"], ["door-lock", "key"])
    assert m == 0
    assert s == 0.0


def test_match_keywords_empty():
    m, t, s = match_keywords([], ["a", "b"])
    assert m == 0
    assert s == 0.0


def test_find_best_cluster_exact():
    result = find_best_cluster(["deadlock", "transaction"], SAMPLE_ENTRIES)
    kw, node, score = result[:3]
    assert node == "2026-06-10-deadlock.md"
    assert score > 0


def test_chinese_substring_match():
    """中文 substring 匹配：查詢「設計」可命中 cluster 中的「設計哲學」"""
    entries = [(["設計哲學", "portable-doc", "vault-as-source"], "design.md")]
    result = find_best_cluster(["設計"], entries)
    kw, node, score = result[:3]
    assert node == "design.md"
    assert score > 0
    result = find_best_cluster(["設計", "哲學"], entries)
    kw, node, score = result[:3]
    assert node == "design.md"


def test_find_best_cluster_no_match():
    result = find_best_cluster(["python", "javascript"], SAMPLE_ENTRIES)
    kw, node, score = result[:3]
    assert kw is None
    assert node is None


def test_find_best_cluster_empty():
    result = find_best_cluster([], SAMPLE_ENTRIES)
    kw, node, score = result[:3]
    assert kw is None
    assert node is None


def test_find_best_cluster_empty_entries():
    result = find_best_cluster(["test"], [])
    kw, node, score = result[:3]
    assert kw is None
    assert node is None
