# HyperMemory Loop Plugin — 設計規格

**定位**: 將 HM 從「agent 自願使用的記憶工具」升級為「Hermes agent 的強制閉環經驗系統」
**前置依賴**: HM core (`hypermemory.core.hm_tools`) 已實作完成
**版本**: v1 (draft)
**日期**: 2026-06-22

---

## 為什麼需要這個 plugin

現狀：HM 提供 MCP tools（recall/think/imprint/confirm），但 agent 必須自願呼叫。實證顯示 agent 經常忘記或不認為需要 recall，導致記憶池淪為靜態知識庫。

解法：利用 Hermes 的 plugin hook 系統，在 framework 層強制執行 recall/confirm/imprint，agent 無從繞過、無需自覺。

---

## 架構位置

```
Hermes agent session
  │
  ├─ pre_llm_call  ──▶ HM Loop Plugin ──▶ hm_tools.think()  ──▶ 每輪自動 recall
  │                       │
  ├─ post_tool_call ──────┤──────────────▶ hm_tools.confirm() ──▶ terminal 自動回報
  │                       │
  ├─ post_llm_call ───────┤──────────────▶ hm_tools.imprint() ──▶ 對話自動刻錄
  │                       │
  └─ agent 正常運作        │
                           └── 使用 hypermemory.core.HMTools（直接 import，不走 MCP）
```

---

## Plugin 檔案結構

```
~/.hermes/plugins/hm-loop/
├── __init__.py          ← 唯一必要檔案
└── README.md            ← 安裝說明（可選）
```

不需要 `pyproject.toml`。Hermes plugin 只要有 `__init__.py` + `register()` function 就自動載入。

---

## 實作

### 完整程式碼 (`__init__.py`)

```python
"""HM Loop Plugin — Hermes-native 記憶強制閉環

每輪 user message → pre_llm_call 自動 recall
每輪 terminal → post_tool_call 自動 confirm
每輪回答完成 → post_llm_call 自動 imprint

安裝：將此目錄放至 ~/.hermes/plugins/hm-loop/，重啟 Hermes。
"""

import json
import logging
from hypermemory.core.hm_tools import HMTools

logger = logging.getLogger("hm-loop")
hm = HMTools()  # 指向預設 pool (~/.hypermemory/pools/default/)

# ── 1. pre_llm_call — 每輪強制 recall ─────────────────────

def inject_recall(user_message, is_first_turn, **kwargs):
    """在 agent 看到 user message 之前，把 HM recall 結果注入 context。"""
    if not user_message or len(user_message.strip()) < 3:
        return None

    try:
        result = hm.think(user_message, dry_run=True)
        if not result.get("found"):
            return None

        best = result.get("result", {})
        summary = best.get("summary", "") or best.get("title", "")
        weight = best.get("weight", 0)
        maturation = best.get("maturation", 0)

        context = (
            "[HM Memory Recall]\n"
            f"Match: {best.get('title', '')}\n"
            f"Weight: {weight} | Maturation: {maturation}\n"
            f"Summary: {summary}\n"
            "---\n"
        )
        return {"context": context}
    except Exception as e:
        logger.warning("hm recall failed: %s", e)
        return None

# ── 2. post_tool_call — terminal 執行完自動 confirm ───────

def auto_confirm(tool_name, args, result, duration_ms, **kwargs):
    """terminal 指令完成後，根據 exit_code 自動回報 confirm。"""
    if tool_name != "terminal":
        return

    try:
        parsed = json.loads(result)
        exit_code = parsed.get("exit_code")
        if exit_code is None:
            return
    except Exception:
        return

    source_node = f"terminal-{args.get('command', '')[:60]}"
    outcome = "positive" if exit_code == 0 else "negative"
    agent = "hermes"

    try:
        hm.confirm(source_node, outcome, agent=agent,
                   context_summary=f"exit_code={exit_code}")
        logger.info("hm confirm: %s → %s", source_node[:40], outcome)
    except Exception as e:
        logger.warning("hm confirm failed: %s", e)

# ── 3. post_llm_call — 對話結束自動 imprint ────────────────

def auto_imprint(assistant_response, user_message, **kwargs):
    """每輪結束，偵測是否有值得記錄的經驗，自動刻錄。"""
    if not assistant_response or len(assistant_response) < 100:
        return

    # 偵測關鍵字觸發
    trigger_keywords = [
        "結論", "決定", "決策", "修復", "錯誤", "失敗", "原因",
        "root cause", "架構", "收穫", "教訓", "學到", "問題",
    ]
    if not any(kw in assistant_response for kw in trigger_keywords):
        return

    # 建立節點內容
    import datetime
    ts = datetime.datetime.now().isoformat()

    content = (
        "---\n"
        "type: episodic_memory\n"
        f"timestamp: {ts}\n"
        "node_type: 1\n"
        f"intensity: 3\n"
        "total_mentions: 0\n"
        "---\n"
        "# 自動刻錄\n\n"
        "## 正文\n"
        f"{assistant_response[:800]}"
    )

    try:
        result = hm.imprint(content)
        if result.get("success"):
            logger.info("hm imprinted: %s", result.get("node", ""))
    except Exception as e:
        logger.warning("hm imprint failed: %s", e)

# ── 4. Register — 掛上 Hermes hook ─────────────────────────

def register(ctx):
    ctx.register_hook("pre_llm_call", inject_recall)
    ctx.register_hook("post_tool_call", auto_confirm)
    ctx.register_hook("post_llm_call", auto_imprint)
    logger.info("HM loop plugin registered (3 hooks)")
```

