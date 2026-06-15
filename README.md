# HyperMemory

AI 記憶放大器 — 個人經驗記憶系統。

HyperMemory 不是知識庫。它儲存的是「經驗」——走過的路、犯過的錯、做過的決策。這些是 LLM 權重裡沒有的，沒 recall 到就等於沒發生過。

## 安裝

```bash
git clone https://github.com/chenqb0309/HyperMemory.git
cd HyperMemory
pip install -e .
```

需要 Python 3.9+。

MCP server 內建支援（不需額外套件）：

## 快速開始

```bash
# 指定現有記憶池
hm list --pool /path/to/pool

# 或讓 HM 自動建立預設池
hm list
# → ~/.hypermemory/pools/default/ 自動建立
```

### Pool 指定方式

```bash
hm list --pool /path/to/pool          # --pool 在後
hm --pool /path/to/pool list          # --pool 在前
export HYPERMEMORY_POOL=/path/pool    # 環境變數
hm list                               # 使用預設池
```

## 指令

### 回憶

| 指令 | 功能 |
|------|------|
| `hm recall <keywords>` | 關鍵字匹配回憶。回傳 node 完整內容，自動更新 total_mentions |
| `hm think <query>` | 習慣性回想。回答前使用，回傳摘要，自動更新 total_mentions |
| `hm inspect <node>` | 檢視單一 node：frontmatter、鏈結、body |

### 寫入

| 指令 | 功能 |
|------|------|
| `hm imprint <file>` | 從檔案刻錄新 node。自動驗證 frontmatter、更新 index、同步 parent、產生 body link |

### 維護

| 指令 | 功能 |
|------|------|
| `hm maintain recalc` | 權重重算。掃描所有 cluster 鏈，確保 index 指向最高權重 node |
| `hm maintain dreamloop` | 關鍵字去重 + 孤立 cluster 清理 |
| `hm maintain reflect` | Reflection Loop — 掃 session log 自動刻錄新 node |
| `hm maintain all` | 一次跑 recalc + dreamloop + reflect |

### 監控

| 指令 | 功能 |
|------|------|
| `hm list` | 列出所有 cluster、當前 node、權重 |
| `hm info` | 記憶池健康狀態：node/cluster/type/weight 統計 |
| `hm daemon status` | 查詢 daemon 是否存活、下次排程 |
| `hm daemon log` | 顯示 daemon 日誌 |

### MCP Server

| 指令 | 功能 |
|------|------|
| `hm serve` | 啟動 MCP server（stdio 協定）。支援 8 個 tools |

### 背景排程（Daemon）

| 指令 | 功能 |
|------|------|
| `hm daemon start` | 啟動背景 daemon（自動排程維護） |
| `hm daemon stop` | 優雅關閉 |
| `hm daemon status` | 查詢執行狀態與下次排程時間 |
| `hm daemon log` | 顯示 daemon 日誌 |

Daemon 自動執行以下排程：

| 時間 | 動作 |
|------|------|
| 每天 23:00 | Reflection（掃 log 自動刻錄） |
| 每天 03:00 | Recalc（權重重算） |
| 每週日 04:00 | DreamLoop（關鍵字去重） |

```bash
# 一行啟動完整生命週期
hm daemon start
```

## MCP Server 設定範例

### Hermes Agent

```yaml
mcp_servers:
  hypermemory:
    command: hm
    args: ["serve"]
```

### 通用 MCP Client (Claude Desktop / Cline / Cursor)


## 核心設計

HyperMemory 用 cluster 關鍵字比對取代 embedding 語義搜尋，因為經驗的關鍵字本來就來自對話，自然跟問題的關鍵字重疊。

- 三層認知流：Flashback → Amplifier → Imprint
- 權重公式：`intensity × (1 + 0.1 × total_mentions) × decay(t)`
- Decay：intensity-adaptive 線性衰減，高衝擊經驗衰退更慢
- Node 鏈結：prenode（父）/ nextnodes（子）/ ref_by（跨鏈參考）
- Body Link：自動產生，frontmatter 與文件 body 雙向同步

完整架構規格見 `spec/` 目錄（9 份文件）。

## 專案結構

```
HyperMemory/
├── spec/          → 通用架構規格（agent-agnostic）
├── src/hypermemory/
│   ├── core/      → 核心函式庫（pool/index/node/weight/cluster）
│   ├── commands/  → CLI 指令（8 支）
│   ├── __main__.py → 入口
│   └── mcp_server.py → MCP server
└── tests/         → 核心單元測試（33 tests）
```
