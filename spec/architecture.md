# HyperMemory：核心架構

## 什麼是 HyperMemory

HyperMemory 是一套 AI 記憶系統，模擬人類的：

- **反射式 recall**：關鍵字觸發時，記憶自然浮現
- **遺忘曲線**：近期記憶清晰度高於久遠記憶
- **印痕效應**：高衝擊事件對時間衰減有更高的抗性
- **反芻強化**：反覆提取的記憶會越來越牢固

它不是知識庫。知識庫儲存「事實」，HyperMemory 儲存「經驗」。這兩者的差異決定了整個架構的設計。

## 三層認知流

```
使用者輸入
      │
      ▼
【1. Flashback】── 回憶觸發
      │         語義暗示或關鍵詞提取
      │         查 index → cluster 匹配 → 讀取 node
      ▼
【2. Amplifier】── 思考放大
      │         比對過去與現在，找出模式重疊與盲點
      │         詳見 protocols/amplifier.md
      ▼
【3. Imprint】── 印痕刻錄
                將新經驗寫入記憶池 + 更新索引
```

三層不一定每次都完整執行。使用者的問題可能只觸發 Flashback，不需要 Imprint。但每次 Imprint 之前都應該先經過 Flashback 確認記憶是否已存在。

## 記憶池分離

每個 agent 擁有獨立的記憶池：

```
<memory-store-root>/
├── memory-pools/
│   ├── <agent-name>/
│   │   ├── index.md          ← cluster → node 索引
│   │   ├── YYYY-MM-DD-*.md   ← 記憶 node
│   │   └── ...
│   └── ...
└── consensus/                 ← 選擇性：跨 agent 共識池
    ├── decisions/
    ├── specs/
    └── shared-context/
```

### index.md

```
《cluster: [關鍵字1, 關鍵字2, ...]》 → [[node-檔名.md]]
《cluster: [關鍵字A, 關鍵字B, ...]》 → [[node-檔名.md]]
```

- 每條索引只指向一個 node（該鏈上當前權重最高者）
- 不同條目之間沒有權重比較問題，純靠 cluster 相符度決定哪條被命中

### 記憶 Node

每個 node 是一個 markdown 檔案，包含 frontmatter + body：

```yaml
---
type: episodic_memory
timestamp: 2026-06-11T14:30:00+08:00
node_type: 1                 # 1=new, 2=evolution, 3=cross-chain
prenode: null                 # scalar，單一父節點
nextnodes: null               # list，多個子分支
ref_by: null                  # list，Type 3 的參考來源
intensity: 7                  # 1-10
total_mentions: 1             # 被成功 recall 的次數
tags: [hypermemory, imprint]  # 選擇性標籤
---
```

### Node 類型

| Type | 意義 | prenode | ref_by |
|------|------|---------|--------|
| 1 | 全新經驗 | null | null |
| 2 | 從既有經驗推移進化 | [[舊node]] | null |
| 3 | 跨鏈集合進化 | [[主鏈node]] | [[A]], [[B]] |

### 權重公式

```
node_score = intensity × (1 + 0.1 × total_mentions) × decay(timestamp)
```

- **intensity**：1-10，寫入時設定的衝擊強度
- **total_mentions**：每次成功 recall +1
- **decay**：時間衰減函數，高 intensity node 有更高抗性

## 三條認知協議

1. **以記憶為底座的思考**：回答前先自問「我過去遇過類似的事嗎？」
2. **跨時間模式識別**：當使用者遭遇挫折時，主動比對過往類似失敗
3. **刻錄強迫症**：重要對話產生結論時，有義務寫入記憶池

## 服務邊界

HyperMemory CLI（`hm`）是 agent 與記憶池之間的服務邊界：

```
Agent（任何平台）
  │  hm recall / hm imprint / hm list
  ▼
HyperMemory CLI
  │  強制執行 cluster 匹配、frontmatter 格式、權重更新
  ▼
記憶池（markdown 檔案）
```

CLI 的存在解決了一個架構問題：當 agent 可以直接讀寫檔案時，記憶協定是建議性的。CLI 作為強制閘道，確保所有操作遵守規格。

## 維護循環

| 循環 | 頻率 | 職責 |
|------|------|------|
| Recalc | 每日 | 重算權重，更新 index node 指標 |
| DreamLoop | 每週 | 關鍵字去重、cluster 合併 |
| Reflection Loop | 每日 | 掃描新 session，反思刻錄 |
