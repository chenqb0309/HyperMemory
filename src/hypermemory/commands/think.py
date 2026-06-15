"""hm think — 習慣性回想（lightweight recall，回傳最新 matching node）"""

import sys
import re

from hypermemory.core.pool import resolve_pool, index_path
from hypermemory.core.index import parse_index
from hypermemory.core.cluster import find_all_clusters
from hypermemory.core.node import parse_frontmatter, extract_title
from hypermemory.core.weight import calc_weight, format_score
from hypermemory.core.dimensions import parse_dimensions
from hypermemory.core.maturation import get_confirmation_stats, calc_maturation


def run(args):
    pool = resolve_pool(args.pool)
    idx_path = index_path(pool)

    if not idx_path.exists():
        print("Index not found.")
        return

    with open(idx_path, encoding="utf-8") as f:
        entries = parse_index(f.read())

    if not entries:
        print("(empty index)")
        return

    query = args.query
    kw_list = [k.strip() for k in query.replace(",", " ").split() if k.strip()]

    # Find ALL matching clusters, sorted by recency
    matches = find_all_clusters(kw_list, entries, min_score=0.3)

    if not matches:
        print("No relevant experience found.")
        return

    # Read all matched nodes, collect with timestamps
    candidates = []
    for m in matches:
        node_file = m["node"]
        node_path = pool / node_file
        if not node_path.exists():
            continue
        with open(node_path, encoding="utf-8") as f:
            content = f.read()

        fm = parse_frontmatter(content)
        title = extract_title(content)
        weight = calc_weight(
            fm.get("intensity", 1),
            fm.get("total_mentions", 0),
            fm.get("timestamp"),
        )
        node_dims = parse_dimensions(fm)
        stats = get_confirmation_stats(pool, node_file)
        mat = calc_maturation(
            fm.get("intensity", 1),
            stats["positive"],
            stats["negative"],
            fm.get("timestamp"),
            node_dims=node_dims,
        )

        candidates.append({
            "node": node_file,
            "title": title,
            "content": content,
            "fm": fm,
            "weight": weight,
            "maturation": mat,
            "timestamp": fm.get("timestamp", "0000"),
            "dimensions": node_dims,
        })

    # Sort by timestamp descending (newest first)
    candidates.sort(key=lambda n: n["timestamp"] or "0000", reverse=True)
    best = candidates[0]

    fm = best["fm"]
    content = best["content"]
    weight = best["weight"]
    mat = best["maturation"]

    # Extract body summary (first meaningful lines after headings)
    body_preview = ""
    in_body = False
    for line in content.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("## ") and "關聯" in stripped:
            continue
        if stripped.startswith("#") or stripped.startswith("---"):
            continue
        if not in_body and any(stripped.startswith(p) for p in ["1.", "2.", "-", "##", "###"]):
            if not stripped.startswith("## 關聯"):
                in_body = True
        if in_body:
            if stripped.startswith("## ") or stripped.startswith("---"):
                break
            body_preview += stripped[:150] + "\n"
            if len(body_preview) >= 400:
                body_preview += "..."
                break

    print(f"Related experience found (newest):")
    print()
    print(f"  Title:      {best['title']}")
    print(f"  Node:       {best['node']}")
    print(f"  Type:       T{fm.get('node_type', '?')}")
    print(f"  Strength:   {fm.get('intensity', '?')}/10 (weight: {format_score(weight)})")
    print(f"  Maturation: {mat['score']} (P={mat['positive_events']}/N={mat['negative_events']})")
    if fm.get("tags"):
        print(f"  Tags:       {', '.join(fm.get('tags', []))}")
    if best.get("dimensions"):
        dim_str = ", ".join(f"{k}={v}" for k, v in best["dimensions"].items())
        print(f"  Dimensions: {dim_str}")
    print(f"  Date:       {best['timestamp'][:19] if best['timestamp'] != '0000' else '(unknown)'}")
    ts_display = best["timestamp"][:10] if best["timestamp"] != "0000" else "(no date)"
    print(f"  Date:       {ts_display}")
    if body_preview:
        print(f"\n{body_preview}")

    # Update total_mentions
    if not args.dry_run:
        mentions = fm.get("total_mentions", 0) + 1
        new_content = re.sub(r"(total_mentions:\s*)\d+", rf"\g<1>{mentions}", content)
        with open(pool / best["node"], "w", encoding="utf-8") as f:
            f.write(new_content)
