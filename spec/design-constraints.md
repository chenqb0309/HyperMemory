# HyperMemory：設計約束（Design Constraints）

**版本**: 1.0
**建立日期**: 2026-06-17
**定位**: 本文件定義 HyperMemory 不可協調的設計原則。所有 spec、實作、測試若與以下約束衝突，應以本文件為準。

---

## 約束 1：Agent 優先的記憶外掛

HyperMemory 的主要使用者是 AI agent，不是人類。

| 面向 | 內容 |
|------|------|
| Why | agent 內建記憶（Memory.md）收容空間過小，無法承載長期經驗累積 |
| What | HyperMemory 是 agent 的外掛記憶空間，透過 MCP/stdin 介面存取 |
| 不做的 | 不設計為人類筆記工具（雖然人類可讀），不依賴 GUI |
| 驗收 | 任何 AI agent 接入 MCP 後即可 recall/imprint/confirm，不需人類介入 |

---

## 約束 2：記憶按主體形成鏈狀結構，經驗累積有複利

同一主題的經驗不應是散落的獨立節點，而是一條隨時間生長的鏈。

| 面向 | 內容 |
|------|------|
| Why | 線性經驗累積：每個新教訓基於舊教訓，鏈越長代表該主題越成熟 |
| What | Node 以 prenode → nextnodes 構成單向鏈，Type 1/2/3 支援推移與跨鏈聚合 |
| 不做的 | 不設計為純標籤分類系統（tag-only 無法表達經驗演化次序） |
| 驗收 | 同主題的經驗可追溯整條鏈；鏈越長、recall 優先級越高 |

---

## 約束 3：事實糾偏循環

經驗必須經過事實驗證才能提高可靠度，不可由 AI 主觀決定。

| 面向 | 內容 |
|------|------|
| Why | AI 刻錄時給的 intensity 是靜態的，只有真實執行結果（build pass/fail、test pass/fail、HTTP 200/500）才能糾偏 |
| What | 循環：recall → 實作 → confirmation event（positive/negative）→ maturation 更新 |
| 不做的 | 不允許無事實依據的權重調整，不允許 agent 自評 maturation |
| 驗收 | 每次事實驗證後 maturation 正確反映；multiple negative events 可讓經驗降級或淘汰 |

---

## 約束 4：場景參數影響經驗適用性

同一經驗在不同場景（OS、技術棧、環境）下成功率不同，系統必須感知這個差異。

| 面向 | 內容 |
|------|------|
| Why | Windows 上 debug MCP 的經驗，在 Linux 上不一定有效。不區分場景的 recall 會誤導 agent |
| What | 5M1E 維度系統（機料法環人量）標記每個經驗的適用場景；recall 時維度衝突的 node 直接排除 |
| 不做的 | 維度衝突不扣分、不懲罰，只是過濾。不做 embedding 語義場景比對 |
| 驗收 | 查詢帶 context_dims 時，維度衝突的 node 不會出現在 recall 結果中 |

---

## 約束 5：人腦記憶模型 — 用進廢退，長期有效經驗形成肌肉記憶

記憶系統應模擬人腦的遺忘曲線與技能自動化機制。

| 面向 | 內容 |
|------|------|
| Why | 近期活躍的經驗比久遠無 recall 的經驗更重要；反覆驗證有效的經驗應固化為可重複使用的 skill |
| What | 半衰期模型（經驗30d/骨骼90d/自動刻錄7d）；固化基底 solidification 永不歸零；weight+maturation 達門檻 → skill_ready |
| 不做的 | 不刪除舊 node（保留追溯能力），不讓 weight 歸零 |
| 驗收 | 高 intensity 的舊 node 即使衰減仍有基本 recall 機會；weight+maturation 達標的經驗可標記 skill_ready |

---

## 約束 6：可信任的經驗依據

最終目的是讓 agent 將 HyperMemory 作為每次處理事情的依據來源，提高人類對 AI 實作的信任度。

| 面向 | 內容 |
|------|------|
| Why | 沒有記憶的 agent 每次從零開始，人類無法信任其決策一致性 |
| What | MCP 讓任何 agent 接入；maturation 提供事實驗證的可靠度指標；認知協議（recall-first）確保 agent 不自作主張 |
| 不做的 | 不提供「AI 自信度」取代事實驗證，不偽造經驗 |
| 驗收 | agent 接入 HM 後，相同問題可回傳一致的、有經驗依據的回答；人類可檢視經驗鏈與 confirmation 紀錄 |
