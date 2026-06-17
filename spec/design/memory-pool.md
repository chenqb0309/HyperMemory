# HyperMemory：記憶池規格

## 目錄結構

```
<memory-store-root>/
├── memory-pools/
│   ├── <agent-name>/
│   │   ├── index.md              ← cluster → node 索引
│   │   ├── YYYY-MM-DD-*.md       ← 記憶 node
│   │   └── ...
│   ├── <another-agent>/
│   └── ...
└── consensus/                     ← 選擇性：跨 agent 共識池
```

## index.md 規範

### 格式

每條索引為一個《cluster → node》映射：

```
《cluster: [關鍵字1, 關鍵字2, ...]》 → [[YYYY-MM-DD-node-file.md]]
```

### 規則

- 每條索引只指向一個 node，不是列表
- node 是該記憶鏈上當前權重最高的那一個
- 不同條目之間沒有權重比較問題——純靠 cluster 相符度決定哪條被命中
- 同一個字出現在不同 cluster 中時，靠 cluster 的其他詞做語義消歧義

### 範例

```
《cluster: [deadlock, concurrency, transaction, lock]》 → [[2026-06-10-deadlock-resolution.md]]
《cluster: [door-lock, key, stuck]》                     → [[2026-06-09-door-lock-repair.md]]
```

## Node 檔案命名

建議格式：`YYYY-MM-DD-簡短英文描述.md`

- 日期前綴方便時間軸排序
- 英文描述避免跨平台編碼問題
- 範例：`2026-06-11-hypermemory-buildout.md`

## Agent 內建記憶設定

agent 的內建記憶（通常為 key-value store）中只需要一行：

```
memory-pool: <absolute-path>/memory-pools/<agent-name>/index.md
```

回憶流程：內建記憶拿路徑 → 讀取 index.md → cluster 匹配 → 讀取 node.md。
