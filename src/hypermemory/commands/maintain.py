"""hm maintain — 維護循環"""

import sys

from hypermemory.core.pool import resolve_pool, index_path, list_nodes
from hypermemory.core.index import parse_index, update_index_entry
from hypermemory.core.node import parse_frontmatter, extract_title
from hypermemory.core.weight import calc_weight, format_score
from hypermemory.core.log import recent as recent_logs
from hypermemory.core.print import safe_print


def run(args):
    pool = resolve_pool(args.pool)

    if args.action == "recalc":
        _recalc(pool)
    elif args.action == "dreamloop":
        _dreamloop(pool)
    elif args.action == "reflect":
        _reflect(pool, args.days)
    elif args.action == "sediment":
        _sediment(pool)
    elif args.action == "muscle":
        _muscle(pool)
    elif args.action == "all":
        print("=== Recalc ===")
        _recalc(pool)
        print()
        print("=== DreamLoop ===")
        _dreamloop(pool)
        print()
        print("=== Sediment ===")
        _sediment(pool)
        print()
        print("=== Muscle ===")
        _muscle(pool)
        print()
        print("=== Reflection ===")
        _reflect(pool, args.days)
    else:
        print(f"Unknown action: {args.action}")
        sys.exit(1)


def _recalc(pool):
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
            safe_print(f"  [x] {current_node} — file not found, skipping")
            continue

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

        best_node = None
        best_weight = -1

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
                node_type=fm.get("node_type", "經驗"),
            )
            if weight > best_weight:
                best_weight = weight
                best_node = node_name

        if best_node and best_node != current_node:
            index_content = update_index_entry(index_content, current_node, best_node)
            changes += 1
            safe_print(f"  ^ {current_node} → {best_node} (w={format_score(best_weight)})")
        elif best_node:
            safe_print(f"  v {current_node} (w={format_score(best_weight)})")

    if changes > 0:
        with open(idx_path, "w", encoding="utf-8") as f:
            f.write(index_content)
        print(f"\nIndex updated: {changes} cluster(s) re-pointed")
    else:
        print("\nNo changes — all pointers are correct")


def _dreamloop(pool):
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

    # Scan 1: Dedup keywords
    changes = 0
    new_lines = []
    for line in content.split("\n"):
        m = __import__("re").search(r'《cluster:\s*\[(.*?)\]》\s*→\s*\[\[(.+?)\]\]', line)
        if m:
            kw_str = m.group(1)
            node_file = m.group(2)
            keywords = [k.strip() for k in kw_str.split(",")]
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

    # Scan 2: Orphan removal
    orphans = 0
    new_lines = []
    for line in content.split("\n"):
        m = __import__("re").search(r'《cluster:\s*\[(.*?)\]》\s*→\s*\[\[(.+?)\]\]', line)
        if m:
            node_file = m.group(2)
            np = pool / node_file
            if not np.exists():
                orphans += 1
                safe_print(f"  [x] Orphan: {node_file}")
                continue
        new_lines.append(line)

    if orphans > 0:
        content = "\n".join(new_lines)
        print(f"  Scan 2: {orphans} orphan cluster(s) removed")

    with open(idx_path, "w", encoding="utf-8") as f:
        f.write(content)

    if changes == 0 and orphans == 0:
        safe_print("  No changes needed")


