"""hm list — 列出所有 cluster 與當前 node"""

import sys
from pathlib import Path

from hypermemory.core.pool import resolve_pool, index_path
from hypermemory.core.index import parse_index
from hypermemory.core.weight import calc_weight, format_score
from hypermemory.core.node import parse_frontmatter, extract_title


def run(args):
    pool = resolve_pool(args.pool)
    idx_path = index_path(pool)

    if not idx_path.exists():
        print(f"Index not found: {idx_path}")
        sys.exit(1)

    with open(idx_path, encoding="utf-8") as f:
        entries = parse_index(f.read())

    if not entries:
        print("(empty index — no clusters)")
        return

    print(f"HyperMemory Pool: {pool}")
    print(f"Clusters: {len(entries)}")
    print()

    for keywords, node_file in entries:
        node_path = pool / node_file
        exists = node_path.exists()

        score_str = ""
        title_str = ""
        if exists:
            with open(node_path, encoding="utf-8") as f:
                content = f.read()
            fm = parse_frontmatter(content)
            title = extract_title(content)
            score = calc_weight(
                fm.get("intensity", 1),
                fm.get("total_mentions", 0),
                fm.get("timestamp"),
            )
            score_str = format_score(score)
            title_str = title
        else:
            title_str = "(file not found)"

        # Truncate long keyword lists
        kw_preview = ", ".join(keywords[:5])
        if len(keywords) > 5:
            kw_preview += f" ... (+{len(keywords)-5})"

        marker = "✓" if exists else "✗"
        print(f"  [{marker}] {kw_preview}")
        print(f"         → {node_file}  ({score_str})  {title_str[:60]}")
        print()
