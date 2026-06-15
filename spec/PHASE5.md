# HyperMemory Phase 5 — 進化計畫

主軸：**經驗產生複利，從經驗累積到可信 skill**

---

## 核心設計問題

### 鏈遍歷：整鏈進 context vs AI 自主決定

**原則：鏈是索引，不是 payload。**

當 recall 命中一個 node 時，不應自動將整鏈資料塞入 context。HM 回傳的 metadata 應包含鏈的前後文指標（prenode/nextnodes），但由呼叫端（AI agent）決定是否追蹤。

**實作方式：**
- `hm_recall` 回傳結果含 `prenode` / `nextnodes` / `ref_by` 指標
- 新增 `hm_chain` tool：查詢 chain 上下游（給 node 名，往前/往後 N 步，回傳摘要）
- Agent 自行決定是否調用 `hm_chain` 追蹤 — 不自動注入

---

## 1. 權重演算法重構（Weight v2）

### 現狀問題

當前公式 `score = intensity × (1 + 0.1 × mentions) × decay(t)`：
- intensity 是人工給定（1-10），但缺乏 feedback 校正
- mentions 只增不減，舊 node 的 mentions 可能虛高
- decay 是線性，不能反映「近期突然活躍」的 pattern
- 鏈與權重沒有配套 — 鏈上的 node 不共享權重訊號

### 新權重模型：三因子動態權重

```
weight = relevance × engagement × recency
```

**relevance（語義相關性）**：取代關鍵字硬匹配
- 保留關鍵字匹配作為第一層 filter
- 加第二層：node body TF-IDF 關鍵詞向量（純文字、無 embedding 依賴）
- 當 recall 的 query 與 node body 共享高頻實詞時加分

**engagement（參與度）**：取代單純 mentions
- 不只計算 recall/think 命中次數
- 加入：ref_by 數量（被多少 node 引用）、被 inspect 次數、鏈長度加成（鏈越長代表持續有效）
- 負面因子：多次被 DreamLoop 建議合併但未被動作 → 降低權重

**recency（時效性）**：取代線性 decay
- 改用「最近活躍時間窗」：若 N 天內有命中，權重維持；若 N 天無命中，開始指數衰減
- 不同 node_type 有不同的半衰期：
  - `經驗`/`決策`：30 天無命中開始衰減
  - `骨骼`：90 天無命中開始衰減
  - `自動刻錄`：7 天無命中開始衰減

### 鏈與權重配套

**chain boost**：同鏈 node 共享流量訊號
- 當鏈上任一 node 被 recall 命中，整鏈 node 的 recency 都更新
- 鏈頭 node（prenode=None）有額外權重加成（gateway node effect）
- 鏈末 node（nextnodes=[]）若活躍度持續上升，表 chain 正在 grow → 整鏈權重加成

### 檔案變更

- `src/hypermemory/core/weight.py` — v2 權重公式
- `src/hypermemory/core/cluster.py` — 雙層匹配（關鍵字 + body TF-IDF）
- `src/hypermemory/commands/maintain.py` — recalc 改用新公式

---

## 2. Muscle Memory Loop（經驗 → Skill）

### 設計目標

經驗 node 累積到足夠可信度後，自動生成可重複使用的 skill。Skill 必須是**結構化、可執行**的，不是自然語言筆記。

### 轉換條件（AND）

| 條件 | 說明 |
|------|------|
| weight ≥ 門檻 | 權重持續高於 threshold 超過 N 天（eg. weight > 15 連續 30 天） |
| mentions ≥ 門檻 | 被 recall/think 命中 ≥ M 次（eg. 10 次） |
| ref_by ≥ 門檻 | 被其他 node 引用 ≥ K 次（eg. 3 次） |
| 鏈穩定 | 所屬 chain 在 N 天內無重大改寫 |

### 轉換流程

