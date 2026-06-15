# HyperMemory

AI 記憶放大器 — CLI 工具。

## 安裝

```bash
cd HyperMemory
pip install -e .
```

需要 Python 3.10+。

## 快速開始

```bash
# 不指定 pool（使用預設 ~/.hypermemory/pools/default/，自動建立）
hm list

# 指定 pool
hm list --pool /path/to/pool

# 透過環境變數
export HYPERMEMORY_POOL=/path/to/pool
hm list
```

## 指令

| 指令 | 功能 |
|------|------|
| `hm list` | 列出所有 cluster 與當前 node |
| `hm recall <keywords>` | 關鍵字匹配回憶 |
| `hm inspect <node>` | 檢視單一 node 與鏈結 |
| `hm imprint <file>` | 從檔案刻錄新 node（自動產生 body link） |

## 規格

完整架構規格見 `spec/` 目錄。
