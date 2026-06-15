# Maturation v2：兩軸分離的事實確認累積系統

> 前置規格：`spec/PHASE5.md`（方向 1：權重 v2）
> 對應 HM node：`2026-06-16-maturation-v2-design.md`

---

## 1. 為何需要 Maturation v2

### 1.1 舊設計的問題

現行 weight 系統（v1）：

```
weight = intensity × (1 + 0.1 × total_mentions) × stability_factor
```

| 問題 | 具體表現 |
|------|---------|
| AI 靜態賦值主導 | intensity（6-10）遠超 mentions（0-2x），weight 基本上由刻錄時決定 |
| 新 node 被淹沒 | 同 cluster 老的高 intensity node 每次 recall 排最前 |
| 缺乏事實校驗 | weight 從未被真實執行結果修正 |
| 無維度感知 | Windows 經驗在 Linux 場景出現但無過濾機制 |

### 1.2 Jet 的 paradigm 挑戰

> 「是否指標應該最優先指向新節點，然後再回憶有需要的記憶，而不是最開始設計的最重的記憶」

> 「這樣 weight 實際上就是按照 AI 當時刻錄給定的重量為准了對嗎，這樣如何累積到變成肌肉記憶的積分需要好好設計」

> 「事實會糾偏，假設每次的經驗調動都經過事實驗證，那是否事實會給出正反饋，這樣就可以獲得 confirm 積分」

> 「在這之前要確認過往 node 被 head node 擴散的有效性，並且按照維度匹配性（人機料法環量）有適配性才可以評分」

結論：**retrieval 與 muscle memory 需要兩套獨立機制。**

---

## 2. 兩軸分離模型

```
┌─────────────────────────────────────────────────────┐
│                   HM Maturation v2                     │
├──────────────────────┬──────────────────────────────┤
│   Track A            │   Track B                      │
│   Retrieval Score    │   Maturation Score             │
│                      │                                │
│   用途：recall 排序   │   用途：muscle memory 門檻       │
│   排序：recency-first │   排序：maturation 值           │
│   因子：時間、cluster  │   因子：事實確認比例             │
│   AI 判斷：無         │   AI 判斷：base_intensity 起點  │
│   累積：無            │   累積：確認事件                 │
│   5M1E：Layer 1 過濾  │   5M1E：計分前提                 │
└──────────────────────┴──────────────────────────────┘
```

---

## 3. Track A：Retrieval Score

### 3.1 設計原則

- **recency-first 是預設**：同一 cluster 下最新 node 排最前
- cluster 關鍵字匹配決定屬於哪條鏈（既有 HM 機制）
- 鏈末端即預設入口點（符合 existing three-layer filter model）

### 3.2 排序邏輯

```python
def retrieval_sort(nodes, query):
    """
    1. 第一層 filter：5M1E 維度匹配（不匹配直接排除）
    2. 第二層：cluster 關鍵字匹配（既有機制）
    3. 第三層：recency 降序（最新 node 排最前）
    """
    matched = [n for n in nodes if dimensions_compatible(n, query)]
    clustered = cluster_match(matched, query.keywords)
    return sorted(clustered, key=lambda n: n.timestamp, reverse=True)
```

### 3.3 不在 Retrieval 中使用的因子

| 因子 | 不使用的原因 |
|------|-------------|
| intensity | AI 主觀判斷，不影響排序 |
| confirmation_ratio | 這是長期可靠度，不是短期相關性 |
| total_mentions | 僅在 tie-breaker 時使用 |

---

## 4. Track B：Maturation Score

### 4.1 核心公式

```
maturation = base_intensity × confirmation_ratio × time_matured

confirmation_ratio = (positive_events + 1) / (total_events_in_matched_context + 1)

total_events_in_matched_context = positive_events + negative_events

time_matured:
  1.0  → node 存在超過 30 天且 weight 穩定
  0.8  → node 存在超過 14 天
  0.5  → node 存在不足 14 天
```

### 4.2 base_intensity 語意變更

v1 的 `intensity` 是 weight 的主要決定因子。
v2 的 `base_intensity` **僅作為 maturation 的起點**，不再是排序因子：

| 值 | 語意 | Node 類型範例 |
|----|------|--------------|
| 10 | 架構性原則 | design philosophy, 三層 filter 模型 |
| 8-9 | 重要經驗 | buildout debug, MCP transport fix |
| 6-7 | 一般經驗 | 特定專案紀錄 |
| 4-5 | 參考資訊 | 技術筆記 |
| 1-3 | 暫存 | 未成熟的觀察 |

