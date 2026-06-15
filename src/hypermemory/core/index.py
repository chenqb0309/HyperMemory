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

        # Count how many query words match this cluster
        matched = sum(1 for qw in query_words if qw in entry_words)
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
    pattern = r'(《cluster:\s*\[(.*?)\]\s*→\s*\[\[)' + re.escape(old_node) + r'(\]\]\))'
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
