"""hm inspect — 檢視單一 node 與鏈結"""

import sys
from pathlib import Path

from hypermemory.core.pool import resolve_pool, node_path
from hypermemory.core.node import parse_frontmatter, extract_title, extract_body_link_section
from hypermemory.core.weight import calc_weight, format_score


def run(args):
    pool = resolve_pool(args.pool)
    
    # Resolve node path
    try:
        npath = node_path(pool, args.node)
    except FileNotFoundError as e:
        print(e)
        sys.exit(1)

    with open(npath, encoding="utf-8") as f:
        content = f.read()

    fm = parse_frontmatter(content)
    title = extract_title(content)
    weight = calc_weight(
        fm.get("intensity", 1),
        fm.get("total_mentions", 0),
        fm.get("timestamp"),
    )

    # Display node info
    print(f"File: {npath.name}")
    print(f"Title: {title}")
    print(f"Weight: {format_score(weight)}")
    print()
    print(f"  Type:         T{fm.get('node_type', '?')}")
    print(f"  Intensity:    {fm.get('intensity', '?')}")
    print(f"  Mentions:     {fm.get('total_mentions', 0)}")
    print(f"  Timestamp:    {fm.get('timestamp', '?')}")
    print(f"  Tags:         {', '.join(fm.get('tags', [])) or '(none)'}")
    print()

    # Chain links
    prenode = fm.get("prenode")
    nextnodes = fm.get("nextnodes", [])
    ref_by = fm.get("ref_by", [])

    print("Chain:")
    if prenode:
        pre_path = pool / prenode
        pre_exists = "✓" if pre_path.exists() else "✗"
        print(f"  ↑ prenode:   {prenode} [{pre_exists}]")
    else:
        print(f"  ↑ prenode:   (root node)")

    if nextnodes:
        for child in nextnodes:
            child_path = pool / child
            child_exists = "✓" if child_path.exists() else "✗"
            print(f"  ↓ nextnodes: {child} [{child_exists}]")
    else:
        print(f"  ↓ nextnodes: (none)")

    if ref_by:
        for ref in ref_by:
            ref_path = pool / ref
            ref_exists = "✓" if ref_path.exists() else "✗"
            print(f"  ↻ ref_by:    {ref} [{ref_exists}]")

    # Body link section
    body_link = extract_body_link_section(content)
    if body_link:
        print(f"\nBody links:")
        for line in body_link.split("\n"):
            print(f"  {line.strip()}")

    print()
    # Show body content preview
    lines = content.split("\n")
    body_start = 0
    for i, line in enumerate(lines):
        if line.startswith("## 正文") or (line.startswith("## ") and "關聯" not in line):
            body_start = i + 1
            break

    print("--- Body (first 15 lines) ---")
    for line in lines[body_start:body_start + 15]:
        if line.strip():
            print(line)
    if len(lines) > body_start + 15:
        print("...")
