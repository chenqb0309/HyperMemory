"""hm recall — 關鍵字匹配回憶（recency-first，最新在前）"""

import sys
import re
from datetime import datetime, timezone

from hypermemory.core.pool import resolve_pool, index_path
from hypermemory.core.index import parse_index
from hypermemory.core.cluster import find_all_clusters
from hypermemory.core.node import parse_frontmatter, extract_title
from hypermemory.core.weight import calc_weight
from hypermemory.core.dimensions import parse_dimensions
from hypermemory.core.maturation import get_confirmation_stats, calc_maturation


def run(args):
    pool = resolve_pool(args.pool)
    idx_path = index_path(pool)

    if not idx_path.exists():
        print(f"Index not found: {idx_path}")
        sys.exit(1)

    with open(idx_path, encoding="utf-8") as f:
        entries = parse_index(f.read())

    if not entries:
        print("(empty index)")
        return

    # Parse query keywords
    query = args.keywords
    if not query:
        print("No keywords provided.")
        return

    kw_list = [k.strip() for k in query.split(",") if k.strip()]

    # Find ALL matching clusters
    matches = find_all_clusters(kw_list, entries, min_score=0.3)

    if not matches:
        print(f"No matching memory found for: {' '.join(kw_list)}")
        return

    # Read all matched nodes, collect with timestamps
    nodes = []
    for m in matches:
        node_file = m["node"]
        node_path = pool / node_file
        if not node_path.exists():
            continue
        with open(node_path, encoding="utf-8") as f:
            content = f.read()

        fm = parse_frontmatter(content)
        ts = fm.get("timestamp", "0000")
        title = extract_title(content)
        weight = calc_weight(
            fm.get("intensity", 1),
            fm.get("total_mentions", 0),
            fm.get("timestamp"),
        )

        nodes.append({
            "node": node_file,
            "title": title,
            "type": fm.get("node_type", "?"),
            "intensity": fm.get("intensity", "?"),
            "weight": round(weight, 2),
            "timestamp": ts or "0000",
            "tags": fm.get("tags", []),
            "cluster_score": m["score"],
        })

    # Sort by timestamp descending (newest first)
    nodes.sort(key=lambda n: n["timestamp"], reverse=True)

    # Display results
    for i, n in enumerate(nodes):
        ts_display = n["timestamp"][:10] if n["timestamp"] != "0000" else "(no date)"
        tags_str = ", ".join(n["tags"][:3]) if n["tags"] else ""
        print(f"{i+1}. {n['title']}")
        print(f"   Node: {n['node']}")
        print(f"   Type: T{n['type']}  Intensity: {n['intensity']}  "
              f"Weight: {n['weight']}  Date: {ts_display}")
        if tags_str:
            print(f"   Tags: {tags_str}")
        print()

    # Update total_mentions for the top result
    if not args.dry_run and nodes:
        top = nodes[0]
        top_path = pool / top["node"]
        with open(top_path, encoding="utf-8") as f:
            content = f.read()
        fm = parse_frontmatter(content)
        mention_tag = fm.get("total_mentions", 0)
        if isinstance(mention_tag, int):
            mention_tag += 1
        else:
            mention_tag = 1
        new_content = re.sub(
            r"(total_mentions:\s*)\d+",
            rf"\g<1>{mention_tag}",
            content,
        )
        with open(top_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"(total_mentions for {top['node']} updated to {mention_tag})")
