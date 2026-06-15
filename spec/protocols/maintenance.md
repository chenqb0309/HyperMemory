# HyperMemory：維護循環

## Recalc（權重重算）

**頻率**：每日一次。

### 流程

1. 讀取 index.md 取得所有 cluster 條目
2. 對每條 cluster：
   a. 讀取當前指向的 node
   b. 沿 prenode 回溯至頂端，收集鏈上所有 node
   c. 用權重公式計算每個 node 的分數
   d. 找出鏈上最高權重 node
   e. 若與當前 index 指標不同，更新之

### 邊界

- node 檔案不存在於硬碟 → 從 index 移除
- prenode 指向的 node 已遺失 → 降級為 Type 1

## DreamLoop（關鍵字收斂）

**頻率**：每週一次。

### Scan 1：關鍵字去重合併

針對同一 cluster 內部的關鍵字，找出語義高度接近的詞彙對進行合併。

### Scan 2：跨 cluster 重疊檢查

計算不同 cluster 之間的關鍵字重疊比例。若 overlap > 50%，標記為「可能需合併」。

```
overlap = |cluster_A ∩ cluster_B| / min(|A|, |B|)
```

### Scan 3：孤立關鍵字清理

檢查每個關鍵字：其所指向的 node 是否仍存在於硬碟上。若檔案已遺失，從 cluster 中移除對應關鍵字。

## Reflection Loop（反思刻錄）

**頻率**：每日一次，在每日結束前執行。

### 流程

1. 收集當日對話 session 清單（排除 routine 執行）
2. 對比既有記憶 node，判斷哪些 session 尚未被涵蓋
3. 對每個新內容執行完整 imprint 協定

### 判斷規則

| 狀態 | 條件 | 動作 |
|------|------|------|
| Already imprinted | 結論已被既有 node 涵蓋 | 跳過 |
| Needs imprint | 包含新結論、決策、教訓 | 執行 imprint |
| No actionable content | 純執行對話、無新結論 | 跳過 |

## 圖示

```
時間軸
  │
  ├─ 03:00  Recalc
  │       權重重算，更新 index
  │
  ├─ 04:00（週日） DreamLoop
  │       關鍵字收斂，cluster 合併
  │
  └─ 23:00  Reflection Loop
          新 session 反思刻錄
```
