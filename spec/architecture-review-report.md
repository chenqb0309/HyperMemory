# HyperMemory — 架構審查報告（Architecture Review Report）

**專案**: HyperMemory v1.2.0
**生成日期**: 2026-06-16
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

每個記憶節點是一個 Markdown 檔案（`YYYY-MM-DD-slug.md`），含 YAML frontmatter + Markdown body。

#### Frontmatter 欄位表

| 欄位 | 必填 | 類型 | 格式／範圍 | 說明 |
|------|------|------|-----------|------|
| `type` | 是 | str | `episodic_memory` (固定) | 節點類型識別 |
| `timestamp` | 是 | str (ISO 8601) | `2026-06-11T17:00:00+08:00` | 經驗發生時間 |
| `node_type` | 是 | int | 1 / 2 / 3 | 1=新經驗, 2=演化, 3=跨鏈合併 |
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
| `dimensions` | 否 | dict | `機: WSL` `料: Python 3.11` | 5M1E 環境維度 (巢狀 dict，見 1.2) |

#### Body 結構

```
# <Title>

## 關聯          ← 自動產生的雙軌鏈結鏡像（給人類觀看）
- 前驅：[[parent.md]]
- 後繼：[[child-a.md]]、[[child-b.md]]

## 正文 / 其他自訂區塊
...
```

規則：
- `prenode != null` → 生成「前驅」行
- `nextnodes` 非空 → 生成「後繼」行
- `ref_by` 非空 → 生成「參考來源」行
- 全部為空 → 整個 `## 關聯` 區塊省略
- frontmatter 中的 wikilink 是 AI 解析的 canonical source；body 中的關聯區塊是給人在 Obsidian Graph View 看的鏡像（雙軌設計）

#### Index 索引結構

索引檔 `index.md` 儲存 Cluster → Node 的對映關係，每行格式：

```
《cluster: [hypermemory, 記憶架構, 索引設計, ...]》 → [[2026-06-11-hypermemory-buildout.md]]
```

條目指向**鏈頭**節點（current node pointer）。當鏈中權重發生偏移時，`hm maintain recalc` 會重新計算鏈中所有節點的權重，並將 pointer 移到權重最高的節點。

檔案位置：`<pool>/index.md`

### 1.2 5M1E 維度系統

| 維度 | 英文 | 範例 |
|------|------|------|
| 人 | Man / Personnel | Jet |
| 機 | Machine / Equipment / OS | WSL, Windows |
| 料 | Material / Tech stack | Python 3.11, uv |
| 法 | Method / Workflow | uv-install, debug-by-assertion |
| 環 | Environment / Deployment | venv, container |
| 量 | Measurement / Metrics | latency=200ms |

匹配規則（`is_compatible()`）：
- Node 未指定某維度 → 相容（context-agnostic）
- Node 指定、context 未提供 → 相容
- 兩邊都有值 → 必須完全相等（不區分大小寫）
- 任一維度衝突 → 整筆 node 不相容（硬濾波，不扣分）

### 1.3 真實節點 JSON 範例

```json
{
  "filename": "2026-06-11-hypermemory-buildout.md",
  "frontmatter": {
    "type": "episodic_memory",
    "timestamp": "2026-06-11T17:00:00+08:00",
    "node_type": 3,
    "prenode": "2026-06-11-hypermemory-first-imprint.md",
    "nextnodes": [
      "2026-06-11-hm-vs-wiki-comparison.md",
      "2026-06-15-mcp-debug.md",
      "2026-06-16-hm-phase5.md"
    ],
    "ref_by": null,
    "intensity": 9,
    "total_mentions": 5,
    "tags": ["hypermemory", "milestone", "build-out"]
  },
  "title": "Hypermemory 完整建置歷程",
  "body": "從一次記憶 compact 需求出發，歷經一整天的設計討論與迭代實作，完成 Hypermemory 記憶放大器的完整建置。\n\n### 歷程\n1. 記憶 compact（91% → 54%）\n2. 人類記憶類比\n3. 架構設計\n4. 脫鉤通用化\n5. 更名 Hypermemory\n6. Phase 0-3 實作\n\n### 關鍵決策\n- Vault 為源，Runtime 為實作\n- 索引《cluster → node》不為 list，不比權重\n- 基底偏移時問使用者，不猜"
}
```

