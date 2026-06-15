"""hm imprint — 從檔案刻錄新 node"""

import sys, os, shutil, re
from pathlib import Path

from hypermemory.core.pool import resolve_pool, index_path
from hypermemory.core.index import parse_index, update_index_entry
from hypermemory.core.node import parse_frontmatter, extract_title
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
    content = _strip_body_links(content)
    content = _generate_body_links(content)

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
    new_keywords = _extract_keywords(fm, dest_name)

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
            _sync_parent_links(pool, prenode, dest_name)

        else:
            new_entry = _format_entry(new_keywords, dest_name)
            index_content += new_entry + "\n"
            print(f"  New cluster created (prenode {prenode} not indexed)")

    else:
        new_entry = _format_entry(new_keywords, dest_name)
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
    print(f"  Weight:  {format_score(weight)}")


# ─── Body Link Auto-generation ───────────────────────────────


def _strip_body_links(content):
    """移除 body 中既有的 ## 關聯 區塊（保留 frontmatter 中的 wikilinks）"""
    return re.sub(r'\n##\s*關聯\n.*?(?=\n##|\Z)', '', content, flags=re.DOTALL)


def _generate_body_links(content):
    """根據 frontmatter 自動產生 body link ## 關聯 區塊。
    寫入位置：在第一個 heading（# 或 ##）之後，下一個區塊之前。
    """
    fm = parse_frontmatter(content)
    prenode = fm.get("prenode")
    nextnodes = fm.get("nextnodes", [])
    ref_by = fm.get("ref_by", [])

    # Build link lines
    lines = []
    if prenode:
        lines.append(f"- 前驅：[[{prenode}]]")
    if nextnodes:
        children_str = "、".join(f"[[{c}]]" for c in nextnodes)
        lines.append(f"- 後繼：{children_str}")
    if ref_by:
        refs_str = "、".join(f"[[{r}]]" for r in ref_by)
        lines.append(f"- 參考來源：{refs_str}")

    if not lines:
        return content  # No links at all, nothing to add

    link_section = "\n\n## 關聯\n" + "\n".join(lines) + "\n"

    # Find the first heading (# or ##) to insert after
    heading_match = re.search(r'^#{1,3}\s+.+$', content, re.MULTILINE)
    if not heading_match:
        return content

    insert_pos = heading_match.end()
    return content[:insert_pos] + link_section + content[insert_pos:]


# ─── Parent Node Synchronization ────────────────────────────


def _sync_parent_links(pool, parent_name, child_name):
    """在 parent node 中：
    1. 將 child 加入 nextnodes
    2. 重新產生 body link 區塊（根據 frontmatter 最新狀態）
    """
    parent_path = pool / parent_name
    if not parent_path.exists():
        return

    with open(parent_path, encoding="utf-8") as f:
        content = f.read()

    fm = parse_frontmatter(content)
    existing = fm.get("nextnodes", []) or []

    if child_name not in existing:
        # Add child to frontmatter nextnodes
        all_children = existing + [child_name]
        nextnodes_block = "nextnodes:\n" + "\n".join(
            f"  - [[{c}]]" for c in all_children
        )

        fm_match = re.search(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
        if not fm_match:
            return

        fm_text = fm_match.group(1)
        fm_start, fm_end = fm_match.span(1)

        if re.search(r'^nextnodes:', fm_text, re.MULTILINE):
            lines = fm_text.split("\n")
            start_idx = None
            block_end = None
            for i, line in enumerate(lines):
                if re.match(r"^nextnodes:", line):
                    start_idx = i
                if start_idx is not None and i > start_idx:
                    if re.match(r"^\w+:", line):
                        block_end = i
                        break
            if block_end is None:
                block_end = len(lines)
            old_block = "\n".join(lines[start_idx:block_end])
            new_fm = fm_text.replace(old_block, nextnodes_block, 1)
        else:
            insert = None
            for f in ["total_mentions", "intensity", "node_type"]:
                m = re.search(rf"^{f}:.*$", fm_text, re.MULTILINE)
                if m:
                    insert = m.group(0)
            if insert:
                new_fm = fm_text.replace(insert, insert + "\n" + nextnodes_block, 1)
            else:
                new_fm = fm_text + "\n" + nextnodes_block

        content = content[:fm_start] + new_fm + content[fm_end:]
        print(f"  Updated nextnodes in parent: {parent_name}")

    # Regenerate body link section for parent (idempotent)
    content = _strip_body_links(content)
    content = _generate_body_links(content)

    with open(parent_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  Synced body links in parent: {parent_name}")


# ─── Helpers ─────────────────────────────────────────────────


def _extract_keywords(fm, filename):
    keywords = list(fm.get("tags", []))
    name_part = filename.replace(".md", "").split("-", 3)
    if len(name_part) >= 4:
        desc = name_part[3].replace("-", " ")
        if desc not in keywords:
            keywords.append(desc)
    return keywords


def _format_entry(keywords, node_filename):
    kw_str = ", ".join(keywords)
    return f"《cluster: [{kw_str}]》 → [[{node_filename}]]"
