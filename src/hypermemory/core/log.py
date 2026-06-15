"""HyperMemory 核心 — Session Log"""

import os
import json
from datetime import datetime, timezone
from pathlib import Path

LOG_DIR = Path.home() / ".hypermemory" / "log"


def ensure_log_dir():
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def today_path():
    return LOG_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.jsonl"


def capture(text, tags=None, source="manual"):
    """記錄一筆 session entry 到 log。
    
    text:   對話摘要或經驗描述
    tags:   選擇性關鍵字列表
    source: 來源（manual / mcp / reflection）
    """
    ensure_log_dir()
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "content": text.strip(),
        "tags": tags or [],
    }
    with open(today_path(), "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def recent(days=7):
    """讀取最近 N 天的 log entries，回傳 list of dict"""
    ensure_log_dir()
    entries = []

    from datetime import timedelta
    cutoff = datetime.now() - timedelta(days=days)

    for log_file in sorted(LOG_DIR.glob("*.jsonl"), reverse=True):
        date_str = log_file.stem  # YYYY-MM-DD
        try:
            file_date = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            continue
        if file_date < cutoff:
            break  # files are sorted reverse, so we can stop early

        with open(log_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

    return entries


def stats(days=7):
    """回傳最近 N 天的 log 統計"""
    entries = recent(days)
    return {
        "total_entries": len(entries),
        "days_covered": min(days, len(set(e.get("timestamp", "")[:10] for e in entries if e.get("timestamp")))),
        "sources": {},
    }
