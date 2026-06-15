"""hm think — 習慣性回想（輕量版 recall）"""

import sys

from hypermemory.core.pool import resolve_pool, index_path
from hypermemory.core.index import parse_index
from hypermemory.core.cluster import find_best_cluster
from hypermemory.core.node import parse_frontmatter, extract_title
from hypermemory.core.weight import calc_weight, format_score


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
    result = find_best_cluster(query, entries)
    kw_list, node_file, score = result[:3]

    if not kw_list:
        print("No relevant experience found.")
        return

    node_path = pool / node_file
    if not node_path.exists():
        print(f"Node file not found: {node_file}")
        return

    with open(node_path, encoding="utf-8") as f:
        content = f.read()

    fm = parse_frontmatter(content)
    title = extract_title(content)
    weight = calc_weight(
        fm.get("intensity", 1),
        fm.get("total_mentions", 0),
        fm.get("timestamp"),
    )

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

    print(f"Related experience found (score: {score:.2f}):")
    print()
    print(f"  Title:    {title}")
    print(f"  Type:     T{fm.get('node_type', '?')}")
    print(f"  Strength: {fm.get('intensity', '?')}/10 (weight: {format_score(weight)})")
    if fm.get("tags"):
        print(f"  Tags:     {', '.join(fm.get('tags', []))}")
    if body_preview:
        print(f"\n{body_preview}")

    # Update total_mentions
    if not args.dry_run:
        mentions = fm.get("total_mentions", 0) + 1
        import re
        new_content = re.sub(r'(total_mentions:\s*)\d+', rf'\g<1>{mentions}', content)
        with open(node_path, "w", encoding="utf-8") as f:
            f.write(new_content)
