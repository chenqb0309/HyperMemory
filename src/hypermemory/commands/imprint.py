"""hm imprint — 從檔案刻錄新 node"""

import sys, os, shutil, re
from pathlib import Path

from hypermemory.core.pool import resolve_pool, index_path
from hypermemory.core.index import parse_index, update_index_entry, format_index_entry, sync_parent_links
from hypermemory.core.node import parse_frontmatter, extract_title, strip_body_links, generate_body_links, extract_keywords
from hypermemory.core.weight import calc_weight, format_score


def run(args):
    pool = resolve_pool(args.pool)
    idx_path = index_path(pool)

    # 1. Read input file
    src = Path(args.file)
    if not src.exists():
        print(f"File not found: {src}")
        sys.exit(1)

    with open(src, encoding="utf-8") as f:
        content = f.read()

    # 2. Validate frontmatter
    fm = parse_frontmatter(content)
    errors = []

    if not fm.get("type"):
        errors.append("Missing required field: type")
    if not fm.get("timestamp"):
        errors.append("Missing required field: timestamp")
    if fm.get("node_type") is None:
        errors.append("Missing required field: node_type")
    if fm.get("intensity") is None:
        errors.append("Missing required field: intensity")
    if fm.get("total_mentions") is None:
        errors.append("Missing required field: total_mentions")

    node_type = fm.get("node_type")
    if node_type in (2, 3) and not fm.get("prenode"):
        errors.append("Type 2/3 requires prenode")

    if errors:
        print("Frontmatter validation failed:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)

    # 3. Determine filename
    dest_name = args.name if args.name else src.name
    if not dest_name.endswith(".md"):
        dest_name += ".md"

    dest_path = pool / dest_name
    if dest_path.exists() and not args.force:
        print(f"Node already exists: {dest_name} (use --force to overwrite)")
        sys.exit(1)

    # 4. Strip any existing body link section from input, then regenerate
    content = strip_body_links(content)
    content = generate_body_links(content)

    # Write to pool
    with open(dest_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Written: {dest_name}")

    # 5. Read or create index
    if idx_path.exists():
        with open(idx_path, encoding="utf-8") as f:
            index_content = f.read()
        entries = parse_index(index_content)
    else:
        index_content = "# HyperMemory Pool Index\n\n"
        entries = []

    # 6. Determine cluster membership
    prenode = fm.get("prenode")
    new_keywords = extract_keywords(fm, dest_name)

    if prenode:
        # Type 2/3: find prenode's cluster
        pre_entry = None
        for kw_list, node_file in entries:
            if node_file == prenode:
                pre_entry = (kw_list, node_file)
                break

        if pre_entry:
            old_node = pre_entry[1]
            old_path = pool / old_node
            old_weight = 0
            new_weight = calc_weight(
                fm.get("intensity", 1),
                fm.get("total_mentions", 1),
                fm.get("timestamp"),
            )

            if old_path.exists():
                with open(old_path, encoding="utf-8") as f:
                    old_fm = parse_frontmatter(f.read())
                old_weight = calc_weight(
                    old_fm.get("intensity", 1),
                    old_fm.get("total_mentions", 0),
                    old_fm.get("timestamp"),
                )

            if new_weight > old_weight:
                pointer_node = dest_name
                print(f"  Cluster pointer: {old_node} → {dest_name} (weight {format_score(new_weight)} > {format_score(old_weight)})")
            else:
                pointer_node = old_node
                print(f"  Cluster pointer: {old_node} (weight {format_score(old_weight)} >= {format_score(new_weight)})")

            index_content = update_index_entry(
                index_content, old_node, pointer_node, new_keywords
            )

            # Step 9b: update prenode's nextnodes + body links
            sync_parent_links(pool, prenode, dest_name)

        else:
            new_entry = format_index_entry(new_keywords, dest_name)
            index_content += new_entry + "\n"
            print(f"  New cluster created (prenode {prenode} not indexed)")

    else:
        new_entry = format_index_entry(new_keywords, dest_name)
        index_content += new_entry + "\n"
        print(f"  New cluster created")

    # 7. Write index
    with open(idx_path, "w", encoding="utf-8") as f:
        f.write(index_content)
    print(f"Index updated: {idx_path.name}")

    # 8. Summary
    weight = calc_weight(
        fm.get("intensity", 1),
        fm.get("total_mentions", 1),
        fm.get("timestamp"),
    )
    title = extract_title(content)
    print()
    print(f"Summary:")
    print(f"  File:    {dest_name}")
    print(f"  Title:   {title}")
    print(f"  Type:    T{fm.get('node_type', '?')}")
    print(f"  Weight:  {format_score(weight)}\n")
