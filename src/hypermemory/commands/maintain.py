"""hm maintain — 維護循環"""

import sys

from hypermemory.core.pool import resolve_pool, index_path, list_nodes
from hypermemory.core.index import parse_index, update_index_entry
from hypermemory.core.node import parse_frontmatter, extract_title
from hypermemory.core.weight import calc_weight, format_score


def run(args):
    pool = resolve_pool(args.pool)

    if args.action == "recalc":
        _recalc(pool)
    elif args.action == "dreamloop":
        _dreamloop(pool)
    elif args.action == "all":
        print("=== Recalc ===")
        _recalc(pool)
        print()
        print("=== DreamLoop ===")
        _dreamloop(pool)
    else:
        print(f"Unknown action: {args.action}")
        sys.exit(1)


def _recalc(pool):
    """權重重算：掃描所有 cluster 鏈，確保 index 指向最高權重 node"""
    idx_path = index_path(pool)
    if not idx_path.exists():
        print("Index not found.")
        return

    with open(idx_path, encoding="utf-8") as f:
        index_content = f.read()
    entries = parse_index(index_content)

    if not entries:
        print("(empty index)")
        return

    print(f"Recalc: {len(entries)} clusters")
    changes = 0

    for keywords, current_node in entries:
        node_path = pool / current_node
        if not node_path.exists():
            print(f"  [✗] {current_node} — file not found, skipping")
            continue

        # Walk the chain: from current node, backtrack via prenode to root
        chain_nodes = []
        walk = current_node
        visited = set()
        while walk and walk not in visited:
            visited.add(walk)
            chain_nodes.append(walk)
            wp = pool / walk
            if wp.exists():
                with open(wp, encoding="utf-8") as f:
                    content = f.read()
                fm = parse_frontmatter(content)
                walk = fm.get("prenode")
            else:
                break

        if not chain_nodes:
            continue

        # Calculate weights for all nodes in chain
        best_node = None
        best_weight = -1
        node_weights = []

        for node_name in chain_nodes:
            np = pool / node_name
            if not np.exists():
                continue
            with open(np, encoding="utf-8") as f:
                content = f.read()
            fm = parse_frontmatter(content)
            weight = calc_weight(
                fm.get("intensity", 1),
                fm.get("total_mentions", 0),
                fm.get("timestamp"),
            )
            node_weights.append((node_name, weight, fm.get("intensity", 1), fm.get("total_mentions", 0)))
            if weight > best_weight:
                best_weight = weight
                best_node = node_name

        # Update index if pointer changed
        if best_node and best_node != current_node:
            index_content = update_index_entry(index_content, current_node, best_node)
            changes += 1
            print(f"  ↑ {current_node} → {best_node} (w={format_score(best_weight)})")
        elif best_node:
            print(f"  ✓ {current_node} (w={format_score(best_weight)})")

    if changes > 0:
        with open(idx_path, "w", encoding="utf-8") as f:
            f.write(index_content)
        print(f"\nIndex updated: {changes} cluster(s) re-pointed")
    else:
        print("\nNo changes — all pointers are correct")


def _dreamloop(pool):
    """關鍵字收斂：去重、合併重疊 cluster、清理孤立關鍵字"""
    idx_path = index_path(pool)
    if not idx_path.exists():
        print("Index not found.")
        return

    with open(idx_path, encoding="utf-8") as f:
        content = f.read()
    entries = parse_index(content)

    if not entries:
        print("(empty index)")
        return

    print(f"DreamLoop: {len(entries)} clusters")

    # Scan 1: Dedup keywords within each cluster
    changes = 0
    new_lines = []
    for line in content.split("\n"):
        m = __import__("re").search(r'《cluster:\s*\[(.*?)\]》\s*→\s*\[\[(.+?)\]\]', line)
        if m:
            kw_str = m.group(1)
            node_file = m.group(2)
            keywords = [k.strip() for k in kw_str.split(",")]
            # Dedup
            seen = set()
            deduped = []
            for k in keywords:
                k_lower = k.lower()
                if k_lower not in seen:
                    seen.add(k_lower)
                    deduped.append(k)
            if len(deduped) != len(keywords):
                new_kw = ", ".join(deduped)
                new_line = f"《cluster: [{new_kw}]》 → [[{node_file}]]"
                line = new_line
                changes += 1
        new_lines.append(line)

    if changes > 0:
        content = "\n".join(new_lines)
        print(f"  Scan 1: {changes} cluster(s) deduped")

    # Scan 2: Check for orphan keywords (node file missing)
    orphans = 0
    new_lines = []
    for line in content.split("\n"):
        m = __import__("re").search(r'《cluster:\s*\[(.*?)\]》\s*→\s*\[\[(.+?)\]\]', line)
        if m:
            node_file = m.group(2)
            np = pool / node_file
            if not np.exists():
                orphans += 1
                print(f"  [✗] Orphan cluster: {node_file} (file not found)")
                continue  # Skip this line
        new_lines.append(line)

    if orphans > 0:
        content = "\n".join(new_lines)
        print(f"  Scan 2: {orphans} orphan cluster(s) removed")

    # Write changes
    with open(idx_path, "w", encoding="utf-8") as f:
        f.write(content)

    if changes == 0 and orphans == 0:
        print("  No changes needed")