### 1.4 鏈結導航示意

```
[b: 2026-06-11-hypermemory-first-imprint.md]
  ↑ prenode
┌─────────────────────────────────────┐
│ 2026-06-11-hypermemory-buildout.md  │  ← pointer (最高權重)
│   intensity=9, mentions=5           │
└─────────────────────────────────────┘
  ↓ nextnodes (list)
  ├── 2026-06-11-hm-vs-wiki-comparison.md
  ├── 2026-06-15-mcp-debug.md
  ├── 2026-06-15-kanban-serial-preference.md
  ├── 2026-06-15-dotnet-build-env.md
  ├── 2026-06-15-crlf-contamination-wsl.md
  └── 2026-06-16-hm-phase5.md
```

---

## 2. 核心代碼實作邏輯

### 2.1 三層檢索管線

```
User Query (keywords)
       │
       ▼
┌──────────────────────────────────────────────────┐
│ Layer 1: Cluster 關鍵字粗篩 (cluster.py)          │
│  ┌─ query_lower vs cluster_lower                 │
│  ├─ CJK substring match (q in c OR c in q)       │
│  ├─ score = matched / len(query)                 │
│  └─ + coverage bonus (matched/cluster_size × 0.2)│
│  threshold = 0.3 (min_score)                     │
└──────────────────────┬───────────────────────────┘
                       ▼
┌──────────────────────────────────────────────────┐
│ Layer 2: 鏈聯想 (prenode/nextnodes/ref_by)        │
│  recall/think 回傳結果中內含：                    │
│  - prenode (upstream)                            │
│  - nextnodes (downstream)                        │
│  - ref_by (referenced by)                        │
│  AI agent 可以沿這些鏈結自行導航                   │
└──────────────────────┬───────────────────────────┘
                       ▼
┌──────────────────────────────────────────────────┐
│ Layer 3: 語義聯想 (association.py)               │
│  對 top-1 recall result 做二次查詢：              │
│  ┌─ 從 body 提取高頻實詞 (CJK 2-3字 + English)   │
│  ├─ 用這些詞重新 query index                     │
│  ├─ 回傳 suggestions (top_k=3)                  │
│  └─ 純 keyword-space，無 embedding/外部 API       │
└──────────────────────────────────────────────────┘
```

#### Layer 1 細則：Cluster 關鍵字粗篩

位於 `src/hypermemory/core/cluster.py`，函數 `find_all_clusters()`：

```
query_lower = [q.strip().lower() for q in query if q.strip()]
entry_lower = [k.strip().lower() for k in entry_keywords if k.strip()]

matched = 0
for q in query_lower:
    for c in entry_lower:
        if q in c or c in q:    # CJK substring: "設計" 命中了 "設計哲學"
            matched += 1
            break

score = matched / len(query_lower)
coverage = matched / len(entry_lower)
combined = score + coverage * 0.2    # 20% 覆蓋率獎勵
```

- 回傳所有 `combined >= min_score (0.3)` 的結果
- 按 `combined` 降冪排序
- 註：index.py 中的 `match_cluster()` 函數（遺留函數，今被 cluster.py 取代）使用不同的 coverage 權重 0.3

#### Layer 3 細則：Body 關鍵詞提取

位於 `src/hypermemory/core/association.py`，函數 `extract_body_keywords()`：

- CJK 處理：從 `[\u4e00-\u9fff]+` 片語提取所有 2-3 字子字串
  - 過濾全段在 STOPWORDS_CJK 中的 segment
  - 過濾首字為單字停止詞（的、了、是等）
- 英文處理：split → strip punctuation → lowercase → 過濾 stopwords + 長度 <= 2
- 合併：CJK 優先，去重保留順序，最多 8 個關鍵詞