---

## Hook 觸發時機（Hermes 官方行為）

| Hook | 時機 | 頻率 | 參數 |
|------|------|------|------|
| `pre_llm_call` | 每輪 agent 開始推理「之前」 | 每 user turn 一次 | `user_message`, `is_first_turn`, `platform` |
| `post_tool_call` | 每個 tool 執行完「之後」 | 每個 tool call 一次 | `tool_name`, `args`, `result`, `duration_ms` |
| `post_llm_call` | agent 回答完「之後」 | 每 user turn 一次 | `assistant_response`, `user_message` |

**重要**: `pre_llm_call` 回傳 `{"context": str}` 時，框架會將該字串附加到**當前的 user message** 中。agent 無法選擇不看 — context 直接出現在 LLM 的輸入中。

---

## 行為說明

### 1. recall（自動注入）

- 每輪 user message 送達後，先自動 `hm.think(user_message)`
- 有命中 → 格式化後注入 context（agent 輸入中先看到 HM 經驗，才看到 user 問題）
- 無命中 → 不注入，agent 正常處理
- `dry_run=True` 表示不計入 total_mentions（避免無意義的 mention 通膨）
- 首次 turn（`is_first_turn=True`）可考慮加權或跳過（新 session 不一定有相關經驗）

### 2. confirm（自動回報）

- 只攔截 `tool_name == "terminal"` 
- 其他 tool（read_file、web_search 等）不觸發 confirm
- exit_code=0 → positive；非 0 → negative
- source_node 使用指令摘要（便於在 pool 中辨識來源）
- 執行後 maturation 自動更新

### 3. imprint（自動刻錄）

- 只處理 `len(assistant_response) >= 100` 的回答（太短沒刻錄價值）
- 偵測回答中是否含觸發關鍵字（結論、決策、修正、root cause 等）
- 符合條件 → 建立 node_type=1（自動刻錄，半衰期 7 天，快速衰退）
- intensity=3（保守，避免不重要經驗佔據高權重）
- 可擴展：未來可透過 `hm_confirm` 的正反饋提升已自動刻錄節點的 intensity

---

## 安裝方式

```bash
# 1. 建立 plugin 目錄
mkdir -p ~/.hermes/plugins/hm-loop

# 2. 寫入 __init__.py（內容如上）

# 3. 重啟 Hermes
hermes gateway restart   # gateway 模式
# 或
hermes /reset           # CLI 模式（新 session）
```

驗證安裝：
```bash
# 看 log 中是否有註冊訊息
grep "HM loop plugin" ~/.hermes/logs/gateway.log
```

---

## 風險與邊界

| 風險 | 影響 | 處理 |
|------|------|------|
| pre_llm_call 失敗不阻斷 agent | 低 — hook 異常已被框架 catch，agent 正常運作 | 僅 log warning，不回傳 context |
| post_tool_call 誤判 exit_code（如 timeout = 非 0 但不一定是負面經驗） | 中 — 可能產生 false negative confirm | 初始只抓 exit_code=0 vs !=0，後續可細分（如 timeout 不觸發 confirm） |
| auto_imprint 刻錄太多低價值 node | 中 — node_type=1（半衰期 7 天），7 天後 weight < 1，自然衰退 | 關鍵字門檻 + 回答長度門檻雙重過濾 |
| HM pool 路徑硬編碼 | 低 — HMTools() 使用預設路徑，可傳 pool_path 覆蓋 | 後續可改從 plugin config 讀取 |
| dry_run=true 不計 mentions | recall 效率無法反映在 weight 中 | 此為謹慎設計，可根據實際效果決定是否改為非 dry_run |

---

## 與既有路徑的關係

```
hypermemory/
├── core/
│   ├── hm_tools.py     ← Plugin 直接 import 使用
│   ├── weight.py       ← 不動
│   ├── cluster.py       ← 不動
│   └── ...
├── mcp_server.py       ← 保留（供外部 agent）
├── __main__.py          ← 保留（CLI debug）
└── commands/            ← 保留（CLI）

~/.hermes/
├── config.yaml          ← mcp_servers.hypermemory 可保留（供外部 agent）或移除
└── plugins/hm-loop/     ← 主要路徑
    └── __init__.py
```

---

## 驗收條件

- [ ] Plugin 安裝後，`hermes gateway restart` log 出現 `HM loop plugin registered (3 hooks)`
- [ ] 每輪 user message 後，log 出現 `hm recall:` 或 `hm recall failed:`（無命中時不 log）
- [ ] 每輪 terminal 執行後，log 出現 `hm confirm: ... → positive/negative`
- [ ] 每輪回答含結論關鍵字後，log 出現 `hm imprinted: YYYY-MM-DD-自動刻錄-xxx.md`
- [ ] pool 中出現新的自動刻錄 node（node_type=1）
- [ ] MCP server 仍可正常被外部 client 存取（不影響）
- [ ] CLI `hm list` 仍正常列出 cluster（不影響）

---

## 不做的範圍

- 不開發非 Hermes 的 bridge（Claude Code hook、Codex adapter 等）
- 不修改 HM core 來配合 plugin（plugin 只消費既有 API）
- 不處理非 terminal 工具（read_file、web_search 等）的 confirm
- 不做 session 層級的 imprint 去重（同一 session 可能多次刻錄類似內容）
