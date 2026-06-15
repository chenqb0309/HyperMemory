"""HyperMemory 核心 — Cluster 匹配與關鍵字操作"""


def match_keywords(query, cluster_keywords):
    """計算查詢關鍵詞與 cluster 關鍵字的匹配度。

    回傳 (matched_count, total_query, score)
    score = matched_count / len(query) （若 query 為空則 0）
    """
    if not query or not cluster_keywords:
        return 0, len(query) if query else 0, 0.0

    query_lower = [q.strip().lower() for q in query if q.strip()]
    cluster_lower = [k.strip().lower() for k in cluster_keywords if k.strip()]

    if not query_lower or not cluster_lower:
        return 0, len(query_lower), 0.0

    matched = sum(1 for q in query_lower if q in cluster_lower)
    score = matched / len(query_lower)
    return matched, len(query_lower), score


def find_best_cluster(query, entries):
    """從 index entries 中找出最佳匹配的 cluster。

    entries: list of (keywords_list, node_filename)
    回傳 (keywords_list, node_filename, score_score, match_details)
    """
    if not query or not entries:
        return None, None, 0.0, {"matched": 0, "total": 0, "cluster": ""}

    query_lower = [q.strip().lower() for q in query if q.strip()]
    if not query_lower:
        return None, None, 0.0, {"matched": 0, "total": 0, "cluster": ""}

    best_entry = None
    best_score = 0.0
    best_details = None

    for kw_list, node_file in entries:
        cluster_lower = [k.strip().lower() for k in kw_list if k.strip()]
        if not cluster_lower:
            continue

        # Direct match count
        matched = sum(1 for q in query_lower if q in cluster_lower)
        if matched == 0:
            continue

        # Score = matched query words / total query words
        score = matched / len(query_lower)

        # Add cluster coverage bonus
        coverage = matched / len(cluster_lower)
        combined = score + coverage * 0.2  # 20% weight on coverage

        if combined > best_score:
            best_score = combined
            best_entry = (kw_list, node_file, combined)
            best_details = {
                "matched": matched,
                "total": len(query_lower),
                "cluster": ", ".join(kw_list),
                "coverage": f"{matched}/{len(cluster_lower)}",
            }

    if best_entry:
        return best_entry

    return None, None, 0.0, best_details