停止詞集規模：CJK 約 50 個，英文約 100 個。

### 2.2 串行機制：pre/next 標籤導航

**資料結構**：frontmatter 中的 `prenode`（scalar wikilink）和 `nextnodes`（list wikilink）構成單向鏈結串列。

**AI 導航方式**：
1. `recall` / `think` 回傳結果中直接包含 `prenode`、`nextnodes`、`ref_by` 欄位
2. MCP tool `hm_explore` 提供 BFS 遍歷（支援 forward/backward/both，depth 控制，min_weight 過濾）
3. `hm_inspect` 單一節點檢視顯示完整鏈結關係

**鏈維護**：
- `hm imprint` 寫入新節點時，若指定 `prenode`，自動呼叫 `sync_parent_links()` 在父節點 frontmatter 中新增 `nextnodes` 條目
- `hm maintain recalc` 遍歷鏈中所有節點，將 index pointer 指向權重最高的節點

**重複拜訪保護**：explore 模組使用 `visited set` 防止 circular reference。

### 2.3 Maturation Score（經驗成熟度）

獨立的第二維度評分系統（與 weight 正交），公式：

```
maturation = base_intensity × confirmation_ratio × time_matured

confirmation_ratio = (positive + 1) / (positive + negative + 1)
  → 無事件 = 1.0（中性起步）
  → 正事件多 → 趨近 1.0
  → 負事件多 → 趨近 0.0

time_matured:
  >= 30 天 → 1.0
  >= 14 天 → 0.8
  <  14 天 → 0.5
```

- 確認事件 (confirmation event) 存於 `<pool>/confirm/` 子目錄
- 可選 5M1E 維度匹配過濾（越匹配的事件貢獻越高）
- `hm_confirm` MCP tool 供 agent 回報經驗驗證結果

### 2.4 維護循環（Maintenance Loop）

由 daemon 定時驅動，schedule：

| 時間 | 動作 | CLI 對應 |
|------|------|----------|
| 每天 23:00 | Reflection — 掃描 agent log，自動刻錄新經驗到 pool | `hm maintain reflect` |
| 每天 03:00 | Recalc — 全 pool 權重重算，重對齊 index pointer | `hm maintain recalc` |
| 每週日 04:00 | DreamLoop — index 關鍵字去重 + 孤立清理 | `hm maintain dreamloop` |
| 每週日 05:00 | Muscle — 掃描 skill_ready 條件，標記 candidates | `hm maintain muscle` |
| (非定時) | Sediment — weight < 2.0 + 存在 >= 14 天的 cold node 自動歸檔 | `hm maintain sediment` |

### 2.5 沈降管線（Sedimentation）

冷偵測條件：
- `weight < 2.0`（COLD_WEIGHT_THRESHOLD）
- `days_since >= 14`（MIN_NODE_AGE_DAYS）
- 有 timestamp

歸檔動作：
1. 從 `index.md` 移除條目
2. 追加到 `archive_index.md`
3. 依 5M1E 維度寫入 `<pool>/background/<維度>.json`
4. 原始 node 檔案保留（不移除）

### 2.6 肌肉記憶管線（Muscle Memory Loop）

skill_ready 條件（AND）：

```
weight >= 10.0
AND total_mentions >= 5
AND len(ref_by) >= 1
AND has_skill != True
AND node_type != 1（非自動刻錄）
```

- 符合條件的 node 自動標記 `skill_ready: true`
- 30 天未轉換 → 自動過期清除 `skill_ready` flag
- Agent 用 `hm_check_skill_candidates` 取出 → LLM 轉換 → `hm_register_skill` 註冊

### 2.7 MCP 通訊協定

- Transport：stdio + newline-delimited JSON（非 HTTP/SSE）
- 版本：MCP protocol 2024-11-05（echo client requested version）
- 12 個 tools：hm_list, hm_recall, hm_think, hm_inspect, hm_imprint, hm_confirm, hm_daemon_status, hm_pool_info, hm_maintain_now, hm_explore, hm_check_skill_candidates, hm_register_skill
- 依賴：std-only（`mcp` pip package 為 optional dependency）

