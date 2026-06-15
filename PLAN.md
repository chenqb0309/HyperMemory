# HyperMemory：實作方案

## 現狀

HyperMemory 的架構與規格已在 `spec/` 中完全定義。記憶池也已有實際內容（Offer pool 20 nodes、12 clusters）。尚未實作的部分是：

1. **CLI 工具** — 作為服務邊界，強制所有操作遵守規格
2. **MCP server** — 讓任何 MCP client 對接 HyperMemory

## 實作階段

### Phase 1：CLI 核心（建議優先）

建立 `hm` 指令，涵蓋最基本的記憶操作。

**指令清單：**

| 指令 | 功能 | 依賴 |
|------|------|------|
| `hm list` | 列出所有 cluster 與當前 node | pool + index 讀取 |
| `hm recall <keywords>` | 關鍵字匹配 → 回傳 node 內容 + total_mentions +1 | pool + index + cluster 比對 |
| `hm imprint <file>` | 從 frontmatter 規範寫入新 node，更新 index | pool + index + cluster |
| `hm inspect <node>` | 檢視單一 node 的 frontmatter + 鏈結 | pool 讀取 |

**實作順序：**
1. `hm list` — 最簡單，先建立專案骨架
2. `hm recall` — 核心回憶流程
3. `hm inspect` — 鏈結走訪（prenode / nextnodes）
4. `hm imprint` — 寫入 + index 更新

**不需要在 Phase 1 做的：**
- MCP server（Phase 2）
- Recalc / DreamLoop / Reflection Loop 的自動排程（各平台自己用 cron）
- 圖形化介面

### Phase 2：MCP Server

將 CLI 核心包裝為 MCP server，任何支援 MCP 的 agent 可直接對接。

```
hm serve
    ↓
MCP tools: recall, imprint, list, inspect, maintain
    ↓
任何 MCP client
```

### Phase 3：維護循環腳本

提供獨立的 maintain 指令，觸發三種維護操作：

```
hm maintain --recalc
hm maintain --dreamloop
hm maintain --reflect
```

排程由各平台負責（cron、systemd timer、Windows Task Scheduler 等），HyperMemory 只提供單次執行指令。

## 技術選型

| 層 | 選項 | 理由 |
|---|------|------|
| 語言 | Python 3 | 已驗證的 frontmatter parser、sqlite3、跨平台 |
| CLI | argparse（stdlib） | 零依賴，夠用 |
| 套件管理 | uv 或 pip | 最小依賴（僅 pyyaml for frontmatter） |

## 風險

| 風險 | 緩解 |
|------|------|
| Windows 路徑處理 | Python pathlib 跨平台 |
| 大規模記憶池（>1000 nodes） | 索引查詢仍是 O(n)，但 n=cluster 數非 node 數。 cluster 通常 <100 |
| 並發寫入衝突 | 檔案鎖定（fcntl / lockfile） |
