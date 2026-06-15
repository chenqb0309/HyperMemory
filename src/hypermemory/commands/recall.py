"""hm recall — 關鍵字匹配回憶"""

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

    # Find best matching cluster
    kw_list, node_file, score = find_best_cluster(query, entries)[:3]

    if not kw_list:
        print(f"No matching memory found for: {' '.join(query)}")
        return

    # Read node
    node_path = pool / node_file
    if not node_path.exists():
        print(f"Node file not found: {node_path}")
        sys.exit(1)

    with open(node_path, encoding="utf-8") as f:
        content = f.read()

    fm = parse_frontmatter(content)
    title = extract_title(content)
    weight = calc_weight(
        fm.get("intensity", 1),
        fm.get("total_mentions", 0),
        fm.get("timestamp"),
    )

    # Display result
    cluster_name = ", ".join(kw_list[:5])
    if len(kw_list) > 5:
        cluster_name += f" ... (+{len(kw_list)-5})"
    print(f"Matched cluster: {cluster_name}")
    print(f"  Score: {score:.2f}")
    print()
    print(f"Node: {node_file}")
    print(f"Title: {title}")
    print(f"Type: T{fm.get('node_type', '?')}")
    print(f"Intensity: {fm.get('intensity', '?')}")
    print(f"Mentions: {fm.get('total_mentions', 0)}")
    print(f"Weight: {format_score(weight)}")
    print()

    # Show body content (first 20 lines after frontmatter and body links)
    lines = content.split("\n")
    body_start = 0
    for i, line in enumerate(lines):
        if line.startswith("## "):
            body_start = i + 1
            break

    print("--- Content ---")
    for line in lines[body_start:body_start + 20]:
        print(line)
    if len(lines) > body_start + 20:
        print("...")

    # Update total_mentions (+1)
    if not args.dry_run:
        mention_tag = fm.get("total_mentions", 0)
        if isinstance(mention_tag, int):
            mention_tag += 1
        else:
            mention_tag = 1
        # Simple replacement
        import re
        new_content = re.sub(
            r'(total_mentions:\s*)\d+',
            rf'\g<1>{mention_tag}',
            content,
        )
        with open(node_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"\n(total_mentions updated to {mention_tag})")
