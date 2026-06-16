"""HyperMemory 核心 — Muscle Memory Loop（經驗 → Skill）

經驗 node 累積到足夠 weight + mentions + ref_by 後，自動標記為
skill_ready。Agent 透過 MCP tool 取出候選項，轉換為結構化 skill，
註冊到技能庫。30 天未轉換則自動過期。
"""

import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

from hypermemory.core.node import parse_frontmatter, extract_title
from hypermemory.core.weight import calc_weight
from hypermemory.core.pool import list_nodes
from hypermemory.core.maturation import get_confirmation_stats, calc_maturation
from hypermemory.core.dimensions import parse_dimensions


# ─── 常數 ───────────────────────────────────────────────────

SKILL_DIR = "skills"                       # skills/ 子目錄
SKILL_READY_EXPIRE_DAYS = 30               # 未轉換過期天數
MIN_SKILL_WEIGHT = 10.0                    # 最低權重門檻（保留向下相容）
MIN_SKILL_MENTIONS = 5                     # 輔助門檻（最低 recall 次數）
MIN_SKILL_REF_BY = 1                       # 輔助門檻（最低引用數）
MIN_SKILL_MATURATION = 8.0                 # 主要門檻：最低 maturation score
MIN_TIME_MATURED = 0.8                     # 最低 time_matured 因子


# ─── 條件偵測 ───────────────────────────────────────────────


def is_skill_ready(fm: dict, weight: float, maturation_score: float | None = None) -> bool:
    """判斷 node 是否符合 skill_ready 條件（AND）：

    - 尚未有 skill（has_skill != True）
    - 不是自動刻錄（node_type != 1）
    - total_mentions >= MIN_SKILL_MENTIONS（輔助門檻）
    - ref_by 列表長度 >= MIN_SKILL_REF_BY（輔助門檻）
    - **主要門檻**：
        - 若 maturation_score 有提供：maturation_score >= MIN_SKILL_MATURATION
        - 若 maturation_score 未提供（None）：weight >= 15.0（向下相容）
    """
    if fm.get("has_skill") is True:
        return False

    node_type = fm.get("node_type")
    if node_type == 1:
        return False

    mentions = fm.get("total_mentions", 0)
    if isinstance(mentions, str):
        mentions = int(mentions) if mentions.isdigit() else 0
    if mentions < MIN_SKILL_MENTIONS:
        return False

    ref_by = fm.get("ref_by", []) or []
    if len(ref_by) < MIN_SKILL_REF_BY:
        return False

    if maturation_score is not None:
        # 主要門檻：maturation-based
        if maturation_score < MIN_SKILL_MATURATION:
            return False
    else:
        # Fallback：weight-based（向下相容）
        if weight < 15.0:
            return False

    return True


# ─── 標記 ───────────────────────────────────────────────────


def mark_skill_ready(pool: Path, node_name: str) -> dict:
    """在 node frontmatter 中加入：

      skill_ready: true
      skill_ready_at: <ISO timestamp>

    若已存在則不重複加入。
    回傳 {"success": True, "node": node_name}
    """
    node_path = pool / node_name
    if not node_path.exists():
        node_path = pool / f"{node_name}.md"
    if not node_path.exists():
        return {"success": False, "error": f"Node not found: {node_name}"}

    content = node_path.read_text(encoding="utf-8")
    fm = parse_frontmatter(content)

    # 檢查是否已標記
    if fm.get("skill_ready") is True:
        return {"success": True, "node": node_name, "already_marked": True}

    # skill_ready_at 記錄標記時間
    ready_at = datetime.now(timezone.utc).isoformat()

    # 在 frontmatter 中插入 skill_ready 行
    # 在 --- 結尾之前插入
    lines = content.split("\n")
    fm_end = -1
    # 找到第二個 --- (frontmatter 結尾)
    dash_count = 0
    for i, line in enumerate(lines):
        if line.strip() == "---":
            dash_count += 1
            if dash_count == 2:
                fm_end = i
                break

    if fm_end is None or fm_end < 0:
        return {"success": False, "error": "Invalid frontmatter"}

    # 在 frontmatter 末尾之前插入新行
    new_lines = lines[:fm_end] + [
        f"skill_ready: true",
        f"skill_ready_at: {ready_at}",
    ] + lines[fm_end:]

    node_path.write_text("\n".join(new_lines), encoding="utf-8")
    return {"success": True, "node": node_name}


# ─── 掃描 ───────────────────────────────────────────────────


def _read_node_fm(pool: Path, node_file: str) -> tuple[dict, str, str]:
    """讀取 node 檔案，回傳 (frontmatter dict, body_content, title)。"""
    node_path = pool / node_file
    if not node_path.exists():
        node_path = pool / f"{node_file}.md"
    if not node_path.exists():
        return {}, "", ""
    content = node_path.read_text(encoding="utf-8")
    fm = parse_frontmatter(content)
    title = extract_title(content)

    # 提取 body（frontmatter 之後的內容）
    body = ""
    fm_match = re.search(r'^---\s*\n.*?\n---', content, re.DOTALL)
    if fm_match:
        body = content[fm_match.end():].strip()

    return fm, body, title