### 4.3 Confirmation Ratio 行為表

| 情境 | Positive | Negative | Ratio | 意義 |
|------|---------|---------|-------|------|
| 新 node，剛刻錄 | 0 | 0 | (0+1)/(0+1) = 1.0 | 中性起步 |
| 高度可靠的經驗 | 20 | 1 | 21/22 = 0.95 | 值得 skill 化 |
| 多數成功的經驗 | 10 | 3 | 11/14 = 0.79 | 接近門檻 |
| 明確爭議的經驗 | 5 | 5 | 6/11 = 0.55 | 不可靠，應標記 |
| 幾乎失效的經驗 | 1 | 10 | 2/12 = 0.17 | 應考慮淘汰 |
| 從未被 recall（無事件） | 0 | 0 | 1.0 | 維持起步值 |

### 4.4 Muscle Memory 門檻

```
skillify_candidate = (
    maturation >= 8.0
    AND time_matured >= 0.8      # 至少存在 14 天
    AND positive_ratio >= 0.7    # 70% 以上確認率
)
```

v1 對照：舊制用 `weight >= 8.0`，新制用 `maturation >= 8.0`。

---

## 5. 5M1E 維度匹配系統

### 5.1 Frontmatter 格式

每個 node 的 frontmatter 新增 `dimensions` 區塊：

```yaml
---
dimensions:
  機: Windows          # OS、硬體環境（可多值逗號分隔）
  料: .NET, C#         # 技術棧、語言
  法: MSBuild / CLI    # 方法論、流程
  環: Production       # 部署環境
  人: <可選>            # 適用對象
  量: <可選>            # 規模範圍
---
```

### 5.2 匹配規則

| 層級 | 行為 |
|------|------|
| 完全匹配 | 所有指定維度一致 → 通過 |
| 部分匹配 | 指定維度無衝突，未指定視為相容 → 通過 |
| 維度未指定 | 所有 dimensions 為空 → 視為 context-agnostic，通過 |
| **明確衝突** | 任一維度值衝突 → **整筆排除，不進計分階段** |

### 5.3 衝突定義

衝突的判斷原則是：**值不可相容時才算衝突**。

```
相容範例：
  機: Windows         vs 機: Windows       → 匹配
  機: Windows, Linux  vs 機: Windows       → 匹配（含蓋）
  機: (未指定)        vs 機: Windows       → 相容

衝突範例：
  機: Windows         vs 機: Linux         → 衝突（OS 不同且無交集）
  料: .NET            vs 料: Python        → 衝突（技術棧不同）
  環: Production      vs 環: Development   → 衝突（環境不同）
```

### 5.4 衝突時的處理

- 該 node **不出現在 recall 結果中**
- 不計 confirmation 分數（positive 或 negative 都不計）
- 這是 Jet 指定的關鍵規則：Windows 經驗在 Linux 環境被 recall 但失敗，**不應扣分**

---

## 6. 事實確認事件（Confirmation Event）

### 6.1 事件來源

確認事件不來自 AI 主觀判斷，而是來自**事實驗證**的結果：

| 事實來源 | 適用的 agent 情境 |
|---------|-----------------|
| Build 成功/失敗 | 開發 debug 經驗 |
| Test pass/fail | 測試相關經驗 |
| HTTP response（200/500） | API 或網路配置經驗 |
| 檔案操作結果 | 檔案系統相關經驗 |
| Process exit code | CLI/腳本相關經驗 |
| 使用者明確確認 | 無法自動驗證的經驗 |

### 6.2 事件記錄格式

確認事件本身是一個 evidential node：

```yaml
---
type: confirmation_event
timestamp: 2026-06-16T11:30:00+08:00
node_type: 4
ref_to: 2026-06-15-build-env-python.md    # 指向被確認的源 node
result: positive                           # positive | negative | neutral
context_summary: 在 Python 3.11 build 環境驗證成功
dimensions_snapshot:                       # 驗證時的 context 快照
  機: WSL
  料: Python 3.11
  法: uv install
  環: venv
---
```

### 6.3 事件聚合

daemon 定期（每日）聚合確認事件，更新源 node 的 confirmation_ratio：

