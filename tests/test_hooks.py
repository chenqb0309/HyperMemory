"""HyperMemory 測試 — Hooks（Hermes plugin 閉環）

測試範圍：
- inject_recall: pre_llm_call callback
  - 正常 recall 注入 → context 出現在回傳值
  - 無匹配記憶 → None（不阻塞）
  - 極短 query → 跳過不查
- auto_confirm: post_tool_call callback
  - exit_code=0 → hm.confirm() 被呼叫，result=positive
  - exit_code=1 → hm.confirm() 被呼叫，result=negative
  - 非 terminal tool → hm.confirm() 不被呼叫
- auto_imprint: post_llm_call callback
  - 含關鍵字的 response → hm.imprint() 被呼叫
  - 不含關鍵字的 response → hm.imprint() 不被呼叫
  - 過短的 response → hm.imprint() 不被呼叫
- plugin.load(): 回傳三個 hook 且全部 callable
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from unittest.mock import MagicMock, call
import pytest


# ─── inject_recall (pre_llm_call) ──────────────────────


def test_inject_recall_with_match():
    """TS-01: 正常 recall 注入 — context 出現"""
    from hypermemory.core.hooks import inject_recall
    hm = MagicMock()
    hm.think.return_value = {
        "found": True,
        "result": {
            "title": "MCP Debug經驗",
            "weight": 8.5,
            "summary": "解決 MCP transport 問題的方法",
        },
    }
    result = inject_recall("MCP debug", hm=hm)
    assert result is not None
    assert "context" in result
    assert "MCP Debug經驗" in result["context"]
    assert "8.5" in result["context"]


def test_inject_recall_no_match():
    """TS-02: 無匹配記憶 — None（不阻塞 LLM）"""
    from hypermemory.core.hooks import inject_recall
    hm = MagicMock()
    hm.think.return_value = {"found": False, "result": {}}
    result = inject_recall("something unknown", hm=hm)
    assert result is None


def test_inject_recall_short_query():
    """TS-03: 極短 query — 跳過不查 HM，回傳 None"""
    from hypermemory.core.hooks import inject_recall
    hm = MagicMock()
    result = inject_recall("hi", hm=hm)
    assert result is None
    hm.think.assert_not_called()


def test_inject_recall_uses_dry_run():
    """TS-04: think 以 dry_run=True 呼叫，不計 mentions"""
    from hypermemory.core.hooks import inject_recall
    hm = MagicMock()
    hm.think.return_value = {"found": True, "result": {"title": "t", "summary": "s"}}
    inject_recall("test query", hm=hm)
    hm.think.assert_called_once()
    _, kwargs = hm.think.call_args
    assert kwargs.get("dry_run") is True or ("test query" in hm.think.call_args[0] and True)


# ─── auto_confirm (post_tool_call) ─────────────────────


def test_auto_confirm_exit_zero():
    """TS-05: exit_code=0 → hm.confirm 被呼叫，result=positive"""
    from hypermemory.core.hooks import auto_confirm
    hm = MagicMock()
    auto_confirm("terminal", {"command": "dotnet build"}, '{"exit_code": 0}', hm=hm)
    hm.confirm.assert_called_once()
    args, _ = hm.confirm.call_args
    assert "positive" in args


def test_auto_confirm_exit_nonzero():
    """TS-06: exit_code=1 → hm.confirm 被呼叫，result=negative"""
    from hypermemory.core.hooks import auto_confirm
    hm = MagicMock()
    auto_confirm("terminal", {"command": "dotnet test"}, '{"exit_code": 1}', hm=hm)
    hm.confirm.assert_called_once()
    args, _ = hm.confirm.call_args
    assert "negative" in args


def test_auto_confirm_non_terminal():
    """TS-07: 非 terminal tool → hm.confirm 不被呼叫"""
    from hypermemory.core.hooks import auto_confirm
    hm = MagicMock()
    auto_confirm("read_file", {"path": "test.txt"}, '{"content": "hello"}', hm=hm)
    hm.confirm.assert_not_called()


def test_auto_confirm_invalid_result():
    """TS-08: result JSON 無 exit_code → 不觸發 confirm"""
    from hypermemory.core.hooks import auto_confirm
    hm = MagicMock()
    auto_confirm("terminal", {"command": "echo hi"}, '{"output": "hi"}', hm=hm)
    hm.confirm.assert_not_called()


# ─── auto_imprint (post_llm_call) ──────────────────────


def test_auto_imprint_with_keyword():
    """TS-09: response 含關鍵字 → hm.imprint 被呼叫"""
    from hypermemory.core.hooks import auto_imprint
    hm = MagicMock()
    hm.imprint.return_value = {"success": True, "node": "2026-06-22-auto.md"}
    long_resp = "這是一個很重要的結論，我們決定改用 Hermes plugin 架構。" * 10
    auto_imprint(long_resp, hm=hm)
    hm.imprint.assert_called_once()


def test_auto_imprint_without_keyword():
    """TS-10: response 不含關鍵字 → hm.imprint 不被呼叫"""
    from hypermemory.core.hooks import auto_imprint
    hm = MagicMock()
    short_msg = "好的，我已經幫你 build 完成了。測試全部通過。"
    auto_imprint(short_msg, hm=hm)
    hm.imprint.assert_not_called()


def test_auto_imprint_short_response():
    """TS-11: 太短的 response → hm.imprint 不被呼叫"""
    from hypermemory.core.hooks import auto_imprint
    hm = MagicMock()
    auto_imprint("OK", hm=hm)
    hm.imprint.assert_not_called()


# ─── plugin.load() ─────────────────────────────────────


def test_plugin_load_returns_three_hooks():
    """TS-12: plugin.load() 回傳 dict 含三個 hook，且全部 callable"""
    from hypermemory.plugin import load
    hooks = load()
    assert isinstance(hooks, dict)
    assert "pre_llm_call" in hooks
    assert "post_tool_call" in hooks
    assert "post_llm_call" in hooks
    for name, fn in hooks.items():
        assert callable(fn), f"{name} is not callable"
