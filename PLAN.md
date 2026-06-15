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
| `hm think` | 習慣性回想（回答前使用） | ✅ |
| `hm maintain recalc` | 權重重算 | ✅ |
| `hm maintain dreamloop` | 關鍵字去重 | ✅ |
| `hm maintain reflect` | 反思刻錄（從 log 自動產生 node） | ✅ |
| `hm maintain all` | 一次跑全部維護 | ✅ |
| `hm info` | 記憶池健康狀態 | ✅ |
| `hm log capture` | 紀錄經驗到 log | ✅ |
| `hm log recent` | 顯示最近 log | ✅ |
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

| 項目 | 狀態 |
|------|------|
| pyproject.toml | ✅ |
| Unit tests（33 tests, 4 modules） | ✅ |
| GitHub Actions CI（3.10/3.11/3.12） | ✅ |
| 邊界錯誤處理 | ✅ |
| Session log | ✅ |
| Reflection Loop | ✅ |
| README | ✅ |
| MCP server 實戰驗證 | ⬜ |
| PyPI 發布 | ⬜ |