```python
def recalc_maturation(pool):
    for node in pool.nodes:
        events = pool.get_ref_by(node.id, type="confirmation_event")
        positive = len([e for e in events if e.result == "positive"])
        negative = len([e for e in events if e.result == "negative"])
        total = positive + negative

        node.confirmation_ratio = (positive + 1) / (total + 1)
        node.maturation = node.base_intensity * node.confirmation_ratio * time_matured(node)
```

---

## 7. 三層 Filter 模型整合（更新版）

```python
def hm_recall(query):
    # Layer 1：環境匹配（5M1E dimensions filter）
    candidates = [n for n in all_nodes if dimensions_compatible(n, query)]

    # Layer 2：Cluster 關鍵字匹配（既有 HM 機制）
    chain = cluster_match(candidates, query.keywords)

    # Layer 3：鏈末端 = 最新 node（recency-first）
    head = sorted(chain, key=lambda n: n.timestamp, reverse=True)[0]
    return head  # 指向最新 node

def hm_think(query):
    # 同上，但回傳候選清單（recency 排序）
    candidates = [n for n in all_nodes if dimensions_compatible(n, query)]
    chain = cluster_match(candidates, query.keywords)
    return sorted(chain, key=lambda n: n.timestamp, reverse=True)
```

---

## 8. 狀態遷移圖

```
                     Node Created（imprint）
                          │
                          ▼
                  ┌─────────────────┐
                  │   New Node      │
                  │  maturation=1.0 │
                  │  confirmation=0 │
                  └────────┬────────┘
                           │ 被 recall + 事實驗證
                           ▼
              ┌──────────────────────────┐
              │  Accumulating            │
              │  confirmation_events     │
              │  maturation 浮動          │
              └────┬─────────────┬───────┘
                   │             │
           ratio<0.3    ratio>0.7 + time>14d
                   │             │
                   ▼             ▼
        ┌───────────┐   ┌───────────────┐
        │ Stale      │   │ Skill         │
        │ 5M1E 沈降  │   │ Candidate     │
        │ 或淘汰     │   │ Muscle Memory │
        └───────────┘   └───────────────┘
                              │ 人類確認
                              ▼
                        ┌──────────┐
                        │ SKILL.md │
                        └──────────┘
```

---

## 9. 實作優先級（Phase 5 細化）

| 優先級 | 項目 | 依賴 | 估算 |
|--------|------|------|------|
| P0 | dimensions frontmatter schema + parser | 無 | 1 天 |
| P0 | retrieval 改為 recency-first | P0 | 0.5 天 |
| P0 | 5M1E Layer 1 filter | P0 (dimensions) | 1 天 |
| P1 | confirmation_event node schema | P0 | 1 天 |
| P1 | daemon recalc_maturation 聚合 | P1 | 1 天 |
| P1 | maturation 公式實裝 | P1 | 1 天 |
| P2 | Muscle Memory 門檻改讀 maturation | P1 | 0.5 天 |
| P2 | 舊 node 5M1E 沈降（cold storage） | P1 | 2 天 |

---

## 10. 邊界條件與風險

| 情境 | 處理方式 |
|------|---------|
| 新 node 無任何確認事件 | maturation = base_intensity × 1.0（中性起步） |
| 多個維度同時衝突 | 任一衝突即整筆排除 |
| 維度值格式不一致 | 強制小寫 standardize，大小寫差異視為 match |
| 證據 node 指向不存在的源 node | 孤立證據，daemon 維護時清理 |
| Agent 惡意刷確認分 | 一次 recall 只計一次確認事件，daemon 去重 |
| 5M1E 維度遺漏未指定 | 視為相容（預設行為），不影響 recall |

---

## 11. 附錄：與現有系統的相容性

### 11.1 既有 node 遷移

- 所有既有 node 的 `dimensions` 預設為空 → Layer 1 filter 全數通過
- 既有的 `intensity` 值保留為 `base_intensity`（語意不變）
- 既有的 `total_mentions` 保留，但不直接用於 maturation（改用 confirmation 事件）
- 第一次 recalc 時，既有 node 的 confirmation_ratio = (0 + 1) / (0 + 1) = 1.0

### 11.2 Node type 擴充

| type | 名稱 | 說明 |
|------|------|------|
| 1 | episodic | 情節記憶（既有） |
| 2 | skill-chain | 技能鏈（既有） |
| 3 | design | 設計決策（既有） |
| **4** | **confirmation_event** | **事實確認事件（新增）** |
