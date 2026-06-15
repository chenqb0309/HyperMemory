# HyperMemory MCP Server — 設定指南

HyperMemory 可以作為 MCP server 運行，讓任何支援 MCP 的 AI client 直接存取記憶池。

## 啟動方式

```bash
hm serve

# 指定記憶池（預設 ~/.hypermemory/pools/default/）
hm serve --pool /path/to/pool
```

MCP server 使用 stdio 傳輸，透過 `Content-Length` 框架傳遞 JSON-RPC 訊息。

## 可用工具

| 工具 | 功能 |
|------|------|
| `hm_list` | 列出所有 cluster 與當前 node |
| `hm_recall` | 關鍵字匹配回憶（回傳完整 node） |
| `hm_think` | 回答前習慣性回想（回傳摘要） |
| `hm_inspect` | 檢視單一 node 詳細資訊 |
| `hm_imprint` | 從內容刻錄新 node |

## Client 設定

### Claude Desktop

編輯 `claude_desktop_config.json`：

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
**Linux:** `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "hypermemory": {
      "command": "python3",
      "args": ["-m", "hypermemory", "serve", "--pool", "/path/to/your/pool"]
    }
  }
}
```

### Cline (VS Code)

編輯 VS Code `settings.json`（Command Palette → Preferences: Open Settings (JSON)）：

```json
{
  "cline.mcpServers": {
    "hypermemory": {
      "command": "python3",
      "args": ["-m", "hypermemory", "serve", "--pool", "/path/to/your/pool"]
    }
  }
}
```

### Cursor

在專案根目錄建立 `.cursor/mcp.json`：

```json
{
  "mcpServers": {
    "hypermemory": {
      "command": "python3",
      "args": ["-m", "hypermemory", "serve", "--pool", "/path/to/your/pool"]
    }
  }
}
```

### 通用 MCP Client

```json
{
  "mcpServers": {
    "hypermemory": {
      "command": "python3",
      "args": ["-m", "hypermemory", "serve", "--pool", "/path/to/your/pool"]
    }
  }
}
```

## 安裝相依

```bash
cd HyperMemory
pip install -e .           # CLI 可用
pip install -e ".[mcp]"    # 如需要 MCP 套件支援
```

## 環境變數

所有 client 也支援 `HYPERMEMORY_POOL` 環境變數：

```json
{
  "mcpServers": {
    "hypermemory": {
      "command": "python3",
      "args": ["-m", "hypermemory", "serve"],
      "env": {
        "HYPERMEMORY_POOL": "/path/to/your/pool"
      }
    }
  }
}
```

## 驗證連線

啟動後可用 MCP Inspector 測試：

```bash
npx @modelcontextprotocol/inspector python3 -m hypermemory serve --pool /path/to/pool
```
