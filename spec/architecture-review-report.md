# HyperMemory — 架構審查報告（Architecture Review Report）

**專案**: HyperMemory v1.2.0
**生成日期**: 2026-06-22
**目的**: 提供外部 AI 架構師進行全方位架構評估與代碼診斷之技術基底
**作者**: Offer (CTO, Engineer_Obsidian)

---

## 目錄

1. [資料結構 (Schema)](#1-資料結構-schema)
2. [核心代碼實作邏輯](#2-核心代碼實作邏輯)
3. [權重公式實戰參數](#3-權重公式實戰參數)
4. [運作效果與瓶頸](#4-運作效果與瓶頸)

---

## 1. 資料結構 (Schema)

### 1.1 Memory Node 完整欄位定義

每個記憶節點是一個 Markdown 檔案（`YYYY-MM-DD-slug.md`），含 YAML frontmatter + Markdown body，以 `^HM_MEMORY_START` / `^HM_MEMORY_END` marker 包覆（設計約束 7）。

#### Frontmatter 欄位表

| 欄位 | 必填 | 類型 | 格式／範圍 | 說明 |
|------|------|------|-----------|------|
| `type` | 是 | str | `episodic_memory` (固定) | 節點類型識別 |
| `timestamp` | 是 | str (ISO 8601) | `2026-06-11T17:00:00+08:00` | 經驗發生時間 |
| `node_type` | 是 | int | 1 / 2 / 3 | 1=自動刻錄, 2=經驗/決策, 3=骨骼 |
| `prenode` | 否 | str (wikilink) | `[[parent.md]]` 或 `null` | 前驅節點 (scalar) |
| `nextnodes` | 否 | list[str] | `- [[child-a.md]]` | 後繼節點 (list) |
| `ref_by` | 否 | list[str] | `- [[source.md]]` | 參考來源 (list) |
| `intensity` | 是 | int | 1–10 | 經驗強度 |
| `total_mentions` | 是 | int | >= 0 | 累計 recall 命中次數 |
| `tags` | 否 | list[str] | `[hypermemory, design]` | 分類標籤 (metadata) |
| `skill_ready` | 否 | bool | true/false | 肌肉記憶候選標記 |
| `skill_ready_at` | 否 | str (ISO 8601) | `2026-06-15T...` | 標記時間戳 |
| `has_skill` | 否 | bool | true/false | 已轉換為 skill |
| `skill_path` | 否 | str | `skills/xxx.skill.json` | skill 檔案路徑 |
| `dimensions` | 否 | dict | `機: WSL`, `料: Python 3.12` | 5M1E 環境維度 |

#### 實體檔案格式

```
^HM_MEMORY_START
# HyperMemory 經驗記錄 — 非當前事實，使用前請確認時效性與場景適用性
---
type: episodic_memory
timestamp: 2026-06-11T17:00:00+08:00
node_type: 3
prenode: [[2026-06-11-hypermemory-first-imprint.md]]
nextnodes:
  - [[2026-06-11-hm-vs-wiki-comparison.md]]
  - [[2026-06-15-mcp-debug.md]]
ref_by: null
intensity: 9
total_mentions: 5
tags: [hypermemory, milestone, build-out]
---

# Hypermemory 完整建置歷程

## 關聯
- 前驅：[[2026-06-11-hypermemory-first-imprint.md]]
- 後繼：[[2026-06-11-hm-vs-wiki-comparison.md]]、[[2026-06-15-mcp-debug.md]]

## 正文

從一次記憶 compact 需求出發...
^HM_MEMORY_END
```

#### 解析器行為 (node.py)

`parse_frontmatter()` 使用正則解析 YAML frontmatter，支援：
- **Scalar 欄位**: `type`, `timestamp`, `node_type`, `intensity`, `total_mentions` — 單行 regex
- **Boolean 欄位**: `skill_ready`, `has_skill` — `"true"` → True
- **Scalar wikilink**: `prenode` — `[[wikilink]]` → extract inner, `null` → None
- **List 欄位**: `nextnodes`, `ref_by`, `tags` — 支援 inline `[a, b, c]` 與 multi-line `- item` 格式
- **Nested dict**: `dimensions` — 從 `dimensions:` 區塊逐行解析 `key: value`

**重要 edge case**: `ref_by: null` (scalar) vs `ref_by:` (list, empty) vs `ref_by: []` (explicit empty) 三種形式的數值類型不一致。現行處理：`_parse_list_field()` 對 `null` 回傳 `[]`，對 multi-line 空 list 也回傳 `[]`，但不保證所有 YAML 邊界 case 正確。

### 1.2 Index 索引結構

```
《cluster: [hypermemory, 記憶架構, 設計]》 → [[2026-06-11-hypermemory-buildout.md]]
```

每行格式：`《cluster: [kw1, kw2, ...]》 → [[filename.md]]`

- **pointer 語義**: 指向鏈頭（權重最高者）。`hm maintain recalc` 重新計算鏈中所有節點權重，將 pointer 移到最高者。
- **更新機制**: `imprint` 寫入新 node + 指定 `prenode` → 自動比較新/舊 weight → pointer 指向較高者 → 呼叫 `sync_parent_links()` 更新 parent frontmatter

### 1.3 5M1E 維度系統 (dimensions.py)

| 維度 | 英文 | 範例 |
|------|------|------|
| 人 | Man | Jet |
| 機 | Machine | WSL |
| 料 | Material | Python 3.12 |
| 法 | Method | uv-install |
| 環 | Environment | venv |
| 量 | Measurement | latency=200ms |

**匹配規則 (`is_compatible()`, L48-69)**:
- Node 未指定某維度 → 相容（context-agnostic）
- Node 指定、context 未提供 → 相容
- 兩邊都有值 → 必須完全相等（case-insensitive）
- 任一維度衝突 → 整筆 node 不相容（**硬濾波**，不扣分，不降權重）

**當前狀態**：`is_compatible()` 已實作，但 recall/think 管線 **未強制執行** 此過濾。Layer 1 的 5M1E 維度匹配僅在 `explore.py` 和 `scan_maturation_all()` 中選擇性使用。

### 1.4 Chain Length 計算 (pool.py L63-101)

```
def resolve_chain_length(pool, node_name, fm, max_depth=5):
    count = 1
    # backward: follow prenode chain
    # forward: BFS on nextnodes
    return count
```

- 往前追溯 `prenode` 鏈 (最多 5 層)
- 往後 BFS `nextnodes` (最多 5 層)
- **實戰現狀**: 已整合進 `HMTools` 的 `_chain_length()`，recall/think/inspect/list 全都透過 `calc_weight(chain_length=...)` 正確傳入。**chain_boost 已在生產中生效**。

---

## 2. 核心代碼實作邏輯

### 2.1 三層檢索管線

```
User Query (keywords / natural text)
       │
       ▼
┌──────────────────────────────────────────────────┐
│ Layer 1: Cluster 關鍵字粗篩 (cluster.py)          │
│  ┌─ substring match (CJK-friendly)               │
│  ├─ score = matched / len(query)                 │
│  ├─ coverage bonus = matched / len(cluster) × 0.2│
│  ├─ threshold = 0.3 (CLUSTER_THRESHOLD)          │
│  └─ returns sorted list by combined score         │
└──────────────────────┬───────────────────────────┘
                       ▼
┌──────────────────────────────────────────────────┐
│ Layer 2: 鏈聯想 (prenode/nextnodes/ref_by)        │
│  ┌─ recall/think 回傳結果中內含完整鏈結資訊       │
│  ├─ MCP hm_explore 提供 BFS 遍歷                  │
│  ├─ hm_inspect 顯示單一 node 完整關係             │
│  └─ AI agent 可直接循鏈導航                       │
└──────────────────────┬───────────────────────────┘
                       ▼
┌──────────────────────────────────────────────────┐
│ Layer 3: 語義聯想 (association.py)               │
│  ┌─ 對 top-1 result 做二次查詢                    │
│  ├─ extract_body_keywords: body 高頻實詞提取      │
│  ├─ 用這些詞重新 query index                     │
│  ├─ 回傳 suggestions (top_k=3)                   │
│  └─ 純 keyword-space，零 embedding                │
└──────────────────────────────────────────────────┘
```

### 2.2 Layer 1 細則：Cluster 關鍵字粗篩

**實作檔案**: `src/hypermemory/core/cluster.py`, 函數 `find_all_clusters()` (L58-113)

```python
query_lower = [q.strip().lower() for q in query if q.strip()]
cluster_lower = [k.strip().lower() for k in kw_list if k.strip()]

matched = 0
for q in query_lower:
    for c in cluster_lower:
        if q in c or c in q:    # CJK substring: 「設計」→「設計哲學」
            matched += 1
            break

score = matched / len(query_lower)           # 主要分數
coverage = matched / len(cluster_lower)      # cluster 覆蓋率
combined = score + coverage * 0.2            # 最終分數
```

**關鍵行為**:
- CJK substring match (雙向): query substring in cluster OR cluster substring in query
- 僅 matched > 0 的 entry 進入評分
- `min_score=0.0` 用於 association (無門檻)
- `min_score=0.3` 用於 recall/think (標準門檻)
- 結果按 `combined` 降冪排序

**覆蓋率權重不一致** (已知, 設計意圖非 bug):
- `cluster.py` (recall 管線): coverage × **0.2**
- `index.py` `match_cluster()` (reflect 重複檢查): coverage × **0.3**
- 兩條管線用途不同，數值差異是設計決定

### 2.3 Layer 3 細則：Body 關鍵詞提取 (association.py)

**`extract_body_keywords()` (L117-152)**:

```python
def extract_body_keywords(body_text, max_keywords=8):
    # CJK: extract all 2-3 char substrings from [\\u4e00-\\u9fff]+ phrases
    #   filter: stopwords in STOPWORDS_CJK (~50 items)
    #   filter: first char is single-char stopword (的/了/是/關...)
    # English: split → strip punctuation → lowercase
    #   filter: stopwords (~100 items)
    #   filter: length <= 2
    # Combine: CJK first, dedup preserve order
    return result[:max_keywords]
```

**停止詞集規模**: CJK ~50 字, English ~100 字

**`associative_recall()` (L158-291)**:
1. 讀取 source node body
2. 提取 body keywords
3. 用這些 keywords 重新 query index (`find_all_clusters(body_keywords, entries, min_score=0.0)`)
4. 過濾掉 source node 自身
5. 取 top_k=3, 回傳 suggestions (含 title, score, match_keywords)

### 2.4 串行機制：pre/next 標籤導航

**資料結構**: 單向鏈結串列（單 parent + 多 children）

**AI 導航方式**:
1. `recall` / `think` 回傳結果中直接包含 `prenode` / `nextnodes` / `ref_by` 欄位
2. `hm_explore` (explore.py L15-82): BFS 遍歷，支援 direction=forward/backward/both, depth 控制, min_weight 過濾, 5M1E 維度過濾
3. `hm_inspect`: 單一 node 顯示完整鏈結關係 + 權重值

**鏈維護**:
- `hm imprint` 寫入新 node，若指定 `prenode` → 自動呼叫 `sync_parent_links()` 更新 parent 的 nextnodes
- `hm maintain recalc` → 全池 weight 重算 + 重對齊 index pointer
- 重複拜訪保護: `visited set` (explore.py L109/162)

### 2.5 Recall 管線實作細節 (hm_tools.py)

**`recall()` (L77-220)**:
1. 解析關鍵詞 (`keywords` comma-separated string → list)
2. `find_all_clusters(kw_list, entries, min_score=0.3)` → 匹配結果
3. 逐一讀取 node → `calc_weight()` (含 chain_length) → `calc_maturation()`
4. **按 timestamp 降冪排序** (newest first) — 非按 weight 排序
5. Layer 3: 對 top-1 result 執行 `associative_recall()`
6. **更新 total_mentions**: 對 top result 的 frontmatter 中 total_mentions +1 (in-place file write)
7. 若無 active node 匹配 → 嘗試 background recall (sediment 歸檔資料)

**`think()` (L222-338)**:
- 與 `recall()` 相同的查詢邏輯
- 只回傳 best result，額外包含 body summary (前 5 行非關聯區塊內容)
- 同樣更新 total_mentions

### 2.6 Maturation Score (經驗成熟度) — maturation.py

```
maturation = base_intensity × confirmation_ratio × time_matured

confirmation_ratio = (positive + 1) / (positive + negative + 1)
  → 無確認事件 = 1.0（中性起步）
  → 正事件多 → 趨近 1.0
  → 負事件多 → 趨近 0.0

time_matured:
  >= 30 天 → 1.0
  >= 14 天 → 0.8
  <  14 天 → 0.5
```

- 確認事件存於 `<pool>/confirm/` 子目錄 (獨立 node 檔案)
- 每筆確認事件含：source, result, agent, timestamp, dimensions, context_summary
- `hm_confirm` MCP tool 供 agent 回報驗證結果

### 2.7 維護循環（Maintenance Loop）

由 daemon 定時驅動，排程時間及對應 CLI：

| 時間 | 動作 | CLI 對應 | 實作函數 |
|------|------|----------|----------|
| 每天 23:00 | Reflection — 掃描 agent log，自動刻錄新經驗 | `hm maintain reflect` | `maintain._reflect()` |
| 每天 03:00 | Recalc — 全 pool 權重重算，重對齊 index pointer | `hm maintain recalc` | `maintain._recalc()` |
| 每週日 04:00 | DreamLoop — index 關鍵字去重 + 孤立清理 | `hm maintain dreamloop` | `maintain._dreamloop()` |
| 每週日 05:00 | Muscle — 掃描 skill_ready 條件 | `hm maintain muscle` | `muscle_memory._scan_pool()` |
| (非定時) | Sediment — weight < 2.0 + >= 14 天的 cold node 歸檔 | `hm maintain sediment` | `sediment.sediment_pool()` |

**已知差距 (code-review 已確認)**:
- DreamLoop 僅做同一 cluster 內關鍵字去重 + 孤立 cluster 移除，**未做跨 cluster 語義發現**
- Sediment 是獨立指令，**未被整合進 DreamLoop**
- 「自動刻錄」功能 (`hm maintain reflect`) 已實作但需 agent log 作為輸入源，生產中尚未啟用

### 2.8 沈降管線 — sediment.py

**冷偵測條件**:
- `weight < 2.0` → COLD_WEIGHT_THRESHOLD
- `days >= 14` → MIN_NODE_AGE_DAYS
- 必須有 timestamp（無 timestamp 保守處理 → 不歸檔）

**歸檔動作**:
1. 從 `index.md` 移除條目
2. 追加到 `archive_index.md`
3. 依 5M1E 維度寫入 `<pool>/background/<維度>.json`
4. **原始 node 檔案保留**（不移除）

### 2.9 肌肉記憶管線 — muscle_memory.py

**skill_ready 條件** (AND):
```python
weight >= 10.0            # MIN_SKILL_WEIGHT
AND total_mentions >= 5   # MIN_SKILL_MENTIONS
AND len(ref_by) >= 1      # MIN_SKILL_REF_BY
AND has_skill != True
AND node_type != 1        # 非自動刻錄
```

**v1.2.0 新增**: 主要門檻改為 `maturation_score >= 8.0` (MIN_SKILL_MATURATION)，weight 門檻降為輔助（fallback 仍可用 weight >= 15.0）。

**其他常數**:
- `SKILL_READY_EXPIRE_DAYS = 30` — 符合條件但 30 天未轉換 → 自動清除 skill_ready flag
- `MIN_TIME_MATURED = 0.8` — 最低 time_matured 因子

### 2.10 Memory Marker (設計約束 7) — node.py

```python
MARKER_START = "^HM_MEMORY_START"
MARKER_DISC  = "# HyperMemory 經驗記錄 — 非當前事實，使用前請確認時效性與場景適用性"
MARKER_END   = "^HM_MEMORY_END"
```

**行為規則**:
- 三個寫入路徑強制附加：CLI imprint、MCP imprint、reflect
- `parse_frontmatter()` 自動跳過 marker 行 (prefix-based skip: `^` 或 MARKER_DISC)
- Marker **不參與任何邏輯運算** (weight, maturation, filter 都不依賴它)
- `wrap_markers()` / `strip_markers()` 為 idempotent (已存在則 no-op)
- 35 個既有 node 已全數補上 marker (2026-06-17 批次更新)

### 2.11 MCP 通訊協定

| 屬性 | 值 |
|------|-----|
| Transport | stdio + newline-delimited JSON |
| Protocol | MCP 2024-11-05（echo client requested version） |
| Tools 數 | 12 |
| 依賴 | `mcp` pip 套件為 optional |
| 並行模型 | 單線程同步（MCP 協議本質 single-request-at-a-time） |

**12 個 MCP tools**:
1. `hm_list` — 列出所有 cluster
2. `hm_recall` — 關鍵字回憶
3. `hm_think` — 習慣性回想（recall 的簡化版）
4. `hm_inspect` — 單一 node 檢視
5. `hm_imprint` — 刻錄新記憶
6. `hm_confirm` — 回報確認事件
7. `hm_daemon_status` — 排程器狀態
8. `hm_pool_info` — 記憶池健康度
9. `hm_maintain_now` — 立即觸發維護
10. `hm_explore` — 鏈探索
11. `hm_check_skill_candidates` — 列出 skill_ready 候選
12. `hm_register_skill` — 註冊轉換為 skill

---

## 3. 權重公式實戰參數

### 3.1 完整公式

```python
weight = engagement * recency + solidification

engagement  = intensity * (1 + 0.1 * total_mentions)
            + ref_by_count * 0.3
            + max(0, chain_length - 1) * 0.2

recency     = node_type-aware 半衰期指數模型
              (full 1.0 within half-life, exponential decay after)

solidification = intensity * 0.05   # 永不衰減基底
```

### 3.2 所有常數一覽

| 常數 | 值 | 所在檔案 (行) | 說明 |
|------|-----|--------------|------|
| `mentions_multiplier` | **0.1** | weight.py L58 | 每次 mention 增加 10% 的 intensity 基數 |
| `ref_by_boost` | **0.3** | weight.py L59 | 每次被引用加 0.3 |
| `chain_boost` | **0.2** | weight.py L60 | 鏈長度每多 1 節點加 0.2（僅 chain_len > 1） |
| `solidification_rate` | **0.05** | weight.py L62 (inline) | intensity × 5% = 永不衰減基底 |
| `recency_floor` | **0.05** | weight.py L84 | recency 最小值下限 |
| `half_life_經驗` | **30 天** | weight.py L15 | 一般經驗半衰期 |
| `half_life_決策` | **30 天** | weight.py L16 | 決策同經驗 |
| `half_life_骨骼` | **90 天** | weight.py L17 | 骨骼級知識半衰期最長 |
| `half_life_方法` | **30 天** | weight.py L18 | 方法同經驗 |
| `half_life_自動刻錄` | **7 天** | weight.py L19 | 自動產生的 node 最短半衰期 |
| `default_half_life` | **30 天** | weight.py L21 | fallback 值 |
| `COLD_WEIGHT_THRESHOLD` | **2.0** | sediment.py L15 | 低於此 weight 的 cold 候選 |
| `MIN_NODE_AGE_DAYS` | **14** | sediment.py L16 | 至少存在 14 天才可歸檔 |
| `MIN_SKILL_WEIGHT` | **10.0** | muscle_memory.py L24 | skill 候選最低權重 (輔助門檻) |
| `MIN_SKILL_MENTIONS` | **5** | muscle_memory.py L25 | skill 候選最低 mentions |
| `MIN_SKILL_REF_BY` | **1** | muscle_memory.py L26 | skill 候選最低 ref_by |
| `MIN_SKILL_MATURATION` | **8.0** | muscle_memory.py L27 | skill 候選最小 maturation (主要門檻) |
| `MIN_TIME_MATURED` | **0.8** | muscle_memory.py L28 | skill 候選最小 time_matured 因子 |
| `SKILL_READY_EXPIRE_DAYS` | **30** | muscle_memory.py L23 | skill_ready 過期天數 |
| `CLUSTER_THRESHOLD` | **0.3** | hm_tools.py L87/L232 | 第一層 cluster 匹配最低分 |
| `ASSOCIATION_TOP_K` | **3** | association.py L158 | 語義聯想回傳上限 |
| `BODY_KEYWORDS_MAX` | **8** | association.py L117 | body 關鍵詞提取上限 |
| `EXPLORE_DEPTH` | **3** | explore.py (function param) | 鏈探索預設深度 |

### 3.3 衰減模型細則

```python
# 1. 參數優先順序:
#    days_since_last_hit > timestamp_str > 無參數 → recency=1.0
if days_since_last_hit is not None:
    days = days_since_last_hit
elif timestamp_str:
    # 從 ISO timestamp 計算 days_since
    ts = datetime.fromisoformat(timestamp_str)
    days = max(0, (now - ts).days)
else:
    days = None

# 2. 半衰期模型
if days is not None:
    half_life = HALF_LIFE_MAP.get(node_type, DEFAULT_HALF_LIFE)
    if days < half_life:
        recency = 1.0                  # 半衰期內全額
    else:
        excess = days - half_life
        recency = max(0.05, exp(-excess / half_life))  # 指數衰減
else:
    recency = 1.0  # 無時間資訊 → 樂觀估計

# 3. 最終 weight
return engagement * recency + float(intensity) * 0.05
```

### 3.4 數值範例（實際可驗證）

**情境 A：高活躍核心節點**
```
intensity=9, mentions=5, ref_by=0, chain_length=7, 剛建立
engagement = 9 * (1 + 0.5) + 0 + 1.2 = 13.5 + 1.2 = 14.7
recency = 1.0 (半衰期內)
solidification = 9 * 0.05 = 0.45
weight = 14.7 * 1.0 + 0.45 = 15.15
```

**情境 B：冷 node（30 天無 recall）**
```
intensity=5, mentions=1, node_type=經驗, days=60
engagement = 5 * (1 + 0.1) = 5.5
excess = 60 - 30 = 30
recency = exp(-30/30) = 0.3679
solidification = 5 * 0.05 = 0.25
weight = 5.5 * 0.3679 + 0.25 = 2.27
```

**情境 C：自動刻錄快速衰退**
```
intensity=3, mentions=0, node_type=自動刻錄, days=21
engagement = 3 * 1.0 = 3.0
excess = 21 - 7 = 14
recency = exp(-14/7) = 0.1353
solidification = 3 * 0.05 = 0.15
weight = 3.0 * 0.1353 + 0.15 = 0.56 → 低於 sediment 門檻 2.0
```

### 3.5 Weight v2 完整公式簽名 (weight.py L24-32)

```python
def calc_weight(
    intensity: int,           # 1-10
    total_mentions: int,      # >= 0
    timestamp_str: str | None = None,   # ISO 8601
    node_type: str = "經驗",           # 決定 half_life
    ref_by_count: int = 0,             # ref_by 長度
    chain_length: int = 1,             # chain boost
    days_since_last_hit: int | None = None,  # 手動覆蓋
) -> float:
```

---

## 4. 運作效果與瓶頸

### 4.1 測試覆蓋與驗證結果

**測試數據（2026-06-22 執行）**:
```
19 test files, 207 tests, 0 failed, 1 warning (5.32s)
```

| 測試檔案 | Tests | 說明 |
|---------|-------|------|
| test_weight.py | 8 | v1 權重相容性 |
| test_weight_v2.py | 27 | v2 公式（半衰期、solidification、edge cases） |
| test_cluster.py | ~15 | 關鍵字匹配邏輯 |
| test_index.py | ~12 | Index 解析與更新 |
| test_node.py | ~12 | Frontmatter 解析 |
| test_markers.py | 13 | 設計約束 7 marker |
| test_explore.py | ~10 | 鏈遍歷（含 circular reference 保護） |
| test_association.py | ~10 | Body 關鍵詞提取 + 語義聯想 |
| test_sediment.py | ~10 | 沈降邏輯 |
| test_chain_*.py | ~20 | Chain 欄位與鏈結維護 |
| test_muscle_memory.py | ~15 | Skill_ready 條件判定 |
| test_confirmation.py | ~15 | 確認事件 + maturation |
| 其他 (background, mcp, maintain 等) | ~40 | 整合測試 |

### 4.2 真實記憶池狀態

**`~/.hypermemory/pools/default/`**: 35 個 active node + `index.md` + `confirm/` 子目錄
- 日期範圍：2026-06-11 ~ 2026-06-21
- 節點類型組合：骨骼決策 (node_type=3)、經驗 (node_type=2)、設計文件
- 已建立鏈結：hypermemory-buildout 為核心 chain head（intensity=9, mentions=5），後繼 6 個 node

### 4.3 檢索表現分析

**Layer 1 (cluster 關鍵字)**:
- 命中率高度依賴 `index.md` 中 cluster 關鍵詞品質
- CJK substring 匹配對中文友善（「設計」→「設計哲學」）
- 對英文精確查詢可能過度寬鬆（任何包含 substring 的 cluster 都命中）
- threshold 0.3 是當前最佳實務值，但未經大規模 A/B 測試

**Layer 2 (鏈聯想)**:
- 鏈結品質決定效果；目前鏈結多靠 imprint 手動指定 `prenode`
- 缺乏自動鏈結推論（如 body 語義相似度建議）
- `resolve_chain_length()` 已實作且被 recall/think 管線使用，chain_boost 已在生產中

**Layer 3 (語義聯想)**:
- Body 關鍵詞提取對結構化 body 效果好
- 純 keyword-space（無 embedding）覆蓋有限
- 對純敘述性內容可能提取不足（短 body < 20 chars → 跳過）

### 4.4 邊界案例與極端狀況

**E1. 孤立節點（Orphan Node）** — 風險: 低
- prenode 指向不存在的檔案，或 nextnodes 中有 dangling reference
- `_read_node_metadata()` 拋 FileNotFoundError → graceful continue
- 但累積過多會產生 phantom entries in index

**E2. 覆蓋率權重分歧** — 風險: 低
- `index.py` `match_cluster()` 使用 `coverage * 0.3` (imprint 重複檢查用)
- `cluster.py` `find_all_clusters()` 使用 `coverage * 0.2` (recall 用)
- 僅影響 `_reflect()` 的覆蓋判斷靈敏度，不影響主要 recall 管線

**E3. 時間戳缺失** — 風險: 中
- Node 缺少 `timestamp` → `days=None` → recency=1.0（永遠不衰退）
- `_days_since()` 回傳 None → time_matured=0.5（永遠得不到完整分數）
- 雙重副作用：weight 偏高但 maturation 偏低

**E4. Chain 長度已正確計算** — ~~風險: 中~~ → **已修復 (v1.2.0)**
- v1.1.0: `chain_length` 預設為 1，呼叫方從未傳入實際值，chain_boost 永遠為 0
- **v1.2.0**: `resolve_chain_length()` 實作 + `HMTools._chain_length()` 整合 → recall/think/inspect/list 全部正確傳入 chain_length

**E5. Ref_by 僅標記不計分** — 風險: 低
- `ref_by_count` 在 calc_weight 呼叫中已正確傳入
- 但 ref_by 的增加僅靠手動編輯 frontmatter，無自動追蹤機制

**E6. DreamLoop 僅去重不跨 cluster 合併** — 風險: 中（規模化後）
- 多 cluster 可能高度重疊（如「hypermemory, mcp, debug」和「hypermemory, debug, testing」指向不同 node）
- 無自動合併 → cluster 持續膨脹 → 每次搜尋的 iteration 增加
- 對小 pool (< 100 nodes) 無影響，大 pool (> 500) 可能需優化

**E7. MCP 線性處理** — 風險: 低
- 單線程同步處理，MCP 協議本質 single-request-at-a-time
- `sys.stdin.buffer.read1(4096)` + line-by-line 處理

**E8. 語義聯想不自引用** — 風險: 無
- `associative_recall()` 中已正確過濾 source node

**E9. Ref_by 數值類型不一致** — 風險: 低
- `ref_by: null` (scalar null) vs `ref_by:` (empty list) vs `ref_by: []` (explicit empty)
- `fm.get("ref_by", []) or []` 安全取值，但 `null` 在 `_parse_list_field()` 中回傳 `[]`

**E10. 5M1E 維度過濾未整合進 recall 管線** — 風險: 高（架構 gap）
- `is_compatible()` 已實作但 recall/think 管線從未呼叫
- `find_all_clusters()` 回傳所有 cluster 匹配結果 → 直接進入 calc_weight/maturation
- **無環境維度硬濾波**发生在 main recall path 中

### 4.5 速度與記憶體隱憂

| 項目 | 評估 | 說明 |
|------|------|------|
| **index 解析** | O(n) | `parse_index()` 單次正則掃描，30 條目 ms 級 |
| **find_all_clusters** | O(n × m) | n=entries, m=query_kw × cluster_kw。n > 500 可能達數十 ms |
| **calc_weight** | O(1) | 純算術運算 |
| **associative_recall** | O(n × b × c) | n=entries, b=body_kw, c=cluster_kw。~2000 compares |
| **sediment 批次** | O(n × m) | n=nodes, m=index。硬碟 I/O 瓶頸：每 node 讀一次檔案 |
| **resolve_chain_length** | O(d) | d=max_depth=5，固定小常數。實際 ~2-5 次檔案讀取 |
| **記憶體** | < 50 MB | 無持久 memory，每次操作讀 index(~4KB) + node(~2KB each) |

### 4.6 設計取捨摘要

| 取捨 | 選擇 | 理由 |
|------|------|------|
| 索引結構 | Cluster → single node pointer | 避免多 node 排序，簡化查詢路徑 |
| 權重位置 | 不存於 index，執行時計算 | 避免 stale weight，支援動態公式迭代 |
| 語義聯想 | Pure keyword-space, no embedding | 零外部依賴，agent-agnostic |
| 節點刪除 | 不刪除原始檔案（sediment 歸檔） | 保留原始資料 |
| 連結方向 | Single parent, multi children | 類生物記憶的樹狀分支 |
| MCP 傳輸 | newline-delimited JSON | 相容 Python MCP SDK / Hermes MCP client |
| 檔案格式 | Markdown + YAML frontmatter | 人類可讀，支援 Obsidian Graph View |

### 4.7 當前已確認的代碼差距（未實作規格）

以下為 code review 已確認、spec 檔中明確定義但 code 中未實作的架構設計：

| 設計主旨 | 狀態 | 優先級 |
|---------|------|--------|
| 三層 Filter Layer 1（5M1E 環境維度硬濾波在 recall path 中） | code missing | 高 |
| 強制 Pre-Response Recall（認知協議植入 system prompt） | 行為規則未植入 | 高 |
| 服務邊界強制（Phase 2: 從 MEMORY 移除 pool 路徑） | 完全未開始 | 高 |
| Muscle Memory → Hermes SKILL 轉換（鏈斷在 .skill.json） | 鏈中斷 | 中 |
| DreamLoop 跨 cluster 語義發現 | 未實作 | 中 |
| Weight v2 relevance factor (TF-IDF body 語義層) | 從未進入程式碼 | 低 |
| Head Node 深度層級回傳（weight threshold → response depth） | 未實作 | 低 |
| Sediment/DreamLoop 整合 | 未整合 | 低 |

---

*本報告基於 HyperMemory v1.2.0 代碼庫（約 2026-06-22），引用真實原始碼與測試結果。所有常數與邏輯引用自實際檔案：weight.py, cluster.py, index.py, association.py, sediment.py, muscle_memory.py, maturation.py, dimensions.py, node.py, pool.py, explore.py, hm_tools.py, mcp_server.py。測試結果：207 passed, 0 failed。*
