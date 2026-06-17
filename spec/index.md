# HyperMemory：規格索引（Spec Index）

**定位**: 本文件是 `spec/` 目錄的總綱，提供所有規格文件的導航結構。
**閱讀建議**: 設計約束 → 審計報告 → 依需求深入各子目錄。

---

## 核心閱讀路徑

| 順序 | 文件 | 說明 |
|------|------|------|
| 1 | [design-constraints.md](design-constraints.md) | **設計約束** — 7 條不可協調的設計原則。所有 spec 與實作與此衝突時以此為準。讀 spec 的起點。 |
| 2 | [architecture-review-report.md](architecture-review-report.md) | **架構審查報告** — 當前的實作狀態、資料結構、權重公式常數、邊界案例與已知差距。外部架構師的評估基底。 |
| 3 | 依需求瀏覽下方子目錄 | |

---

## 設計規格（design/）

| 文件 | 狀態 | 說明 |
|------|------|------|
| [design/node-schema.md](design/node-schema.md) | done | Node 資料結構定義：frontmatter 欄位、body link 雙軌設計、memory marker 格式、節點命名規範 |
| [design/weight.md](design/weight.md) | done | 權重公式 v2：engagement × recency + solidification。半衰期模型與所有常數定義 |
| [design/maturation-v2.md](design/maturation-v2.md) | done | 經驗成熟度系統 v2：兩軸分離（Retrieval v.s. Accumulation），5M1E 維度過濾的 confirm 事件累積 |
| [design/memory-pool.md](design/memory-pool.md) | done | 記憶池目錄結構：index 格式、archive 機制、background 儲存 |

---

## 操作協議（protocols/）

| 文件 | 狀態 | 說明 |
|------|------|------|
| [protocols/imprint.md](protocols/imprint.md) | done | **刻錄協議** — 新 node 的寫入流程、鏈結同步、index 更新、marker 強制附加 |
| [protocols/flashback.md](protocols/flashback.md) | done | **回憶協議** — recall/think 的完整查詢管線、cluster 匹配、排序、total_mentions 更新規則 |
| [protocols/maintenance.md](protocols/maintenance.md) | done | **維護循環** — daemon 定時排程、recalc / dreamloop / sediment / muscle 各階段動作 |
| [protocols/imprint-guide.md](protocols/imprint-guide.md) | done | **Node 寫作規範** — 給 AI agent 的 node 結構指引、frontmatter 填寫最佳實務 |
| [protocols/cognitive-protocol.md](protocols/cognitive-protocol.md) | design | **認知協議** — agent 行為協定（非 HM 核心）。要求 agent 在回應前先查詢記憶。但此行為規則未在 HM 引擎中強制。 |
| [protocols/amplifier.md](protocols/amplifier.md) | design | **思考放大協定** — agent 行為協定（非 HM 核心）。三層認知流（Flashback → Amplifier → Imprint）的中間層設計方案。 |

> 備註：標註 `[design]` 的協議是設計意圖（agent 端的行為規範），尚未進入 HM 引擎的強制實作。

---

## 發展計畫（plans/）

| 文件 | 說明 |
|------|------|
| [plans/phase5.md](plans/phase5.md) | Phase 5 進化計畫：三因子動態權重、語義聯想層、5M1E 維度過濾、mentions 更新鏈化、深度層級 response shaping |
| [plans/roadmap.md](plans/roadmap.md) | 產品路線圖：v1 基礎回憶、v1.1 daemon + 維護循環、v1.2 成熟度 + marker + chain boost、Phase 5 進化、v2 Gbrain 整合 |

---

## 存檔（archived/）

| 文件 | 說明 |
|------|------|
| [archived/architecture.md](archived/architecture.md) | 舊版核心架構文件 — 保留歷史紀錄，當前實作以各子目錄的 spec 為準 |

---

## 目錄結構總覽

```
spec/
├── index.md                         ← 本文件（總綱）
├── design-constraints.md            ← 設計約束（binding ground truth）
├── architecture-review-report.md    ← 審計報告（當前狀態）
├── design/                          ← 設計規格
│   ├── node-schema.md
│   ├── weight.md
│   ├── maturation-v2.md
│   └── memory-pool.md
├── protocols/                       ← 操作協議
│   ├── imprint.md
│   ├── flashback.md
│   ├── cognitive-protocol.md
│   ├── amplifier.md
│   ├── maintenance.md
│   └── imprint-guide.md
├── plans/                           ← 發展計畫
│   ├── phase5.md
│   └── roadmap.md
└── archived/                        ← 存檔
    └── architecture.md
```

---

*維護原則：新增 spec 文件時，請放入對應子目錄並在本 index.md 加入鏈結。修改既有文件時，無需更新 index。移除文件時，請更新 index 並注明去向。*
