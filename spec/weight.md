# HyperMemory：權重公式 v2 — 三因子動態權重

## 公式

```
weight = engagement × recency + solidification
```
| 因子 | 說明 |
|------|------|
| **engagement** | 參與度：intensity × (1 + 0.1 × mentions) + ref_by_boost + chain_boost |
| **recency** | 時效性：node_type-aware 半衰期模型，最近活躍則維持，超過半衰期開始指數衰減 |
| **solidification** | 固化基底：intensity × 0.05，永不衰減，確保高強度經驗永遠有基本 recall 機會 |

## Engagement 計算

```
engagement = intensity × (1 + 0.1 × total_mentions) + ref_by_count × 0.3 + max(0, chain_length - 1) × 0.2
```

| 變數 | 範圍 | 說明 |
|------|------|------|
| `intensity` | 1-10 | 寫入時設定的衝擊強度（不變） |
| `total_mentions` | 整數 | 被成功 recall 的次數，每次 +1（不變） |
| `ref_by_count` | 整數 | 被其他 node 引用的次數（from frontmatter ref_by） |
| `chain_length` | 整數 >= 1 | 所屬鏈的長度（包含自身），鏈頭 node 可獲得 chain_boost |

ref_by_boost = `ref_by_count × 0.3`（每次引用 +0.3）
chain_boost = `max(0, chain_length - 1) × 0.2`（每多一個鏈節點 +0.2）

## Recency 計算

半衰期模型：在 half_life 天數內維持 full score，超過後開始指數衰減。

```
if days_since_last_hit < half_life:
    recency = 1.0
else:
    excess = days_since_last_hit - half_life
    recency = max(0.05, exp(-excess / half_life))
```

### Node type 半衰期對照

| node_type | half_life | 行為 |
|-----------|-----------|------|
| 經驗 | 30 天 | 一般經驗，一個月無 recall 開始衰退 |
| 決策 | 30 天 | 同經驗，一個月 |
| 骨骼 | 90 天 | 骨骼級知識，三個月無 recall 才開始衰退 |
| 方法 | 30 天 | 同經驗 |
| 自動刻錄 | 7 天 | 自動產生的 node，一週無 recall 迅速衰退 |
| 其他 | 30 天（fallback）| 未知 type 用保守值 |

### 參數優先順序

1. `days_since_last_hit` 參數（caller 可傳入，代表最近活躍時間）
2. `timestamp_str` 參數（從 node 建立時間計算 days_since）
3. 兩者皆無 → recency = 1.0（無資訊時樂觀估）

## 函數簽名

```python
def calc_weight(
    intensity: int,
    total_mentions: int,
    timestamp_str: str | None = None,
    node_type: str = "經驗",
    ref_by_count: int = 0,
    chain_length: int = 1,
    days_since_last_hit: int | None = None,
) -> float:
```

所有新參數皆有預設值，舊呼叫方不需修改即可相容。

## 檔案變更

- `src/hypermemory/core/weight.py` — 核心公式改寫
- `src/hypermemory/mcp_server.py` — recall/think/inspect/list 傳入 node_type、ref_by_count
- `tests/test_weight_v2.py` — 27 個新測試（保留現有 test_weight.py 相容）

## 不做的範圍

- 不實作 body TF-IDF 關鍵詞向量（第二層 relevance）— 保留給後續迭代
- 不實作 chain boost 的鏈遍歷邏輯（由呼叫方提供 chain_length 參數）
- 不實作 dreamloop 負面因子（被建議合併但未被動作 → 降權）
- 不修改 cluster.py 的 keyword matching 邏輯

## 殘餘風險

- 新公式的 weight scale 與 v1 不同（engagement 加入 ref_by + chain，recency 改用半衰期），導致現有 index 的 cluster 指標可能重新指向不同 node（正常行為）
- 若呼叫方不傳 node_type，預設用「經驗」half_life=30 — 對「骨骼」node 偏保守
- chain_length 需要呼叫方從索引或鏈遍歷取得 — 單一 node 獨自呼叫時 chain_length=1（無加成）

## 驗收準則

- [ ] 全部 27 個新測試通過
- [ ] 現有 test_weight.py 的 8 個測試仍通過（或經過當調整）
- [ ] recall/think 回傳的 weight 欄位符合新公式
- [ ] MCP hm_inspect 顯示的 weight 更新
- [ ] 文件已更新至 spec/weight.md