def _get_status(fm: dict) -> str:
    """判斷 node 的 skill status: ready / converted / expired"""
    if fm.get("has_skill") is True:
        return "converted"
    if fm.get("skill_ready") is True:
        ready_at = fm.get("skill_ready_at")
        if ready_at:
            try:
                ts = datetime.fromisoformat(ready_at)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                now = datetime.now(timezone.utc)
                if (now - ts).days >= SKILL_READY_EXPIRE_DAYS:
                    return "expired"
            except (ValueError, TypeError):
                pass
        return "ready"
    return "not_ready"


def check_candidates(pool: Path) -> list[dict]:
    """掃描所有 node，回傳 skill_ready node 列表。

    每個 candidate：
    {
        "node": str,
        "title": str,
        "weight": float,
        "mentions": int,
        "ref_by": list[str],
        "body_preview": str,      # body 前 200 chars
        "status": "ready" | "converted" | "expired",
        "skill_ready_at": str | None,
    }
    """
    candidates = []
    for node_file in list_nodes(pool):
        node_file_name = node_file.name
        fm, body, title = _read_node_fm(pool, node_file_name)
        if not fm:
            continue

        status = _get_status(fm)
        if status == "not_ready":
            continue

        weight = calc_weight(
            fm.get("intensity", 1),
            fm.get("total_mentions", 0),
            fm.get("timestamp"),
            node_type=fm.get("node_type", "經驗"),
            ref_by_count=len(fm.get("ref_by", []) or []),
        )

        body_preview = body[:200].strip() if body else ""

        candidates.append({
            "node": node_file_name,
            "title": title,
            "weight": round(weight, 2),
            "mentions": fm.get("total_mentions", 0),
            "ref_by": fm.get("ref_by", []) or [],
            "body_preview": body_preview,
            "status": status,
            "skill_ready_at": fm.get("skill_ready_at"),
        })

    return candidates


# ─── 註冊 Skill ─────────────────────────────────────────────


def register_skill(pool: Path, skill: dict) -> dict:
    """註冊一個結構化 skill。

    skill JSON 格式（必要欄位）：
    {
        "skill_name": str,        # 必要
        "trigger": str,           # 必要
        "steps": list,            # 必要（至少 1 step）
        "source_node": str,       # 必要
        "context_required": list, # 選項
        "verification": str,      # 選項
    }

    寫入 ~/.hypermemory/pools/<pool>/skills/<source_node>.skill.json
    在 source node 的 frontmatter 加入：
      has_skill: true
      skill_path: skills/<source_node>.skill.json
    清除 skill_ready flag。

    回傳 {"success": True, "skill_path": str}
    """
    # 驗證必要欄位
    skill_name = skill.get("skill_name", "").strip()
    if not skill_name:
        return {"success": False, "error": "Missing required field: skill_name"}

    trigger = skill.get("trigger", "").strip()
    if not trigger:
        return {"success": False, "error": "Missing required field: trigger"}

    steps = skill.get("steps", [])
    if not steps or not isinstance(steps, list) or len(steps) < 1:
        return {"success": False, "error": "Missing required field: steps (min 1 step)"}

    source_node = skill.get("source_node", "").strip()
    if not source_node:
        return {"success": False, "error": "Missing required field: source_node"}

    # 確認 source node 存在
    node_path = pool / source_node
    if not node_path.exists():
        node_path = pool / f"{source_node}.md"
    if not node_path.exists():
        return {"success": False, "error": f"Source node not found: {source_node}"}

    # 確保 skills/ 目錄存在
    skill_dir = pool / SKILL_DIR
    skill_dir.mkdir(parents=True, exist_ok=True)

    # 寫入 skill JSON 檔案
    source_stem = source_node.replace(".md", "")
    skill_filename = f"{source_stem}.skill.json"
    skill_path = skill_dir / skill_filename

    with open(skill_path, "w", encoding="utf-8") as f:
        json.dump(skill, f, ensure_ascii=False, indent=2)

    # 更新 source node frontmatter
    content = node_path.read_text(encoding="utf-8")
    lines = content.split("\n")

    # 移除 skill_ready 行（保留 skill_ready_at 以供歷史參考，或也移除）
    # 找到 frontmatter 範圍
    dash_count = 0
    fm_start = -1
    fm_end = -1
    for i, line in enumerate(lines):
        if line.strip() == "---":
            if dash_count == 0:
                fm_start = i
            dash_count += 1
            if dash_count == 2:
                fm_end = i
                break

    if fm_end < 0:
        return {"success": False, "error": "Invalid frontmatter"}

    # 在 frontmatter 中：加入 has_skill, skill_path, 移除 skill_ready 系列行
    new_fm_lines = []
    in_skill_ready_block = False
    for line in lines[fm_start + 1:fm_end]:
        stripped = line.strip()
        # 跳過 skill_ready 相關行
        if stripped == "skill_ready: true" or stripped.startswith("skill_ready_at:"):
            continue
        new_fm_lines.append(line)

    # 加入新欄位
    new_fm_lines.append(f"has_skill: true")
    new_fm_lines.append(f"skill_path: {SKILL_DIR}/{skill_filename}")

    # 重組檔案
    new_lines = lines[:fm_start + 1] + new_fm_lines + lines[fm_end:]
    node_path.write_text("\n".join(new_lines), encoding="utf-8")

    return {
        "success": True,
        "skill_path": str(skill_path),
    }


