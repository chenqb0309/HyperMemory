# HyperMemory：設計約束（Design Constraints）

| 版本**: 2.0
| 建立日期**: 2026-06-17 (v2: 2026-06-22)
**定位**: 本文件定義 HyperMemory 不可協調的設計原則。所有 spec、實作、測試若與以下約束衝突，應以本文件為準。

---

## 約束 1：Hermes 原生，MCP 相容

HyperMemory 的主要使用者是 Hermes agent，但透過 MCP 提供跨 agent 相容性。

| 面向 | 內容 |
|------|------|
| Why | agent 內建記憶（Memory.md）收容空間過小，無法承載長期經驗累積；閉環強制力需要 framework-level hook，HM 選擇在不犧牲正確性的前提下優先服務 Hermes |
| What | 核心：直接 import `hypermemory.core` 作為 Hermes 的 plugin + hook，取得 pre_llm_call / post_tool_call / post_llm_call 三處強制閉環；附加：MCP server + CLI 保留，供外部 agent 或手動操作使用 |
| 不做的 | 不為了保持 agent-agnostic 而放棄閉環強制力；不強求「任何 agent 都能達到同等體驗」；MCP 相容僅為附加功能，不主導開發決策 |
| 驗收 | Hermes plugin 裝載後：每輪自動 recall、terminal 結束自動 confirm、對話結束自動 imprint。MCP 仍可被任何支援 MCP 的 client 存取（但體驗不保證閉環） |

---

## 約束 2：記憶按主體形成鏈狀結構，經驗累積有複利

同一主題的經驗不應是散落的獨立節點，而是一條隨時間生長的鏈。

| 面向 | 內容 |
|------|------|
| Why | 線性經驗累積：每個新教訓基於舊教訓，鏈越長代表該主題越成熟 |
| What | Node 以 prenode → nextnodes 構成單向鏈，Type 1/2/3 支援推移與跨鏈聚合 |
| 不做的 | 不設計為純標籤分類系統（tag-only 無法表達經驗演化次序） |
| 驗收 | 同主題的經驗可追溯整條鏈；鏈越長、recall 優先級越高 |

---

## 約束 3：事實糾偏循環

經驗必須經過事實驗證才能提高可靠度，不可由 AI 主觀決定。

| 面向 | 內容 |
|------|------|
| Why | AI 刻錄時給的 intensity 是靜態的，只有真實執行結果（build pass/fail、test pass/fail、HTTP 200/500）才能糾偏 |
| What | 循環：recall → 實作 → confirmation event（positive/negative）→ maturation 更新 |
| 不做的 | 不允許無事實依據的權重調整，不允許 agent 自評 maturation |
| 驗收 | 每次事實驗證後 maturation 正確反映；multiple negative events 可讓經驗降級或淘汰 |

---

## 約束 4：場景參數影響經驗適用性

同一經驗在不同場景（OS、技術棧、環境）下成功率不同，系統必須感知這個差異。

| 面向 | 內容 |
|------|------|
| Why | Windows 上 debug MCP 的經驗，在 Linux 上不一定有效。不區分場景的 recall 會誤導 agent |
| What | 5M1E 維度系統（機料法環人量）標記每個經驗的適用場景；recall 時維度衝突的 node 直接排除 |
| 不做的 | 維度衝突不扣分、不懲罰，只是過濾。不做 embedding 語義場景比對 |
| 驗收 | 查詢帶 context_dims 時，維度衝突的 node 不會出現在 recall 結果中 |

---

## 約束 5：人腦記憶模型 — 用進廢退，長期有效經驗形成肌肉記憶

記憶系統應模擬人腦的遺忘曲線與技能自動化機制。

| 面向 | 內容 |
|------|------|
| Why | 近期活躍的經驗比久遠無 recall 的經驗更重要；反覆驗證有效的經驗應固化為可重複使用的 skill |
| What | 半衰期模型（經驗30d/骨骼90d/自動刻錄7d）；固化基底 solidification 永不歸零；weight+maturation 達門檻 → skill_ready |
| 不做的 | 不刪除舊 node（保留追溯能力），不讓 weight 歸零 |
| 驗收 | 高 intensity 的舊 node 即使衰減仍有基本 recall 機會；weight+maturation 達標的經驗可標記 skill_ready |

---

## 約束 6：可信任的經驗依據

最終目的是讓 agent 將 HyperMemory 作為每次處理事情的依據來源，提高人類對 AI 實作的信任度。

| 面向 | 內容 |
|------|------|
| Why | 沒有記憶的 agent 每次從零開始，人類無法信任其決策一致性 |
| What | Plugin hook（pre_llm_call）強制每輪自動 recall；maturation 提供事實驗證的可靠度指標；post_tool_call 自動 confirm 形成閉環。MCP 保留供外部 agent 存取（但無閉環保證） |
| 不做的 | 不提供「AI 自信度」取代事實驗證，不偽造經驗 |
| 驗收 | agent 接入 HM 後，相同問題可回傳一致的、有經驗依據的回答；人類可檢視經驗鏈與 confirmation 紀錄 |

---

## 約束 7：經驗記憶不是事實

HyperMemory 儲存的是經驗記錄，不是當前事實。consuming AI 必須能夠明確區分，在任何存取路徑下都不應混淆。

| 面向 | 內容 |
|------|------|
| Why | HM 的節點來自過往對話與實作經驗，可能過時、錯誤或 context 不適用。任何 agent 將記憶當作當前事實使用，都可能產出錯誤結果 |
| What | 每個 node 檔案以 `^HM_MEMORY_START` 和 `^HM_MEMORY_END` 成對 marker 包覆，start 行附 disclaimer 文字。所有寫入路徑（imprint、reflect、daemon）自動附加 marker。所有讀取路徑（parse_frontmatter）自動跳過 marker。recall/think 輸出時不強制剝離 marker — consuming AI 在 context 中直接看到 disclaimer |
| 不做的 | marker 不參與任何邏輯運算（權重、maturation、filter 都不依賴它）。不強制 recall/think 回傳時額外加 disclaimer（檔案本身的 marker 已足夠，且 parse_frontmatter 不受干擾） |
| 驗收 | 每個 node 檔案的第一行是 `^HM_MEMORY_START`；最後一行是 `^HM_MEMORY_END`；parse_frontmatter 正確解析包覆後的內容；新建立的 node 自動含 marker；35 個既有 node 批次補全；三條寫入路徑（CLI imprint、MCP imprint、reflect）全部強制 |
