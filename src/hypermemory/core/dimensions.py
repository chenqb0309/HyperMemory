"""HyperMemory 核心 — 5M1E 維度匹配

5M1E = 人(Man)、機(Machine)、料(Material)、法(Method)、環(Environment)、量(Measurement)

每個經驗 node 可標註適用的維度值，recall 時根據當前 context 匹配。
衝突的維度值直接 filter 掉（不計分也不扣分），相容或未指定則通過。
"""

# 5M1E 維度清單
DIMENSION_KEYS = ["人", "機", "料", "法", "環", "量"]

# 維度 key → 英文說明
DIMENSION_LABELS = {
    "人": "Man / Personnel",
    "機": "Machine / Equipment / OS",
    "料": "Material / Tech stack",
    "法": "Method / Workflow",
    "環": "Environment / Deployment",
    "量": "Measurement / Metrics",
}


def parse_dimensions(frontmatter):
    """從 frontmatter dict 中提取 dimensions 子 dict。

    frontmatter 中的 dimensions 是巢狀 dict：
    ```yaml
    dimensions:
      機: WSL
      料: Python 3.11
      法: uv-install
    ```

    回傳 {key: value} dict，無 dimensions 或格式錯誤時回傳空 dict。
    """
    raw = frontmatter.get("dimensions", {})
    if not isinstance(raw, dict):
        return {}
    # 只保留已知維度 key，過濾掉不相關的 key
    return {k: str(v).strip() for k, v in raw.items() if k in DIMENSION_KEYS and v}


def dimensions_from_kwargs(**kwargs):
    """從 caller 提供的關鍵字參數建立 dimensions dict（用於 MCP/CLI 輸入）。"""
    return {k: str(v).strip() for k, v in kwargs.items() if k in DIMENSION_KEYS and v}


def is_compatible(node_dims, context_dims):
    """判斷 node 維度與當前 context 維度是否相容。

    - node 未指定某維度 → 相容（context-agnostic）
    - node 指定、context 未提供 → 相容（無從判斷衝突）
    - node 指定、context 也指定 → 必須完全相等才相容
    - 任一維度衝突 → 整筆 node 不相容

    回傳 (compatible: bool, reason: str|None)
    """
    if not node_dims:
        return True, None  # 無維度標註 = context-agnostic，全數通過

    for key in DIMENSION_KEYS:
        node_val = node_dims.get(key)
        ctx_val = context_dims.get(key)
        if node_val and ctx_val:
            # 兩邊都有值，必須相等
            if node_val.lower() != ctx_val.lower():
                return False, f"維度「{key}」衝突：node={node_val}, context={ctx_val}"

    return True, None


def format_dimensions(dims):
    """格式化 dimensions dict 為可讀字串。"""
    if not dims:
        return "(無維度標註)"
    parts = [f"{k}={v}" for k, v in dims.items()]
    return ", ".join(parts)


def merge_dimensions(*dim_dicts):
    """合併多個 dimensions dict，後者覆蓋前者（用於繼承情境）。"""
    result = {}
    for d in dim_dicts:
        result.update(d)
    return result


def dimension_overlap_score(node_dims, context_dims):
    """計算 node 與 context 的維度重疊分數（0.0 ~ 1.0）。

    用於多筆 node 符合條件時的排序加成，不是 filter。
    - 完全無重疊 → 0.5（仍相容，但 context 資訊不足）
    - 完全匹配 → 1.0
    - 部分匹配 → 比例
    """
    if not node_dims or not context_dims:
        return 0.5  # 資訊不足，給中性分數

    matched = 0
    total = 0
    for key in DIMENSION_KEYS:
        node_val = node_dims.get(key)
        ctx_val = context_dims.get(key)
        if node_val and ctx_val:
            total += 1
            if node_val.lower() == ctx_val.lower():
                matched += 1

    if total == 0:
        return 0.5
    return matched / total
