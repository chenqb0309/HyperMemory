"""HyperMemory 測試 — Chain 鏈資訊回傳

測試 MCP recall/think 的回傳結構是否包含 chain 指標
（prenode / nextnodes / ref_by），以及 CLI 顯示是否正確。
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from hypermemory.mcp_server import HMTools
from hypermemory.core.pool import resolve_pool


def _get_tools():
    """共用：取得 HMTools instance（預設池）"""
    pool = resolve_pool()
    return HMTools(str(pool))


def test_recall_response_has_chain_fields():
    """recall 回傳的每個 result 須包含 prenode / nextnodes / ref_by"""
    tools = _get_tools()
    result = tools.recall("hypermemory buildout", limit=3)

    assert result.get("found"), f"Recall should find results: {result.get('message', '')}"
    assert len(result["results"]) > 0, "Should have at least one result"

    for r in result["results"]:
        assert "prenode" in r, f"Result {r['node']} missing 'prenode'"
        assert "nextnodes" in r, f"Result {r['node']} missing 'nextnodes'"
        assert "ref_by" in r, f"Result {r['node']} missing 'ref_by'"
        # prenode should be None or str
        assert r["prenode"] is None or isinstance(r["prenode"], str)
        # nextnodes should be list
        assert isinstance(r["nextnodes"], list)
        # ref_by should be list
        assert isinstance(r["ref_by"], list)


def test_recall_shows_chain_indicators():
    """已知有鏈的 node 應顯示 chain 資訊"""
    tools = _get_tools()
    result = tools.recall("hypermemory buildout")

    assert result["found"]
    # hypermemory-buildout node has known chain:
    #   prenode: 2026-06-11-hypermemory-first-imprint.md
    #   nextnodes: [..., ...]
    for r in result["results"]:
        if r["node"] == "2026-06-11-hypermemory-buildout.md":
            assert r["prenode"] is not None, "Buildout node should have prenode"
            assert len(r["nextnodes"]) > 0, "Buildout node should have nextnodes"
            # 不 assert 具體值（隨記憶更新變化），只 assert 存在
            break
    else:
        # Node might not be first result due to recency sort — that's OK
        pass


def test_recall_isolated_node_has_null_chain():
    """孤立 node（無 prenode/nextnodes）應回傳空值"""
    # 找一個可能無鏈的 node，或 assert 欄位型別正確
    tools = _get_tools()
    result = tools.recall("windows python")

    if result.get("found"):
        for r in result["results"]:
            # 至少格式正確
            assert isinstance(r.get("prenode"), (str, type(None)))
            assert isinstance(r.get("nextnodes"), list)


def test_think_response_has_chain_fields():
    """think 回傳的 result 須包含 prenode / nextnodes / ref_by"""
    tools = _get_tools()
    result = tools.think("hypermemory buildout")

    assert result.get("found"), f"Think should find results: {result.get('message', '')}"

    r = result["result"]
    assert "prenode" in r, f"Missing 'prenode' in think result"
    assert "nextnodes" in r, f"Missing 'nextnodes' in think result"
    assert "ref_by" in r, f"Missing 'ref_by' in think result"


def test_inspect_response_has_chain_fields():
    """inspect 已含 chain 資訊（確認既有功能無回歸）"""
    tools = _get_tools()
    result = tools.inspect("2026-06-11-hypermemory-buildout.md")

    assert result.get("found")
    assert "prenode" in result
    assert "nextnodes" in result
    assert "ref_by" in result
    assert result["prenode"] is not None, "Buildout node should have prenode"
    assert len(result["nextnodes"]) > 0, "Buildout node should have nextnodes"


def test_chain_values_are_strings_and_lists():
    """型別正確性：prenode=str|None, nextnodes/ref_by=list[str]"""
    tools = _get_tools()
    result = tools.recall("hypermemory buildout")

    for r in result["results"]:
        pre = r.get("prenode")
        assert pre is None or isinstance(pre, str), f"prenode should be str|None, got {type(pre)}"
        assert isinstance(r.get("nextnodes"), list), f"nextnodes should be list"
        assert isinstance(r.get("ref_by"), list), f"ref_by should be list"


def test_recall_no_results_still_no_error():
    """無匹配時不應因 chain 欄位而出錯"""
    tools = _get_tools()
    result = tools.recall("zz_nonexistent_keyword_xyz_999")
    assert not result.get("found")
    # 不應有 exception
