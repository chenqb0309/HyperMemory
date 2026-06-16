# HyperMemory Node Imprint Guide — 給 AI Agent 的 Node 寫作規範

本文件說明如何撰寫高品質的經驗 node，讓 HM 的檢索與 skill 轉換達到最佳效果。**這是操作建議，不是系統強制。** AI agent 應在寫入前自行理解並遵循。

---

## 1. Frontmatter 重要欄位

```yaml
---
type: 2                          # 1=root, 2=evolution, 3=cross-chain
timestamp: 2026-06-15T10:00:00+08:00
node_type: 3                     # 1=自動刻錄, 2=決策/經驗, 3=骨骼
prenode: null                    # [[parent.md]] 或 null
nextnodes: null                  # [[child1.md]], [[child2.md]]
ref_by: null                     # [[referer.md]]
intensity: 7                     # 1-10，衝擊強度
total_mentions: 1
tags: [主題A, 主題B, 技術棧]      # 最多 5 個，與其他 node 共享
dimensions:
  機: WSL
  料: Python 3.12
  法: 實作步驟
---
```

| 欄位 | 重要性 | 建議 |
|------|--------|------|
| `intensity` | 高 | 1-10，重大成功/失敗給 8-10，一般經驗 3-5 |
| `tags` | 高 | 使用與其他 node **共享**的標籤，這是 cluster 聚合的依據 |
| `node_type` | 中 | 經驗用 2，骨骼級知識用 3，自動刻錄用 1 |
| `dimensions` | 中 | 記錄環境維度（WSL/Windows/Python/Ubuntu 等），用於 recall 過濾 |

---

## 2. Body 寫作建議

### 2.1 同義詞擴充（補償 TF-IDF 字面匹配）

HM 的語義聯想使用純關鍵詞比對（TF-IDF），不具備自然語意理解。這代表：

- node body 寫「心情沮喪」
- 但使用者說「我很難過」
- TF-IDF 算不出相關性

**建議：在 node body 開頭用一兩句帶入同義詞與相關用語。**

```
好的寫法：
這是有關 WSL Python 除錯的經驗（WSL = Windows Subsystem for Linux, 即 Linux 子系統）。
當 Python 虛擬環境（venv/virtualenv）在 WSL 中出現路徑問題時...

不好的寫法（太多代名詞）：
它出現了問題。我用了某個方法解決了。這個方法很好。
```

### 2.2 結構化 body

```
## 問題描述
一句話描述。

## 情境
環境、版本、依賴。

## 解法
步驟 1、2、3。

## 驗證
如何確認修好了。
```

### 2.3 長度建議

- 最少 50 字元（太短的 body 無法提取關鍵詞）
- 一般 200-500 字元
- 骨架級（node_type=3）可更長

---

## 3. 鏈結（Chain Linking）

### 何時設定 prenode / nextnodes

| 情境 | 行為 |
|------|------|
| 新經驗是舊經驗的後續 | 新 node 的 `prenode` 指向舊 node |
| 一個經驗產生多個後續分支 | 父 node 的 `nextnodes` 列出所有子 node |
| 跨 node 參考（不屬同一條鏈） | 用 `ref_by` 列表 |

HM 會自動從 frontmatter 產生 body 中的 `## 關聯` 區塊，不需手動維護。

---

## 4. Skill 轉換預備

當 node 累積足夠權重（weight >= 10 + mentions >= 5 + ref_by >= 1），daemon 會自動標記 `skill_ready: true`。你要做的：

1. 呼叫 `hm_check_skill_candidates()` 或從 `pending_skills` 計數察覺
2. 用已知的 LLM 將 node body + chain context 轉換為結構化 skill JSON
3. 透過 `hm_register_skill(skill_json)` 註冊

詳細 skill JSON 格式：

```json
{
  "skill_name": "debug-mcp-transport",
  "trigger": "MCP client timeout / transport error",
  "context_required": ["protocol format", "MCP SDK version"],
  "steps": [
    {"step": 1, "action": "check format", "description": "確認 newline JSON"}
  ],
  "verification": "hm serve pipe test",
  "source_node": "2026-06-15-mcp-debug.md"
}
```

---

## 5. 避免的反模式

| 反模式 | 問題 | 建議 |
|--------|------|------|
| body 只有一句話 | 無法提取關鍵詞，聯想失效 | 至少寫 2-3 句背景 |
| tags 全是獨有詞 | 不會與其他 node cluster 聚合 | tags 要與既有的 node 共享 |
| intensity 永遠給 5 | 無法區分重要經驗 | 真的重大給 8-10，平淡給 1-3 |
| 不設 prenode/nextnodes | 鏈無法形成 | 回想相關舊經驗並鏈結 |
