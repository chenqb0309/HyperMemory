"""HyperMemory 測試 — 語義聯想（第三層 Associative Recall）

測試從 node body 提取關鍵詞、二次 query index、回傳 suggestions。
"""

import sys
import os
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from hypermemory.core.association import extract_body_keywords, associative_recall
from hypermemory.core.pool import resolve_pool


# ─── Body 關鍵詞提取（純函數） ───


def test_extract_english_keywords():
    """英文 body 提取高頻實詞。"""
    body = "HyperMemory uses cluster keyword matching instead of embedding based semantic search because experience keywords naturally overlap with query keywords."
    kw = extract_body_keywords(body)
    assert len(kw) > 0, "Should extract keywords from English body"
    assert "hypermemory" in kw or "cluster" in kw or "keyword" in kw or "matching" in kw
    # Stopwords should be filtered
    assert "the" not in kw
    assert "with" not in kw
    assert "of" not in kw


def test_extract_chinese_keywords():
    """中文 body 提取 2-3 字片語。"""
    body = "HyperMemory 使用 cluster 關鍵字比對取代 embedding 語義搜尋，因為經驗的關鍵字自然與問題的關鍵字重疊。"
    kw = extract_body_keywords(body)
    assert len(kw) > 0, "Should extract Chinese segments"
    # 應包含「關鍵字」「語義」「搜尋」「比對」等
    cjk_kw = [k for k in kw if any('\u4e00' <= c <= '\u9fff' for c in k)]
    assert len(cjk_kw) > 0, "Should extract CJK segments"


def test_extract_no_stopwords():
    """Stopwords（的、了、是、在）不應出現在結果中。"""
    body = "HyperMemory 使用的是 cluster 的關鍵字比對的機制。系統了已經測試了。"
    kw = extract_body_keywords(body)
    # Stopwords like 的是了應該被過濾
    for stopword in ["的是", "的關", "的機", "了已"]:
        assert stopword not in kw, f"Stopword '{stopword}' should be filtered"


def test_extract_empty_body():
    """空 body → 空列表。"""
    assert extract_body_keywords("") == []
    assert extract_body_keywords("   ") == []


def test_extract_short_body():
    """body 太短（< 20 chars）→ 空列表（無意義）。"""
    assert extract_body_keywords("Hello world") == []


def test_extract_max_keywords():
    """max_keywords 參數應限制回傳數量。"""
    body = "Python JavaScript TypeScript Rust Go Swift Kotlin Java C++ C Ruby PHP Perl Lua Haskell Scala Dart"
    kw = extract_body_keywords(body, max_keywords=3)
    assert len(kw) <= 3, f"Should respect max_keywords=3, got {len(kw)}"


def test_extract_deduplicates():
    """重複的關鍵詞應去重。"""
    body = "debug debug debug server server client client error error"
    kw = extract_body_keywords(body)
    assert len(kw) == len(set(kw)), "Keywords should be deduplicated"


# ─── 語義聯想（需 temp pool） ───