---

## 3. 權重公式實戰參數

### 3.1 完整公式

```python
weight = engagement × recency + solidification

engagement = intensity × (1 + 0.1 × total_mentions)
           + ref_by_count × 0.3
           + max(0, chain_length - 1) × 0.2

recency = node_type-aware 半衰期指數模型

solidification = intensity × 0.05   # 永不衰減基底
```

### 3.2 所有常數一覽

| 常數 | 值 | 所在檔案 | 說明 |
|------|-----|---------|------|
| `mentions_multiplier` | **0.1** | weight.py L58 | 每次 mention 增加 10% 的 intensity 基數 |
| `ref_by_boost` | **0.3** | weight.py L59 | 每次被引用加 0.3 |
| `chain_boost` | **0.2** | weight.py L60 | 鏈長度每多 1 節點加 0.2（僅 chain_len > 1） |
| `solidification_rate` | **0.05** | weight.py L62 | intensity × 5% = 永不衰減基底 |
| `recency_floor` | **0.05** | weight.py L84 | recency 最小值下限（不會衰減到 0） |
| `half_life_經驗` | **30 天** | weight.py L15 | 一般經驗半衰期 |
| `half_life_決策` | **30 天** | weight.py L16 | 決策同經驗 |
| `half_life_骨骼` | **90 天** | weight.py L17 | 骨骼級知識半衰期最長 |
| `half_life_方法` | **30 天** | weight.py L18 | 方法同經驗 |
| `half_life_自動刻錄` | **7 天** | weight.py L19 | 自動產生的 node 最短半衰期 |
| `default_half_life` | **30 天** | weight.py L21 | fallback 值 |

### 3.3 衰減模型細則

```
if days < half_life:
    recency = 1.0                          # 半衰期內全額
else:
    excess = days - half_life
    recency = max(0.05, exp(-excess / half_life))  # 指數衰減，下限 0.05
```

- 參數優先順序：`days_since_last_hit` > `timestamp_str` > 無參數 → recency=1.0（樂觀估計）

### 3.4 數值範例

**情境 A：高活躍核心節點**
- intensity=9, mentions=5, ref_by=0, chain_length=7, 剛建立
- engagement = 9 × (1 + 0.5) + 0 + 1.2 = 9×1.5 + 1.2 = 14.7
- recency = 1.0（半衰期內）
- solidification = 9 × 0.05 = 0.45
- weight = 14.7 × 1.0 + 0.45 = **15.15**

**情境 B：冷 node（30 天無 recall）**
- intensity=5, mentions=1, node_type=經驗, days=60
- engagement = 5 × (1 + 0.1) = 5.5
- excess = 60 - 30 = 30, recency = exp(-30/30) = 0.3679
- solidification = 5 × 0.05 = 0.25
- weight = 5.5 × 0.3679 + 0.25 = **2.27**

**情境 C：自動刻錄快速衰退**
- intensity=3, mentions=0, node_type=自動刻錄, days=21
- engagement = 3 × 1.0 = 3.0
- excess = 21 - 7 = 14, recency = exp(-14/7) = 0.1353
- solidification = 3 × 0.05 = 0.15
- weight = 3.0 × 0.1353 + 0.15 = **0.56**（低於沈降門檻 2.0）

### 3.5 沈降與肌肉記憶門檻常數