```
經驗 node (weight 夠高)
  → DreamLoop 標記為 "skill_ready"
  → hm daemon 定期執行 Muscle Memory Loop（每週 05:00）
  → 對每個 skill_ready node：
      1. 讀取 node body (完整經驗描述)
      2. 讀取整條 chain 上下文（prenode chain 到頭）
      3. 調用 LLM（透過 MCP tools/call 或外部）：
         Input: node body + chain context + frontmatter
         Output: structured skill template
      4. 產生 skill 檔案：
         - 存放在 ~/.hypermemory/skills/<node_name>.skill.json
         - 格式：{ trigger, steps, verification, source_node, chain_id, created_at }
      5. 在 node frontmatter 加註 skill 產出路徑
      6. 將原 node type 升級（選項）：經驗 → 方法
```

### Skill 格式

```json
{
  "skill_name": "debug-mcp-transport",
  "trigger": "MCP client timeout / transport error",
  "context_required": ["protocol format", "MCP SDK version"],
  "steps": [
    {"step": 1, "action": "check format", "description": "確認 server 用 newline JSON 非 Content-Length"},
    {"step": 2, "action": "check version", "description": "確認 protocolVersion 在 SDK 支援清單中"}
  ],
  "verification": "hm serve pipe test （subprocess + open stdin）",
  "source_node": "2026-06-15-mcp-debug.md",
  "chain_id": "mcp-fix-chain",
  "created_at": "2026-06-20T00:00:00Z",
  "weight_at_conversion": 18.5
}
```

### 痛點解決

你說「skill 想改就改，完全喪失功能，變成自然語言 script」：

- **skill 產出後不可直接編輯**（immutable by default），只能透過經驗 node 的累積產生新版本
- 若 agent 想修改 skill，必須先建立經驗 node 描述 why → 新 node 累積 weight → 自動產生 v2
- 權重門檻機制確保 skill 是「經驗共識」而非「單次判斷」

### 檔案變更

- 新增 `src/hypermemory/core/muscle_memory.py` — 轉換邏輯
- 新增 `~/.hypermemory/skills/` — skill 存放目錄
- 修改 `maintain.py` — 加入 muscle_memory loop
- 新增 MCP tool `hm_skill_list` / `hm_skill_inspect`

---

## 3. 聯想能力（Associative Recall）

### 現狀

`find_best_cluster` 只做關鍵字比對，命中一個 cluster 就停。沒有「看到 A 想到 B」的聯想機制。

### 設計：三層聯想

#### 第一層：直接命中（現有）
```
query ➜ cluster match ➜ node
```

#### 第二層：鏈聯想（新）
```
命中 node
  ➜ prenode（之前發生什麼）
  ➜ nextnodes（之後發生什麼）
  ➜ ref_by（誰引用了它）
```
回傳結果中包含這些附加指標，但不自動載入 body。

#### 第三層：語義聯想（新）
```
命中 node
  ➜ 從 body 提取高頻關鍵詞
  ➜ 用這些關鍵詞重新 query index
  ➜ 找出語義鄰近的 cluster
  ➜ 回傳「你可能也想看」的建議列表
```
語義聯想不需要 embedding 模型，只在 keyword space 中做關聯傳遞。

### MCP 增強

```python
hm_recall(keywords, associative=True)  
# associative=True 時多回傳一層 suggestions（第二層 + 第三層聯想）
```

### 檔案變更

- 修改 `src/hypermemory/core/cluster.py` — associative recall 邏輯
- 修改 `mcp_server.py` — hm_recall 擴充參數
- 新增 `src/hypermemory/core/association.py` — 語義聯想引擎

---

## 4. Head Node 向量擴散聯想

### 概念

Head node（prenode=None，chain 的起點）代表一個經驗主題的源頭。當命中 head node 時，需要擴散到同鏈的有效 node，但要有選擇性 — 不是整鏈 dump。

### 設計：鏈權重熱力圖

```python
head_node = find("2026-06-mcp-fix")
chain_nodes = traverse_chain(head_node, direction="forward")

# 對鏈上每個 node 打分：
for node in chain_nodes:
    score = node.weight * recency_boost
    if score > threshold:
        include_in_扩散结果
```

