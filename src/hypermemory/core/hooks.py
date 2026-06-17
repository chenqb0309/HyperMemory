"""HyperMemory Hooks — Hermes plugin 的強制閉環核心。

提供三個 hook function，分別對應 LLM call 的三個生命週期點：
- pre_llm_call:   LLM 回答前，自動 recall 相關經驗
- post_tool_call: 工具執行後，自動 confirm（positive/negative 根據 exit code）
- post_llm_call:  LLM 回答後，自動 imprint 新經驗

測試方式：三個 function 接受可選的 hm 參數（DI），
test 可傳入 MagicMock 代替真實 HMTools。
"""

import json
import logging

logger = logging.getLogger("hm-hooks")

# 觸發 auto_imprint 的關鍵字集合
IMPRINT_TRIGGER_KEYWORDS = {
    "結論", "決定", "決策", "修復", "錯誤", "失敗", "原因",
    "root cause", "架構", "收穫", "教訓", "學到", "問題",
    "修正", "改用", "改為", "總結",
}

# auto_imprint 最短 response 長度
MIN_IMPRINT_LENGTH = 100


def _format_recall_context(result: dict) -> str:
    """將 hm.think() 的 result dict 格式化為 context 字串。"""
    title = result.get("title", "")
    weight = result.get("weight", 0)
    summary = result.get("summary", "") or title
    return (
        "[HM Memory]\n"
        f"Title: {title}\n"
        f"Weight: {weight}\n"
        f"Summary: {summary}\n"
        "---"
    )


def inject_recall(user_message, hm=None, **kwargs):
    """pre_llm_call: LLM 回答前，自動 recall 相關經驗。

    Hermes hook 簽名：
        (session_id, user_message, conversation_history,
         is_first_turn, model, platform, **kwargs)

    回傳 {"context": str} 以注入 context，或 None 不注入。

    測試可透過 hm=Mock() 注入 mock。
    """
    # 極短 query 跳過，避免無謂查詢
    if not user_message or len(user_message.strip()) < 5:
        return None

    tools = hm
    if tools is None:
        from hypermemory.core.hm_tools import HMTools
        tools = HMTools()

    try:
        result = tools.think(user_message, dry_run=True)
        if not result.get("found"):
            return None
        return {"context": _format_recall_context(result["result"])}
    except Exception as e:
        logger.warning("inject_recall failed: %s", e)
        return None


def auto_confirm(tool_name, args, result, hm=None, **kwargs):
    """post_tool_call: terminal 執行完，自動 confirm。

    Hermes hook 簽名：
        (tool_name, args, result, task_id, duration_ms, **kwargs)

    只處理 tool_name == "terminal"，exit_code 決定 positive/negative。
    """
    if tool_name != "terminal":
        return

    # 解析 exit_code
    try:
        parsed = json.loads(result) if isinstance(result, str) else result
        exit_code = parsed.get("exit_code")
        if exit_code is None:
            return
    except (json.JSONDecodeError, TypeError, AttributeError):
        return

    tools = hm
    if tools is None:
        from hypermemory.core.hm_tools import HMTools
        tools = HMTools()

    cmd = args.get("command", "") if isinstance(args, dict) else str(args)
    source_node = f"terminal:{cmd[:60]}"
    outcome = "positive" if exit_code == 0 else "negative"

    try:
        tools.confirm(
            source_node,
            outcome,
            agent="hermes",
            context_summary=f"exit_code={exit_code}",
        )
        logger.info("auto_confirm: %s → %s", source_node[:40], outcome)
    except Exception as e:
        logger.warning("auto_confirm failed: %s", e)


def auto_imprint(assistant_response, **kwargs):
    """post_llm_call: LLM 回答後，自動 imprint 新經驗。

    Hermes hook 簽名：
        (session_id, user_message, assistant_response,
         conversation_history, model, platform, **kwargs)

    只處理含 IMPRINT_TRIGGER_KEYWORDS 且長度足夠的回應。
    測試可傳入 hm=Mock() 注入 mock。
    """
    if not assistant_response or len(assistant_response) < MIN_IMPRINT_LENGTH:
        return

    if not any(kw in assistant_response for kw in IMPRINT_TRIGGER_KEYWORDS):
        return

    # 支援 DI：測試可傳 hm=Mock()，否則自動載入 HMTools
    tools = kwargs.get("hm")
    if tools is None:
        from hypermemory.core.hm_tools import HMTools
        tools = HMTools()

    import datetime
    ts = datetime.datetime.now().isoformat()

    # 摘要取前 500 字當 body
    body = assistant_response.strip()[:500]
    title = assistant_response.strip().split("\n")[0][:60]

    content = (
        "---\n"
        "type: episodic_memory\n"
        f"timestamp: {ts}\n"
        "node_type: 1\n"
        "intensity: 3\n"
        "total_mentions: 0\n"
        "---\n"
        f"# {title}\n\n"
        "## 正文\n"
        f"{body}"
    )

    try:
        result = tools.imprint(content)
        if result.get("success"):
            logger.info("auto_imprint: %s", result.get("node", ""))
    except Exception as e:
        logger.warning("auto_imprint failed: %s", e)
