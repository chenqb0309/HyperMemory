# HyperMemory Product Roadmap

目標：HM 成為自足產品，任何 AI agent 均可透過 MCP 使用，不需依賴外部排程器。

---

## Phase 1 — 內建排程器 `hm daemon`

讓 HM 有自己的 background scheduler，取代對 Hermes cron 的依賴。

### 新增指令

```
hm daemon start       # 啟動背景行程（daemon）
hm daemon stop        # 停止
hm daemon status      # 檢查是否存活 + 下次排程時間
hm daemon log         # 顯示最近 daemon 輸出
```

### 排程表（與現行 cron 一致）

| 時間 | 動作 | 說明 |
|------|------|------|
| 每天 03:00 | `hm maintain recalc` | 權重重算 |
| 每週日 04:00 | `hm maintain dreamloop` | 關鍵字去重 + 孤兒清理 |
| 每天 23:00 | `hm maintain reflect` | 掃 log 自動刻錄新 node |

### 實作方式

- 純 Python、零外部依賴（不用 cron/apscheduler）
- 使用 `threading.Timer` 或簡單 while-sleep 迴圈
- PID file 防止重複
- 輸出寫到 `~/.hypermemory/daemon.log`
- 收到 SIGTERM/SIGINT 優雅結束

### 檔案變更

- 新增 `src/hypermemory/commands/daemon.py`
- 修改 `__main__.py` 加入 `daemon` subcommand

---

## Phase 2 — 服務安裝 `hm daemon install`

將 daemon 註冊為 systemd user service，開機自動啟動。

### 新增指令

```
hm daemon install     # 安裝 systemd user service
hm daemon uninstall   # 移除 service
```

### 行為

- 產生 `~/.config/systemd/user/hypermemory.service`
- 使用 `systemctl --user enable --now`
- 支援 restart（process monitor restart）

---

## Phase 3 — MCP 增強

讓 HM MCP server 提供 daemon 狀態與維護操作，agent 可透過 MCP 查詢與觸發。

### 新增 MCP Tools

| Tool | 功能 |
|------|------|
| `hm_daemon_status` | 查詢 daemon 是否存活、下次排程 |
| `hm_maintain_now` | 立即觸發 maintain recalc/dreamloop/reflect/all |
| `hm_pool_info` | 記憶池健康狀態（node 數、cluster 數、index 完整性） |

### 檔案變更

- 修改 `mcp_server.py` 加入新 tools
- TOOLS dict 擴充 + handle_request 新分支

---

## Phase 4 — 文件與產品化

讓 HM 看起來／用起來像完整產品。

### 事項

- README.md 加入 daemon 章節
- MCP_SETUP.md 更新為新格式
- `install.sh` 支援 daemon setup
- 版本 bump → 1.1.0
- CHANGELOG.md

### 驗收標準

- 全新安裝者只要 `pip install hypermemory && hm daemon install` 就能啟動完整生命週期
- 任何 AI agent 透過 `hm serve`（MCP）即可使用全部功能
- 無需額外 cron 設定
