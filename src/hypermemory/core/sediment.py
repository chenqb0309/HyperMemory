"""HyperMemory 核心 — 舊 Node 沈降管線（Sedimentation）

冷偵測 → 歸檔 → 背景資料儲存
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from hypermemory.core.node import parse_frontmatter, extract_title
from hypermemory.core.index import parse_index
from hypermemory.core.weight import calc_weight

COLD_WEIGHT_THRESHOLD = 2.0    # 低於此 weight 的 node 為 cold 候選
MIN_NODE_AGE_DAYS = 14          # 至少存在 14 天才可歸檔
BACKGROUND_DIR = "background"   # 背景資料存放子目錄
ARCHIVE_INDEX = "archive_index.md"  # 歸檔索引檔名


def is_cold_node(fm: dict, weight: float) -> bool:
    """判斷 node 是否符合沈降條件。

    - weight > COLD_WEIGHT_THRESHOLD → False
    - 無 timestamp → False（保守）
    - 存在天數 < MIN_NODE_AGE_DAYS → False
    - 以上皆非 → True
    """
    if weight > COLD_WEIGHT_THRESHOLD:
        return False

    ts_str = fm.get("timestamp")
    if not ts_str:
        return False

    try:
        ts = datetime.fromisoformat(ts_str)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        days = (datetime.now(timezone.utc) - ts).days
    except (ValueError, TypeError):
        return False

    if days < MIN_NODE_AGE_DAYS:
        return False

    return True


def archive_node(pool: Path, node_name: str, fm: dict) -> dict:
    """將單一 node 歸檔。

    1. 從 index.md 中移除該 node 的條目
    2. 在 archive_index.md 中新增條目（格式同 index.md）
    3. 呼叫 write_background() 儲存背景資料
    4. 不刪除原始 node 檔案

    回傳 {"success": True, "node": node_name, "background_file": "機.json"}
    """
    idx_path = pool / "index.md"
    content = idx_path.read_text(encoding="utf-8")

    # Find the entry line for this node
    pattern = r'《cluster:\s*\[.*?\]》\s*→\s*\[\[' + re.escape(node_name) + r'\]\]'
    m = re.search(pattern, content)
    if not m:
        return {"success": False, "node": node_name, "error": "entry not found in index"}

    entry_line = m.group(0)

    # Remove from active index (line + trailing newline)
    new_content = content.replace(entry_line + "\n", "")
    if new_content == content:
        new_content = content.replace(entry_line, "")
    idx_path.write_text(new_content, encoding="utf-8")

    # Add to archive index
    archive_path = pool / ARCHIVE_INDEX
    if archive_path.exists():
        archive_text = archive_path.read_text(encoding="utf-8")
        archive_text += entry_line + "\n"
    else:
        archive_text = "# HyperMemory Pool Index (Archived)\n\n" + entry_line + "\n"
    archive_path.write_text(archive_text, encoding="utf-8")

    # Write background
    bg_file = write_background(pool, node_name, fm)

    return {"success": True, "node": node_name, "background_file": bg_file or ""}


def write_background(pool: Path, node_name: str, fm: dict) -> str | None:
    """將 cold node 的基本資訊寫入背景 JSON。

    依 5M1E 維度分類（若 node 有 dimensions 則用該維度假名當檔名；
    無維度則寫入 background/other.json）。

    回傳寫入的檔案名（如 "機.json"），無維度時回傳 "other.json"。
    若 JSON 已存在，附加 entries 條目（append），不覆蓋。
    """
    node_path = pool / node_name
    if not node_path.exists():
        return None

    content = node_path.read_text(encoding="utf-8")
    title = extract_title(content)

    # Determine categories from dimensions
    dimensions = fm.get("dimensions", {})
    if dimensions:
        categories = list(dimensions.keys())
    else:
        categories = ["other"]

    # Build entry
    entry = {
        "source": node_name,
        "fact": title,
        "tags": fm.get("tags", []),
        "archived_at": datetime.now(timezone.utc).isoformat(),
        "original_weight": calc_weight(
            fm.get("intensity", 1),
            fm.get("total_mentions", 0),
            fm.get("timestamp"),
            node_type=fm.get("node_type", "經驗"),
        ),
    }

    # Write to each category
    bg_dir = pool / BACKGROUND_DIR
    bg_dir.mkdir(parents=True, exist_ok=True)

    first_file = None
    for cat in categories:
        filename = f"{cat}.json"
        filepath = bg_dir / filename
        if first_file is None:
            first_file = filename

        if filepath.exists():
            data = json.loads(filepath.read_text(encoding="utf-8"))
        else:
            data = {"category": cat, "entries": []}

        data["entries"].append(entry)

        filepath.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    return first_file


def sediment_pool(pool: Path, dry_run: bool = False) -> dict:
    """掃描所有 active node，沈降 cold node。

    流程：
    1. 讀取 index.md 取得所有 active entries
    2. 對每個 entry 讀取 node → 解析 frontmatter → 計算 weight
    3. 若 is_cold_node() → 準備歸檔（dry_run 跳過實際寫入）
    4. 回傳統計

    注意：已經在 archive_index.md 中的 node 不要再歸檔第二次。
    """
    idx_path = pool / "index.md"
    if not idx_path.exists():
        return {"archived_count": 0, "archived": [], "candidates": 0}

    content = idx_path.read_text(encoding="utf-8")
    entries = parse_index(content)

    # Read archive index to avoid double-archiving
    archive_path = pool / ARCHIVE_INDEX
    archived_nodes = set()
    if archive_path.exists():
        archive_content = archive_path.read_text(encoding="utf-8")
        for m in re.finditer(r'→\s*\[\[(.+?)\]\]', archive_content):
            archived_nodes.add(m.group(1))

    archived = []
    candidate_count = 0

    for _keywords, node_name in entries:
        if node_name in archived_nodes:
            continue

        node_path = pool / node_name
        if not node_path.exists():
            continue

        node_content = node_path.read_text(encoding="utf-8")
        fm = parse_frontmatter(node_content)

        weight = calc_weight(
            fm.get("intensity", 1),
            fm.get("total_mentions", 0),
            None,  # engagement only — age check is in is_cold_node via fm["timestamp"]
            node_type=fm.get("node_type", "經驗"),
        )

        if not is_cold_node(fm, weight):
            continue

        candidate_count += 1

        if not dry_run:
            result = archive_node(pool, node_name, fm)
            if result["success"]:
                archived.append(node_name)

    return {
        "archived_count": len(archived),
        "archived": archived,
        "candidates": candidate_count,
    }