def _reflect(pool, days=3):
    """Reflection Loop：掃描 log，比對既有 node，自動刻錄新經驗"""
    from hypermemory.core.cluster import find_best_cluster
    from hypermemory.core.log import capture
    from hypermemory.core.node import strip_body_links, generate_body_links, extract_keywords
    from hypermemory.core.index import sync_parent_links, format_index_entry
    from datetime import datetime, timezone
    import re as re_module

    idx_path = index_path(pool)
    entries = []
    if idx_path.exists():
        with open(idx_path, encoding="utf-8") as f:
            entries = parse_index(f.read())

    logs = recent_logs(days=days)
    if not logs:
        print(f"Reflection: no log entries in the last {days} days")
        return

    print(f"Reflection: scanning {len(logs)} log entries from {days} day(s)")

    imprinted = 0
    skipped = 0

    for log_entry in logs:
        content = log_entry.get("content", "")
        tags = log_entry.get("tags", [])
        if not content:
            continue

        # Detect CJK content
        has_cjk = any('\u4e00' <= c <= '\u9fff' for c in content)

        if has_cjk:
            # Chinese: extract 2-char and 3-char segments as keywords
            import re as re_cjk
            cjk_chars = re_cjk.findall(r'[\u4e00-\u9fff]+', content)
            keywords = []
            for segment in cjk_chars:
                for i in range(len(segment)):
                    for j in range(2, 4):
                        if i + j <= len(segment):
                            kw = segment[i:i+j]
                            if kw not in keywords:
                                keywords.append(kw)
            keywords = keywords[:12]
        else:
            # English: split by space + stopword filtering
            stopwords = {"the","and","for","are","but","not","you","all","can","had","her","was","one","our","out","has","have","been","some","them","than","that","this","very","just","with","from","they","what","when","where","which","their","there","would","could","about","should","into","over","after","other"}
            words = [w.lower().strip(".,!?;:()[]「」") for w in content.split()]
            keywords = [w for w in words if len(w) > 2 and w not in stopwords]
            seen = set()
            keywords = [k for k in keywords if not (k in seen or seen.add(k))][:8]

        # Combine with tags
        all_keywords = list(set(keywords + tags))

        # Check if already covered
        result = find_best_cluster(all_keywords, entries)
        if result[0] is not None and result[2] > 0.5:
            skipped += 1
            continue

        # Not covered — auto-imprint
        title = log_entry.get("title") or content[:60].rstrip()
        timestamp = log_entry.get("timestamp", datetime.now(timezone.utc).isoformat())
        intensity = min(5 + len(tags), 8)  # Higher if tagged

        tags_str = ", ".join(f'"{t}"' for t in tags[:5])
        node_content = f"""---
type: episodic_memory
timestamp: {timestamp}
node_type: 1
prenode: null
nextnodes: null
ref_by: null
intensity: {intensity}
total_mentions: 1
tags: [{tags_str}]
---

# {title}

{content}
"""
        # Normalize body links
        node_content = strip_body_links(node_content)
        node_content = generate_body_links(node_content)

        # Write file
        date_str = timestamp[:10]
        slug = re_module.sub(r'[^a-z0-9]+', '-', title.lower())[:30].strip('-')
        filename = f"{date_str}-reflection-{slug}.md"
        dest_path = pool / filename

        if dest_path.exists():
            skipped += 1
            continue

        with open(dest_path, "w", encoding="utf-8") as f:
            f.write(node_content)

        # Update index (Type 1 — new cluster)
        new_keywords = extract_keywords(
            {"tags": tags + keywords[:3]}, filename
        )
        index_entry = format_index_entry(new_keywords, filename)

        with open(idx_path, "a" if idx_path.exists() else "w", encoding="utf-8") as f:
            if idx_path.exists():
                f.write(index_entry + "\n")
            else:
                f.write("# HyperMemory Pool Index\n\n" + index_entry + "\n")

        imprinted += 1
        print(f"  + {filename} ({intensity}/10) — {title[:50]}")

    safe_print(f"\nResult: {imprinted} imprinted, {skipped} skipped (already covered)")


def _sediment(pool):
    from hypermemory.core.sediment import sediment_pool
    from hypermemory.core.print import safe_print

    result = sediment_pool(pool)
    if result["archived_count"] > 0:
        for node in result["archived"]:
            safe_print(f"  [↓] {node} archived")
        print(f"\nSediment: {result['archived_count']} node(s) archived")
    else:
        print(
            f"Sediment: {result['archived_count']} archived, "
            f"{result['candidates']} candidate(s) skipped"
        )


def _muscle(pool):
    from hypermemory.core.muscle_memory import scan_and_mark_candidates, expire_stale_marks
    from hypermemory.core.print import safe_print

    expired = expire_stale_marks(pool)
    result = scan_and_mark_candidates(pool)

    if expired:
        for n in expired:
            safe_print(f"  [x] {n} expired")
    if result["marked"]:
        for n in result["marked"]:
            safe_print(f"  [✓] {n} skill_ready")
    print(f"Muscle: {len(result['marked'])} marked, {result['skipped']} skipped, {len(expired)} expired")
