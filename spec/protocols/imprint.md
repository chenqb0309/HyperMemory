# HyperMemory：刻錄協定（Imprint Protocol） [done]

## 用途

將新經驗寫入記憶池，包含 node 生成、cluster 索引維護、鏈結關係建立。

## 觸發條件

1. 複雜除錯結束：成功解決一個需要多步驟排查的問題
2. 重要決策產生：做出架構選擇、技術選型、或影響後續開發的決定
3. 使用者明顯挫折或成功：強烈情緒反應（不論正面或負面）
4. 明確要求：使用者說「把這個記下來」「記錄一下」

## 執行步驟

### Step 1：判斷引子類型

| Type | 條件 | prenode |
|------|------|---------|
| Type 1：全新 | 無前例可參考的全新經驗或知識 | null |
| Type 2：推移進化 | 基於某個過往經驗的深化 | 指向該經驗 node |
| Type 3：集合進化 | 從多個不同領域的經驗匯聚而來 | 指向主鏈基底 node + ref_by |

### Step 2：設定 intensity

根據當下的衝擊強度打分（1-10）：

- 9-10：災難性失敗或重大突破
- 6-8：明顯的成功或失敗
- 3-5：一般經驗
- 1-2：平淡進度

### Step 3：生成關鍵字群

從對話中提取核心關鍵字和語義近似詞：

- 核心關鍵字：經驗的核心主題詞
- 語義近似詞：同義詞、相關詞，供未來 cluster 匹配使用
- 至少 2-3 個關鍵字，最多不限

### Step 4：生成 Frontmatter

依照 `node-schema.md` 的規範生成 frontmatter。

### Step 5：判斷基底歸屬（Type 3 限定）

```
新結論是否仍包含基底核心？
  ├─ 是 → prenode = 基底 node，屬於原鏈
  └─ 否 → 話題已偏移，發起問答確認歸屬
```

若偏移不明確，問使用者，不猜測。

### Step 5b：跨 cluster 關聯掃描

在寫入之前，掃描 index 中所有 cluster 的當前 node，判斷是否有：

- 語義重疊 → 兩個 node 在講類似概念
- 互補關係 → 一個 node 的前提是另一個的結論
- 相反結論 → 矛盾應被標記

若發現關聯，補進新 node 的 `ref_by`。只掃 index 指向的當前 node（每 cluster 一個），不掃整條鏈。

### Step 6：寫入記憶 Node

寫入完整檔案（frontmatter + body link + 正文）至記憶池：

```
<memory-pool>/<agent-name>/YYYY-MM-DD-description.md
```

### Step 7：讀取當前 index.md

### Step 8：判斷 cluster 歸屬

- 有 prenode（Type 2/3）→ 找到 prenode 所在的 cluster 條目
- 無 prenode（Type 1）→ 準備建立新 cluster

### Step 9：更新 index.md

**情況 A：cluster 已存在**
1. 擴增該 cluster 的關鍵字群
2. 若新 node 權重更高，更新 node 指標

**情況 B：cluster 不存在**
1. 新增《cluster → [[新 node]]》

**情況 C：Type 3 且 prenode 與 ref_by 涉及不同 cluster**
1. prenode 決定主 cluster
2. ref_by 記錄在 node 內文，不影響 index

### Step 9b：維護 prenode 的 nextnodes（雙向鏈結）

Type 2/3 寫入時，在 prenode 的 frontmatter 中加上此 node 的 nextnodes 條目。

**重要**：解析既有 nextnodes 時必須完整重建（list + 新增），不可逐行 append，否則產生重複 entries。

### Step 10：權重計算

```
weight = engagement × recency + solidification

engagement = intensity × (1 + 0.1 × total_mentions) + ref_by_boost + chain_boost
recency = node_type-aware 半衰期模型（經驗30d / 骨骼90d / 自動刻錄7d）
solidification = intensity × 0.05（永不衰減基底）
```

## 常見失誤

- 跳過載入協定直接執行
- Type 2 開了新 cluster 而非擴增既有
- prenode 誤寫為 list 而非 scalar
- YAML parser 將 `[[link.md]]` 解析為巢狀 list
- timestamp 缺少時區資訊
