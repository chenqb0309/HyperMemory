"""HyperMemory 測試 — 背景資料查詢（Background Recall）"""

import sys
import os
import json
import tempfile
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from hypermemory.core.sediment import recall_background


def _pool_with_background():
    """建立有背景資料的暫存池。"""
    tmp = Path(tempfile.mkdtemp(prefix="hm_test_bg_"))
    bg = tmp / "background"
    bg.mkdir()

    (bg / "機.json").write_text(json.dumps({
        "category": "機",
        "entries": [
            {
                "source": "2025-12-10-wsl-setup.md",
                "fact": "WSL Python toolchain with uv",
                "tags": ["wsl", "python", "uv"],
                "archived_at": "2026-06-16T00:00:00+00:00",
                "original_weight": 1.5,
            }
        ],
    }, ensure_ascii=False, indent=2))

    (bg / "料.json").write_text(json.dumps({
        "category": "料",
        "entries": [
            {
                "source": "2026-01-05-dotnet-version.md",
                "fact": ".NET 8 SDK required for project",
                "tags": ["dotnet", "sdk"],
                "archived_at": "2026-06-16T00:00:00+00:00",
                "original_weight": 2.1,
            }
        ],
    }, ensure_ascii=False, indent=2))

    (bg / "other.json").write_text(json.dumps({
        "category": "other",
        "entries": [
            {
                "source": "2026-03-01-note.md",
                "fact": "General note about daily workflow",
                "tags": ["general"],
                "archived_at": "2026-06-16T00:00:00+00:00",
                "original_weight": 0.8,
            }
        ],
    }, ensure_ascii=False, indent=2))

    return tmp


def test_background_recall_by_category():
    """按 category 查詢背景資料。"""
    pool = _pool_with_background()
    result = recall_background(pool, category="機")

    assert result["found"]
    assert len(result["entries"]) == 1
    assert result["entries"][0]["source"] == "2025-12-10-wsl-setup.md"
    assert result["category"] == "機"


def test_background_recall_all():
    """不指定 category → 回傳全部背景資料。"""
    pool = _pool_with_background()
    result = recall_background(pool)

    assert result["found"]
    # 機 + 料 + other = 3 entries
    assert len(result["entries"]) == 3
    assert len(result["categories"]) == 3


def test_background_recall_empty():
    """無背景資料 → found=False。"""
    tmp = Path(tempfile.mkdtemp(prefix="hm_test_bg_empty_"))
    result = recall_background(tmp)
    assert not result["found"]


def test_background_recall_nonexistent_category():
    """不存在的 category → found=False。"""
    pool = _pool_with_background()
    result = recall_background(pool, category="人")
    assert not result["found"]


def test_background_recall_by_tag():
    """按 tag 過濾背景條目。"""
    pool = _pool_with_background()
    result = recall_background(pool, tag="wsl")

    assert result["found"]
    assert len(result["entries"]) == 1
    assert result["entries"][0]["source"] == "2025-12-10-wsl-setup.md"


def test_background_recall_by_tag_no_match():
    """不存在的 tag → 空結果。"""
    pool = _pool_with_background()
    result = recall_background(pool, tag="nonexistent")
    assert not result["found"]


def test_background_recall_prefix_parsing():
    """解析 category: prefix 格式。"""
    pool = _pool_with_background()
    # 模擬 "機:wsl" 前綴
    result = recall_background(pool, category="機", tag="wsl")
    assert result["found"]
    assert len(result["entries"]) == 1