**擴散規則：**

| 條件 | 行為 |
|------|------|
| node weight > threshold T1 | 回傳 node title + summary |
| node weight > threshold T2 | 再加 20% body 開頭 |
| node weight > threshold T3 | 再加 ref_by 引用者 |
| node weight < 衰減線 | 不回傳，僅標記存在 |

### 效果

- 從 head node「看到」整條 chain 的有效 node
- 不自動載入全部，而是提供「摘要列表 + 權重排序」
- Agent 可以選擇性展開感興趣的 node

### MCP 增強

```python
hm_explore(node, depth=3, min_weight=5.0)
# 從 node 出發，往前後探索 depth 層
# 回傳 [node, weight, title, summary, direction]
```

### 檔案變更

- 新增 `src/hypermemory/core/explore.py` — 鏈探索引擎
- 新增 MCP tool `hm_explore`

---

## 5. 舊 Node 沈降（Background Data）

### 概念

「人機料法環量」= 5M1E，用於將舊 node 系統化分類並沈降為背景資料：
- **人**（Man）：使用者偏好、角色、溝通風格
- **機**（Machine）：環境設定、工具、平台
- **料**（Material）：專案、檔案、資料來源
- **法**（Method）：工作流程、SOP、設計決策
- **環**（Environment）：上下文、條件、限制
- **量**（Measurement）：指標、門檻、評價標準

### 設計：權重沈降管線

```
node weight < 衰減線（長期無命中）
  → DreamLoop 標記為 "cold"
  → Reflection Loop 分析 cold node body：
      1. 提取可結構化的資訊
      2. 依 5M1E 分類
      3. 寫入 ~/.hypermemory/background/<category>.json
  → 在 index 中標記為 archived（從 active cluster 移除但保留檔案）
```

### 背景資料格式

```json
// ~/.hypermemory/background/machine.json
{
  "category": "machine",
  "entries": [
    {
      "source": "2025-12-10-wsl-setup.md",
      "fact": "WSL Python toolchain: python3=3.11, uv installed, no pip module",
      "tags": ["env", "python", "wsl"],
      "archived_at": "2026-06-15",
      "original_weight": 2.3
    }
  ]
}
```

### 效果

- 不刪除老 node，保留追溯能力
- active pool 保持輕量（只保留高權重 node）
- 背景資料可在特定 query 下被 recall（eg. `recall "machine:wsl"` 查背景）
- pool_info 顯示 active vs archived 比例

### MCP 增強

```python
hm_recall("machine:wsl python")
# 前綴 category: 觸發背景資料查詢
```

---

## 實作優先級

| 優先 | 項目 | 依賴 | 估計 |
|------|------|------|------|
| P0 | Weight v2 + 鏈配套 | 無 | 2-3 天 |
| P1 | 聯想能力（第二層鏈聯想） | 無 | 1 天 |
| P1 | 舊 node 沈降管線 | Weight v2 | 2 天 |
| P2 | Head node 擴散（hm_explore） | 鏈聯想 | 1-2 天 |
| P3 | Muscle Memory Loop | 聯想 + 沈降 | 3-5 天 |
| P3 | 語義聯想（第三層） | Weight v2 | 2 天 |

---

## 附錄：你的問題回答

### Q: 鏈遍歷會否導致整鏈信息變上下文？該讓 AI 決定嗎？

**正確設計：HM 提供鏈指標（prenode/nextnodes/ref_by），AI 透過 `hm_explore` 或 `hm_chain` 選擇性追蹤。鏈是索引，不是 payload。**

目前 `hm_recall` 回傳已含 `prenode`/`nextnodes` — 已遵循此原則。新增 `hm_explore` 正式化這個模式。

### Q: HM 在市場上的潛力？

相較 Mem0（vector+KV）、Letta（tiered blocks）、Zep（temporal graph），HM 是目前唯一以**經驗鏈**為核心、具備**自我維護循環**、且能**產生可執行 skill** 的記憶系統。市場上尚無 direct competitor。