| 常數 | 值 | 所在檔案 | 說明 |
|------|-----|---------|------|
| `COLD_WEIGHT_THRESHOLD` | **2.0** | sediment.py L15 | 低於此 weight 的 cold 候選 |
| `MIN_NODE_AGE_DAYS` | **14** | sediment.py L16 | 至少存在天數 |
| `MIN_SKILL_WEIGHT` | **10.0** | muscle_memory.py L22 | skill 候選最低權重 |
| `MIN_SKILL_MENTIONS` | **5** | muscle_memory.py L23 | skill 候選最低 mentions |
| `MIN_SKILL_REF_BY` | **1** | muscle_memory.py L24 | skill 候選最低 ref_by |
| `SKILL_READY_EXPIRE_DAYS` | **30** | muscle_memory.py L21 | skill_ready 過期天數 |
| `CLUSTER_THRESHOLD` | **0.3** | recall.py/think.py L40/L34 | 第一層 cluster 匹配最低分 |
| `ASSOCIATION_TOP_K` | **3** | association.py L158 | 語義聯想回傳上限 |
| `BODY_KEYWORDS_MAX` | **8** | association.py L117 | body 關鍵詞提取上限 |

---

## 4. 運作效果與瓶頸

### 4.1 目前運行狀態

基於代碼閱讀與真實記憶池（約 30 個 active node）的分析：

**檢索表現**：
- Layer 1 (cluster 關鍵字)：命中率高度依賴 `index.md` 中 cluster 關鍵詞的品質。CJK substring 匹配對中文查詢友善（「設計」→「設計哲學」），但對英文精確查詢可能過度寬鬆。
- Layer 2 (鏈聯想)：效果由鏈結品質決定。鏈結目前靠 imprint 時手動指定 `prenode` 來建立，缺乏自動鏈結推論。
- Layer 3 (語義聯想)：body 關鍵詞提取對結構化 body 效果好，但對純敘述性內容可能提取不足。純 keyword-space 處理無 embedding 支援，語義覆蓋有限。

**權重系統**：
- v2 公式已穩定運行，solidification 基底確保高 intensity node 永不沈降至 0。
- recalc 維護每月執行，能自動重對齊 index pointer 到鏈中權重最高的 node。

**維護循環**：
- daemon 自動排程運作正常（PID file + SIGTERM 優雅關閉）
- sediment 已能正確歸檔 cold node
- muscle memory 已能掃描 skill_ready 候選

### 4.2 邊界案例與極端狀況

以下為經 code review 識別的 edge case：

**E1. 孤立節點（Orphan Node）**
- 情境：prenode 指向不存在的檔案，或 nextnodes list 中有 dangling reference
- 後果：explore BFS 會跳過（`_read_node_metadata` 拋出 FileNotFoundError → continue），對 recall/think 無直接影響
- 風險：低 — graceful skip，但累積過多會產生 phantom entries in index

**E2. 版本差異的 Coverage 權重分歧**
- 情境：`index.py` 的 `match_cluster()` 使用 `coverage * 0.3`，而 `cluster.py` 的 `find_all_clusters()` 使用 `coverage * 0.2`
- 後果：`match_cluster()` 現僅用於 `_reflect()` 中的 cluster 比對（避免重複刻錄），不影響主要 recall 管線。但兩處邏輯不一致可能導致 `reflect` 與 `recall` 的覆蓋判斷標準不同。
- 風險：低 — 僅影響自動刻錄的靈敏度

**E3. 時間戳缺失**
- 情境：node 缺少 `timestamp` frontmatter
- 後果：`calc_weight()` 判定 `days=None` → recency=1.0（樂觀估計）。`_days_since()` 回傳 None → time_matured=0.5。
- 風險：中 — 缺少時間戳的 node 永遠不會衰退，也永遠得不到完整的 time_matured 分數

**E4. 鏈長度無自動計算**
- 情境：`chain_length` 參數在 calc_weight 中預設為 1，但呼叫方（recall/think/inspect）從未傳入實際鏈長度
- 後果：`chain_boost = max(0, chain_length - 1) × 0.2` 永遠為 0
- 風險：中 — 設計了 chain boost 但因沒有自動鏈長遍歷而無法生效。recalc 維護遍歷鏈時也未計算 chain_length。

