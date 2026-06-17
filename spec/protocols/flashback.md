# HyperMemory：回憶協定（Flashback Protocol） [done] — 回憶步驟全部實作

## 用途

根據關鍵字從記憶池中檢索過往經驗，支援 cluster 匹配與鏈追溯。

## 觸發條件

1. 語義暗示：使用者的語句中包含「以前/之前/記得/上次/不是有過/回想一下」等喚醒記憶的詞彙
2. 任務關鍵詞提取：當前討論涉及技術名、專案名、錯誤訊息等可能與過往經驗相關的內容
3. 明確要求：使用者直接說「回想一下上次的...」或「幫我找找之前...」

## 執行步驟

### Step 1：提取關鍵詞

從使用者語句中提取核心關鍵詞。若使用者說的詞彙過於廣泛（如「那個問題」），發起問答確認。

### Step 2：讀取記憶池路徑

從內建記憶中讀取 `memory-pool:` 行，取得 index.md 的絕對路徑。若找不到，回報「HyperMemory 記憶池未設定」。

### Step 3：讀取索引

讀取 index.md 內容，取得所有《cluster → node》映射。

### Step 4：Cluster 比對

- 比對原則：cluster 中有多少關鍵字命中，而非完全匹配
- 命中閾值：至少 1 個關鍵字匹配即視為潛在命中
- 若多條 cluster 同時命中，取命中關鍵字比例最高者
- 若無任何 cluster 命中，執行語義近似掃描（讀取所有 cluster 的關鍵字列表，用 LLM 判斷是否有近似概念）[design] — HM 不做 embedding，語義近似由 agent 自行判斷

### Step 5：讀取記憶 Node

命中 cluster 後，讀取其指向的 node 檔案內容。

⚠️ node 檔案包含 memory marker（`^HM_MEMORY_START` / `^HM_MEMORY_END` 及 disclaimer 行）。
`parse_frontmatter()` 會自動跳過這些行，不影響解析結果。
disclaimer 在 context 中提醒 consuming AI「這是記憶，不是事實」。

### Step 6：更新 total_mentions

在該 node 的 frontmatter 中，將 `total_mentions` 加 1。

若權重改變導致該 node 不再是鏈上最高，更新 index.md 中該條 cluster 的 node 指標。

### Step 7：回傳結果

將記憶 node 的內容整合進回應中。若需更多脈絡，自動啟動走訪模式。

## 走訪模式

### 自動走訪

當以下情況發生時，自動從 anchor node 開始走訪：
- 使用者問「後來呢？」「那之前呢？」等追問
- 當前的記憶需要更多脈絡才能完整回答
- 明確說「往前追溯」或「看看分支」

### prenode 回溯

從 anchor node 開始，沿 prenode 向上回溯（最多 5 層）。回溯時不比較權重，嚴格逐層走。

### nextnodes 探索

從當前 node 查看 nextnodes 列表，依權重決定探索順序。權重高者優先。

### 完整回憶模式

當使用者說「回想一下」— 讀取 anchor node，沿 prenode 回溯至頂端，從頂端依序走訪所有 nextnodes 分支，返回整條鏈的摘要。