# ─── 過期清除 ───────────────────────────────────────────────


def expire_stale_marks(pool: Path) -> list[str]:
    """掃描所有 skill_ready=true 的 node，若 skill_ready_at 超過
    SKILL_READY_EXPIRE_DAYS 則清除 skill_ready flag。
    回傳被清除的 node 列表。"""
    expired = []
    now = datetime.now(timezone.utc)

    for node_file in list_nodes(pool):
        node_file_name = node_file.name
        content = node_file.read_text(encoding="utf-8")
        fm = parse_frontmatter(content)

        if not fm.get("skill_ready"):
            continue

        ready_at = fm.get("skill_ready_at")
        node_ts = fm.get("timestamp")

        should_expire = False

        # Check primary: skill_ready_at
        if ready_at:
            try:
                ts = datetime.fromisoformat(ready_at)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if (now - ts).days >= SKILL_READY_EXPIRE_DAYS:
                    should_expire = True
            except (ValueError, TypeError):
                pass

        # Check secondary: node's own timestamp
        if not should_expire and node_ts:
            try:
                ts = datetime.fromisoformat(node_ts)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if (now - ts).days >= SKILL_READY_EXPIRE_DAYS:
                    should_expire = True
            except (ValueError, TypeError):
                pass

        if should_expire:
            # 移除 skill_ready: true 和 skill_ready_at 行
            lines = content.split("\n")
            new_lines = [
                line for line in lines
                if not line.strip().startswith("skill_ready:")
                and not line.strip().startswith("skill_ready_at:")
            ]
            node_file.write_text("\n".join(new_lines), encoding="utf-8")
            expired.append(node_file_name)

    return expired


# ─── Pending 計數 ───────────────────────────────────────────


def pending_skill_count(pool: Path) -> int:
    """統計當前 skill_ready=true 且在有效期限內的 node 數量
    （不包含 has_skill=true 和 expired 的）。"""
    count = 0
    now = datetime.now(timezone.utc)

    for node_file in list_nodes(pool):
        content = node_file.read_text(encoding="utf-8")
        fm = parse_frontmatter(content)

        if fm.get("has_skill") is True:
            continue
        if not fm.get("skill_ready"):
            continue

        ready_at = fm.get("skill_ready_at")
        if ready_at:
            try:
                ts = datetime.fromisoformat(ready_at)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if (now - ts).days >= SKILL_READY_EXPIRE_DAYS:
                    continue
            except (ValueError, TypeError):
                pass

        count += 1

    return count


# ─── 完整掃描 ───────────────────────────────────────────────


def scan_and_mark_candidates(pool: Path) -> dict:
    """完整掃描：掃描所有 active node → 計算 weight →
    檢查條件 → 標記符合者。

    用於 `hm maintain muscle` 和 daemon 掃描。

    回傳 {"marked": [node_names], "skipped": N, "expired": [node_names]}
    """
    marked = []
    skipped = 0
    expired = expire_stale_marks(pool)

    for node_file in list_nodes(pool):
        node_name = node_file.name
        content = node_file.read_text(encoding="utf-8")
        fm = parse_frontmatter(content)

        # 跳過已轉換或已標記的
        if fm.get("has_skill") is True:
            skipped += 1
            continue
        if fm.get("skill_ready") is True:
            skipped += 1
            continue

        weight = calc_weight(
            fm.get("intensity", 1),
            fm.get("total_mentions", 0),
            fm.get("timestamp"),
            node_type=fm.get("node_type", "經驗"),
            ref_by_count=len(fm.get("ref_by", []) or []),
        )

        # 計算 maturation score（主要門檻）
        stats = get_confirmation_stats(pool, node_name)
        node_dims = parse_dimensions(fm)
        mat = calc_maturation(
            fm.get("intensity", 1),
            stats["positive"],
            stats["negative"],
            fm.get("timestamp"),
            node_dims=node_dims,
        )
        maturation_score = mat["score"]

        if is_skill_ready(fm, weight, maturation_score=maturation_score):
            mark_skill_ready(pool, node_name)
            marked.append(node_name)
        else:
            skipped += 1

    return {
        "marked": marked,
        "skipped": skipped,
        "expired": expired,
    }
