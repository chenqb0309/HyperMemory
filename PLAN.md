# HyperMemory：實作方案

## 完成狀態

```
Phase 1: CLI 核心      ✅
Phase 2: MCP Server   ✅
Phase 3: 維護循環      ✅
        產品化         🔜
```

## 指令清單

| 指令 | 功能 | 狀態 |
|------|------|------|
| `hm list` | 列出 cluster 與 node | ✅ |
| `hm recall` | 關鍵字匹配回憶 | ✅ |
| `hm inspect` | 檢視 node 與鏈結 | ✅ |
| `hm imprint` | 從檔案刻錄（自動 body link） | ✅ |
| `hm think` | 習慣性回想 | ✅ |
| `hm maintain` | 維護循環（recalc/dreamloop/all） | ✅ |
| `hm info` | 記憶池健康狀態 | ✅ |
| `hm serve` | MCP server（stdio） | ✅ |

## MCP Server Tools

| Tool | 功能 | 狀態 |
|------|------|------|
| `hm_list` | 列出 cluster | ✅ |
| `hm_recall` | 關鍵字回憶 | ✅ |
| `hm_think` | 回答前習慣性回想 | ✅ |
| `hm_inspect` | 檢視 node | ✅ |
| `hm_imprint` | 從內容刻錄 | ✅ |

## 基礎建設

- pyproject.toml（相依、entry point）✅
- Unit tests（33 tests，4 modules）✅
- README（完整指令）✅

## 產品化待辦

- [ ] GitHub Actions CI（自動跑 test）
- [ ] PyPI 發布
- [ ] MCP 整合文件（Claude Desktop / Cline 設定範例）