**E5. Ref_by 僅標記不計分**
- 情境：`ref_by_count` 在 MCP tools 層（`hm_tools.py`）的 `calc_weight()` 呼叫中已傳入正確值
- 後果：**正常運作** — ref_by 加分已生效
- 注意：但 ref_by 的增加僅靠手動編輯 frontmatter；沒有自動追蹤 ref_by 變化的機制

**E6. DreamLoop 僅去重不跨 cluster 合併**
- 情境：多個 cluster 可能包含高度重疊的關鍵詞集（例如「hypermemory, mcp, debug」和「hypermemory, debug, testing」指向不同 node）
- 後果：無自動合併。cluster 會持續膨脹，影響 `find_all_clusters()` 的搜尋效率
- 風險：低 — 對小規模 pool (< 100 nodes) 無影響，但 scale 到大 pool 時可能增加每趟匹配的計算量

**E7. MCP 線性處理瓶頸**
- 情境：`mcp_server.py` 使用 `sys.stdin.buffer.read1(4096)` + line-by-line 處理
- 後果：收到完整 request 後同步處理，無並行控制。多個 request 在單線程中排隊
- 風險：低 — MCP 協議本質上是 single-request-at-a-time

**E8. 語義聯想可能回傳自身**
- 情境：`associative_recall()` 在 Layer 3 中已正確過濾 `source node`（`matches = [m for m in matches if m["node"] != source_node]`）
- 後果：**無問題** — self-reference 已排除

**E9. Ref_by 數值類型不一致**
- 情境：frontmatter 中 `ref_by: null`（scalar null） vs `ref_by:`（list 但無內容） vs `ref_by: []`（空 list）
- 後果：`fm.get("ref_by", []) or []` 用於安全取值，但 `null` 在 `_parse_list_field()` 中回傳 `[]`，應可正確處理
- 風險：低 — 但 parser 的 null 處理依賴正則表達式，e.g. `ref_by:` 無值可能被解析為空字串而非 `None`

### 4.3 速度與記憶體隱憂

| 項目 | 評估 | 說明 |
|------|------|------|
| **index 解析** | O(n) | `parse_index()` 使用單次正則掃描，對 30 條目毫秒級。O(n) 當 n 持續增長。 |
| **find_all_clusters** | O(n × m) | n=index entries, m=query_keywords × cluster_keywords。雙層巢狀迴圈 + substring match。安全，但 n > 500 時可能達數十 ms。 |
| **calc_weight** | O(1) | 純算術運算，無疑慮。 |
| **associative_recall** | O(n × b × c) | n=index entries, b=body keywords, c=cluster keywords。標準差約 8 × 50 × 5 = 2000 compares。安全。 |
| **sediment 批次掃描** | O(n × m) | n=nodes, m=index entries。硬碟 I/O 主要瓶頸（每個 node 讀一次檔案）。n > 1000 可能需 100+ ms。 |
| **記憶體** | < 50 MB | 所有 node metadata 在 memory 中不持久化。每次操作讀取 index.md（~4KB）+ 命中 node（~2KB each）。 |

### 4.4 設計取捨摘要

| 取捨 | 選擇 | 理由 |
|------|------|------|
| 索引結構 | Cluster → single node pointer | 避免多 node 排序，簡化查詢路徑 |
| 權重位置 | 不存於 index，執行時計算 | 避免 stale weight，支援動態公式迭代 |
| 語義聯想 | Pure keyword-space, no embedding | 零外部依賴，保持 agent-agnostic 原則 |
| 節點刪除 | 不刪除原始檔案（sediment 歸檔） | 保留原始資料，僅從 active index 移除 |
| 連結方向 | Single parent (prenode), multi children (nextnodes) | 類生物記憶的樹狀分支結構 |
| MCP 傳輸 | newline-delimited JSON | 相容 Python MCP SDK / Hermes MCP client |

---

*本報告基於 HyperMemory v1.2.0 代碼庫（commit 約 2026-06-16）生成。所有常數與邏輯引用自：weight.py, cluster.py, index.py, association.py, sediment.py, muscle_memory.py, maturation.py, dimensions.py, node.py, mcp_server.py。*
