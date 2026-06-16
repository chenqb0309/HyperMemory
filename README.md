# HyperMemory

AI 記憶放大器 — 個人經驗記憶系統。

HyperMemory 不是知識庫。它儲存的是「經驗」——走過的路、犯過的錯、做過的決策。這些是 LLM 權重裡沒有的，沒 recall 到就等於沒發生過。

## 安裝

```bash
git clone https://github.com/chenqb0309/HyperMemory.git
cd HyperMemory

# 全域安裝（從任何目錄使用 hm）
uv tool install .

# 或僅專案內安裝
uv pip install -e .
```

需要 Python 3.10+。

## 快速開始

```bash
# 列出記憶池
hm list

# 回憶經驗
hm recall "MCP debug WSL"

# 啟動 MCP server（供 AI agent 連接）
hm serve
```

第一次執行時會自動建立預設記憶池 `~/.hypermemory/pools/default/`。

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
| `hm recall <keywords>` | 關鍵字匹配回憶 + 語義聯想 suggestions。回傳 node 完整內容，自動更新 total_mentions |
| `hm think <query>` | 習慣性回想。回答前使用，回傳摘要。含鏈結與 suggestions |
| `hm inspect <node>` | 檢視單一 node：frontmatter、鏈結（prenode/nextnodes/ref_by）、body、maturation |

### 寫入

| 指令 | 功能 |
|------|------|
| `hm imprint <file>` | 從檔案刻錄新 node。自動驗證 frontmatter、更新 index、同步 parent、產生 body link |

Node 寫作指引見 `spec/imprint-guide.md`。

### 維護

| 指令 | 功能 |
|------|------|
| `hm maintain recalc` | 權重重算。掃描所有 cluster 鏈，確保 index 指向最高權重 node |
| `hm maintain dreamloop` | 關鍵字去重 + 孤立 cluster 清理 |
| `hm maintain reflect` | Reflection Loop — 掃 session log 自動刻錄新 node |
| `hm maintain sediment` | 舊 node 沈降 — 將長期無 recall 的冷 node 歸檔至 archive index，依 5M1E 維度寫入背景資料 |
| `hm maintain muscle` | Muscle Memory Loop — 掃描符合 skill 門檻的 node，標記 skill_ready |
| `hm maintain all` | 一次跑 recalc + dreamloop + sediment + muscle + reflect |

### 監控

| 指令 | 功能 |
|------|------|
| `hm list` | 列出所有 cluster、當前 node、權重、pending_skills |
| `hm info` | 記憶池健康狀態：node/cluster/type/weight 統計 |
| `hm daemon status` | 查詢 daemon 是否存活、下次排程 |
| `hm daemon log` | 顯示 daemon 日誌 |

### MCP Server

| 指令 | 功能 |
|------|------|
| `hm serve` | 啟動 MCP server（stdio 協定）。支援 10 個 tools |

MCP tools 清單：

| Tool | 功能 |
|------|------|
| `hm_list` | 列出所有 cluster 與指向的 node（含 weight、pending_skills） |
| `hm_recall` | 關鍵字匹配回憶 + 鏈聯想 + 語義聯想 suggestions |
| `hm_think` | 習慣性回想（同 recall 輕量版） |
| `hm_inspect` | 檢視 node 詳細資訊與鏈結 |
| `hm_imprint` | 刻錄新記憶 node |
| `hm_confirm` | 回報經驗確認事件（更新 maturation score） |
| `hm_daemon_status` | 查詢 daemon 排程器狀態 |
| `hm_pool_info` | 記憶池健康狀態 |
| `hm_maintain_now` | 立即觸發維護循環 |
| `hm_explore` | 從 node 出發探索鏈上下游（depth/min_weight/direction） |
| `hm_check_skill_candidates` | 列出所有 skill_ready 的經驗 node |
| `hm_register_skill` | 註冊結構化 skill |

### 背景排程（Daemon）

| 指令 | 功能 |
|------|------|
| `hm daemon start` | 啟動背景 daemon（自動排程維護） |
| `hm daemon stop` | 優雅關閉 |
| `hm daemon status` | 查詢執行狀態與下次排程時間 |
| `hm daemon log` | 顯示 daemon 日誌 |
| `hm daemon install` | 安裝為 systemd user service（開機自動啟動） |
| `hm daemon uninstall` | 移除 systemd service |

Daemon 自動執行以下排程：

| 時間 | 動作 |
|------|------|
| 每天 23:00 | Reflection（掃 log 自動刻錄） |
| 每天 03:00 | Recalc（權重重算） |
| 每週日 04:00 | DreamLoop（關鍵字去重） |
| 每週日 05:00 | Muscle（掃描 skill 門檻） |

```bash
# 一行啟動完整生命週期
hm daemon start

# 或安裝為開機自動啟動
hm daemon install
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
- 三層檢索：直接命中 → 鏈聯想（prenode/nextnodes/ref_by）→ 語義聯想（body keyword 二次 query）
- 權重公式 v2：`weight = engagement × recency + solidification`
  - engagement = `intensity × (1 + 0.1 × mentions) + ref_by_boost + chain_boost`
  - recency = node_type-aware 半衰期（經驗30d / 骨骼90d / 自動刻錄7d）
  - solidification = `intensity × 0.05`（永不歸零的固化基底）
- Maturation score：base_intensity × confirmation_ratio × time_matured（5M1E 維度過濾）
- 舊 node 沈降：weight < 2 且存在 > 14 天 → 歸檔 + 5M1E 背景資料
- Muscle Memory Loop：weight >= 10 + mentions >= 5 + ref_by >= 1 → skill_ready

完整架構規格見 `spec/` 目錄（12 份文件）。

## 專案結構

```
HyperMemory/
├── spec/          → 通用架構規格（agent-agnostic）
├── src/hypermemory/
│   ├── core/      → 核心函式庫（pool/index/node/weight/cluster/maturation/
│   │                 sediment/explore/association/muscle_memory/hm_tools）
│   ├── commands/  → CLI 指令（10 支）
│   ├── __main__.py → 入口
│   └── mcp_server.py → MCP 協定層（分離自 hm_tools）
└── tests/         → 核心單元測試（132 tests）
```
