"""HyperMemory Hermes Plugin Entry Point

Plugin 不修改 Hermes 核心程式碼，僅透過 hook 介面與 Hermes 互動。

安裝方式：
  pip install hypermemory
  hermes plugins enable hm-loop

或透過 entry_points 自動發現（pyproject.toml 已設定）。
"""


def load():
    """載入三個 hook function。

    Returns:
        dict: {"pre_llm_call": fn, "post_tool_call": fn, "post_llm_call": fn}
    """
    from hypermemory.core.hooks import inject_recall, auto_confirm, auto_imprint

    return {
        "pre_llm_call": inject_recall,
        "post_tool_call": auto_confirm,
        "post_llm_call": auto_imprint,
    }


def register(ctx):
    """Hermes plugin entry point — entry_points 直接呼叫此函式。

    Hermes 安裝 HM 後，透過 pyproject.toml 中的 entry_points 發現此函式，
    自動執行註冊三個 hook。

    Args:
        ctx: Hermes PluginContext，由 Hermes framework 傳入。
    """
    for name, fn in load().items():
        ctx.register_hook(name, fn)