def _make_pool_for_association():
    """建立一個有多個相關 node 的暫存記憶池。

    Node A: 關於 MCP debug（body 含 WSL, stdio, JSON-RPC 等）
    Node B: 關於 WSL Python 環境（body 含 WSL, Python, uv）
    Node C: 關於 Kanban DB（body 含 SQLite, WAL, corruption）
    """
    tmp = Path(tempfile.mkdtemp(prefix="hm_test_assoc_"))

    nodes = {
        "2026-06-15-mcp-debug.md": {
            "intensity": 5,
            "tags": ["hypermemory", "mcp", "debug"],
            "body": "Debug MCP protocol on WSL with newline JSON and stdio transport. JSON-RPC without Content-Length header. protocolVersion echo fix.",
            "title": "MCP Debug",
        },
        "2026-06-15-wsl-python.md": {
            "intensity": 4,
            "tags": ["wsl", "python", "env"],
            "body": "WSL Python toolchain setup: python3.12 with uv package manager. pip not available directly. Use venv for isolation.",
            "title": "WSL Python",
        },
        "2026-06-11-kanban-db.md": {
            "intensity": 6,
            "tags": ["kanban", "sqlite", "corruption"],
            "body": "Kanban DB corruption on WSL due to SQLite WAL file issues. root cause was parallel directory access. recovery via session search.",
            "title": "Kanban DB Corruption",
        },
        "2026-06-10-unrelated.md": {
            "intensity": 2,
            "tags": ["personal"],
            "body": "Personal note about daily journal and task tracking. Nothing technical here.",
            "title": "Personal Journal",
        },
    }

    index_lines = ["# HyperMemory Pool Index\n"]
    for filename, data in nodes.items():
        tags_str = ", ".join(f'"{t}"' for t in data.get("tags", []))
        content = f"""---
type: 2
timestamp: 2026-06-15T00:00:00+00:00
node_type: 1
prenode: null
nextnodes: null
ref_by: null
intensity: {data['intensity']}
total_mentions: 1
tags: [{tags_str}]
---

# {data['title']}

{data['body']}
"""
        (tmp / filename).write_text(content)
        index_lines.append(
            f"《cluster: [{filename.replace('.md','').replace('-',' ')}]》 → [[{filename}]]\n"
        )
    (tmp / "index.md").write_text("".join(index_lines))
    return tmp


def test_association_finds_related():
    """從 MCP debug node 的 body 提取關鍵詞後，應找到相關的 WSL node。"""
    pool = _make_pool_for_association()
    result = associative_recall(pool, "2026-06-15-mcp-debug.md", top_k=3)

    assert result["found"]
    assert len(result["suggestions"]) > 0
    nodes = [s["node"] for s in result["suggestions"]]
    # WSL Python node should be suggested (shares "wsl" keyword)
    assert "2026-06-15-wsl-python.md" in nodes, "WSL node should be suggested"


def test_association_excludes_source():
    """不應將 source node 自己當作 suggestion。"""
    pool = _make_pool_for_association()
    result = associative_recall(pool, "2026-06-15-mcp-debug.md")

    nodes = [s["node"] for s in result["suggestions"]]
    assert "2026-06-15-mcp-debug.md" not in nodes, "Source node should not be suggested"


def test_association_limit():
    """top_k 應限制 suggestion 數量。"""
    pool = _make_pool_for_association()
    result = associative_recall(pool, "2026-06-15-mcp-debug.md", top_k=1)

    assert len(result["suggestions"]) <= 1


def test_association_scores():
    """每個 suggestion 應包含 score 和 match_keywords。"""
    pool = _make_pool_for_association()
    result = associative_recall(pool, "2026-06-15-mcp-debug.md")

    for s in result["suggestions"]:
        assert "node" in s
        assert "title" in s
        assert "score" in s
        assert "match_keywords" in s


def test_association_isolated_node_no_suggestions():
    """無相關 node 的孤立 query → suggestions 為空。"""
    pool = _make_pool_for_association()
    result = associative_recall(pool, "2026-06-10-unrelated.md")

    # Personal journal body has no technical keywords → no suggestions
    assert result["found"]
    assert len(result["suggestions"]) == 0


def test_association_unknown_node():
    """不存在的 node → found=False。"""
    pool = _make_pool_for_association()
    result = associative_recall(pool, "nonexistent.md")
    assert not result["found"]


def test_association_keywords_from_body():
    """回傳的 match_keywords 應為實際匹配到的關鍵詞，非空列表。"""
    pool = _make_pool_for_association()
    result = associative_recall(pool, "2026-06-15-mcp-debug.md")

    for s in result["suggestions"]:
        assert len(s["match_keywords"]) > 0, "match_keywords should not be empty"
        # All match_keywords should be strings
        for kw in s["match_keywords"]:
            assert isinstance(kw, str) and len(kw) > 0
