"""HyperMemory 核心 — Index 解析與更新"""

import re


def parse_index(index_text):
    """解析 index.md 文字內容，回傳 list of (keywords_list, node_filename)"""
    entries = []
    pattern = r'《cluster:\s*\[(.*?)\]》\s*→\s*\[\[(.+?)\]\]'
    for m in re.finditer(pattern, index_text):
        kw_str = m.group(1)
        keywords = [k.strip() for k in kw_str.split(",")]
        node_file = m.group(2)
        entries.append((keywords, node_file))
    return entries


def match_cluster(keywords, entries):
    """給定關鍵詞列表和 index entries，回傳最佳匹配的 (keywords, node_filename, score)

    score = 匹配到的關鍵字數量 / 查詢關鍵字總數
    支援中文（substring 匹配）：查詢「設計」可命中 cluster 中的「設計哲學」
    若無匹配（score=0），回傳 (None, None, 0)
    """
    if not keywords or not entries:
        return None, None, 0

    query_words = [k.strip().lower() for k in keywords if k.strip()]

    best_entry = None
    best_match = 0

    for entry_kw, node_file in entries:
        entry_words = [k.strip().lower() for k in entry_kw if k.strip()]
        if not entry_words:
            continue

        # Count matched keywords (exact + substring for CJK)
        matched = 0
        for qw in query_words:
            for ew in entry_words:
                if qw in ew or ew in qw:
                    matched += 1
                    break
        if matched == 0:
            continue

        # Score: proportion of query words matched
        score = matched / len(query_words)
        # Bonus: also consider coverage of entry keywords
        coverage = matched / len(entry_words)
        combined = score + coverage * 0.3  # weight toward query match

        if combined > best_match:
            best_match = combined
            best_entry = (entry_kw, node_file, combined)

    if best_entry:
        return best_entry

    # No match found
    return None, None, 0


def format_index_entry(keywords, node_filename):
    """格式化一條 index 條目"""
    kw_str = ", ".join(keywords)
    return f"《cluster: [{kw_str}]》 → [[{node_filename}]]"


def update_index_entry(index_text, old_node, new_node, new_keywords=None):
    """在 index.md 文字中更新 node 指標。
    若 new_keywords 提供，同時擴增關鍵字。
    回傳更新後的文字。
    """
    pattern = r'(《cluster:\s*\[(.*?)\]》\s*→\s*\[\[)' + re.escape(old_node) + r'(\]\])'
    replacement = None

    for m in re.finditer(pattern, index_text):
        current_keywords = [k.strip() for k in m.group(2).split(",")]
        if new_keywords:
            # Merge new keywords (avoid duplicates)
            for kw in new_keywords:
                k = kw.strip()
                if k and k not in current_keywords:
                    current_keywords.append(k)
        kw_str = ", ".join(current_keywords)
        replacement = f"《cluster: [{kw_str}]》 → [[{new_node}]]"
        old_str = m.group(0)
        return index_text.replace(old_str, replacement, 1)

    return index_text  # No change


def sync_parent_links(pool, parent_name, child_name):
    """在 parent node 中：
    1. 將 child 加入 nextnodes
    2. 重新產生 body link 區塊（根據 frontmatter 最新狀態）
    """
    from pathlib import Path
    from hypermemory.core.node import parse_frontmatter, strip_body_links, generate_body_links

    parent_path = Path(pool) / parent_name if isinstance(pool, (str, Path)) else pool / parent_name
    if not parent_path.exists():
        return

    with open(parent_path, encoding="utf-8") as f:
        content = f.read()

    fm = parse_frontmatter(content)
    existing = fm.get("nextnodes", []) or []

    if child_name not in existing:
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

    content = strip_body_links(content)
    content = generate_body_links(content)

    with open(parent_path, "w", encoding="utf-8") as f:
        f.write(content)
