# HyperMemory：Node Schema

## Frontmatter

```yaml
---
type: 2
timestamp: 2026-06-11T14:30:00+08:00
node_type: 2                  # 1=自動刻錄, 2=經驗/決策, 3=骨骼
prenode: null                 # scalar：[[parent-node.md]]
nextnodes: null               # list：
                              #   - [[child-a.md]]
                              #   - [[child-b.md]]
ref_by: null                  # list：
                              #   - [[source-a.md]]
                              #   - [[source-b.md]]
intensity: 7                  # 1-10
total_mentions: 1             # 初始為 1（寫入即算一次）
tags: [hypermemory, design]   # 選擇性，純 metadata
dimensions:                   # 選擇性，5M1E 環境維度
  機: WSL
  料: Python 3.12
skill_ready: false            # 由 Muscle Memory Loop 自動設定
skill_ready_at: null          # ISO timestamp
has_skill: false              # 由 hm_register_skill 自動設定
skill_path: null              # skills/<node>.skill.json
---
```

### 欄位說明

| 欄位 | 必填 | 格式 | 說明 |
|------|------|------|------|
| `type` | 是 | `episodic_memory` | 固定值 |
| `timestamp` | 是 | ISO 8601 + timezone | `2026-06-11T14:30:00+08:00` |
| `node_type` | 是 | 1/2/3 | 引子類型 |
| `prenode` | 否 | `[[wikilink]]` 或 null | 純量，非 list |
| `nextnodes` | 否 | YAML list 或 null | 多個子分支 |
| `ref_by` | 否 | YAML list 或 null | Type 3 參考來源 |
| `intensity` | 是 | 1-10 | 衝擊強度 |
| `total_mentions` | 是 | 整數 | recall 次數 |
| `tags` | 否 | YAML list | metadata |

### prenode 與 nextnodes/ref_by 的 YAML 差異

**prenode** 是純量（scalar）：
```yaml
prenode: [[parent-node.md]]
```

**nextnodes** 和 **ref_by** 是清單（list）：
```yaml
nextnodes:
  - [[child-a.md]]
  - [[child-b.md]]
```

混淆兩者會導致 parser 將鏈結解釋為巢狀結構。

## Body Link 雙軌設計

Frontmatter 中的 `[[wikilink]]` 是 AI parsing 的 canonical source。body 中的 `## 關聯` 區塊是給人類在 Obsidian Graph View 中檢視的鏡像。

```
---
<frontmatter>
---

# Title

## 關聯

- 前驅：[[parent-node.md]]
- 後繼：[[child-a.md]]、[[child-b.md]]
- 參考來源：[[source-a.md]]

## 正文

...
```

規則：
- prenode 非 null → `前驅：[[node.md]]`
- nextnodes 非空 → `後繼：[[node1.md]]、[[node2.md]]`
- ref_by 非空 → `參考來源：[[src1.md]]、[[src2.md]]`
- 該欄位為 null/空時，對應行省略
1. 三個欄位皆空時，整個 `## 關聯` 區塊省略
2. `## 關聯` 永遠在 title 之後、正文第一節之前

## Memory Marker（設計約束 7）

每個 node 檔案以成對 marker 包覆，使 consuming AI 在任意存取路徑下都能直觀辨識「這是記憶，不是事實」。

### 檔案格式

```
^HM_MEMORY_START
# HyperMemory 經驗記錄 — 非當前事實，使用前請確認時效性與場景適用性
---
<frontmatter>
---

# Title

## 正文

...
^HM_MEMORY_END
```

### 欄位

| 行 | 內容 | 說明 |
|----|------|------|
| 1 | `^HM_MEMORY_START` | marker 起始，宣告以下內容為經驗記憶 |
| 2 | `# HyperMemory 經驗記錄 — 非當前事實，使用前請確認時效性與場景適用性` | disclaimer 文字，consuming AI 在 context 中直接可見 |
| 3-? | 原有 frontmatter + body | 不受 marker 影響 |
| 末 | `^HM_MEMORY_END` | marker 結束 |

### 規則

- marker 不參與任何邏輯運算（權重、maturation、filter 都不依賴它）
- `parse_frontmatter()` 自動跳過 marker 行
- `wrap_markers()` / `strip_markers()` 提供程式化增刪
- 三個寫入路徑強制附加：CLI imprint、MCP imprint、reflect

## 節點命名

`YYYY-MM-DD-簡短英文描述.md`

範例：`2026-06-11-hypermemory-buildout.md`
