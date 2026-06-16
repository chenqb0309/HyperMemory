"""HyperMemory 核心 — Cluster 匹配與關鍵字操作

職責：**搜尋匹配引擎**
角色：從 parse 好的 index entries 中做關鍵詞比對、評分、排名。
不負責讀寫 index.md 檔案（那是 index.py 的事）。

與 index.py 的關係：
   index.py 管「怎麼讀寫 index.md」→ 產出 entries
   cluster.py 管「怎麼在 entries 裡搜尋」→ 算出分數

注意：find_all_clusters 的 coverage 權重（0.2）與 index.py 的 match_cluster
coverage 權重（0.3）數值不同，因為兩者是不同用途：
  - cluster.py 的 0.2 → 檢索時對 cluster 覆蓋率的加分（搜尋）
  - index.py 的 0.3   → 寫入前對現有 cluster 的比對權重（重複檢查）
"""


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

    matched = find_all_clusters(query, entries, min_score=0.0)
    if not matched:
        return None, None, 0.0, {"matched": 0, "total": 0, "cluster": ""}
    best = matched[0]
    return (best["keywords"], best["node"], best["score"], best["details"])


def find_all_clusters(query, entries, min_score=0.0):
    """找出所有匹配分數超過 min_score 的 cluster，按分數降冪排序。

    entries: list of (keywords_list, node_filename)
    query: list of str
    min_score: float，最低匹配分數（0.0 ~ 1.0）

    回傳 list of dict:
    {keywords, node, score, details: {matched, total, cluster, coverage}}
    """
    if not query or not entries:
        return []

    query_lower = [q.strip().lower() for q in query if q.strip()]
    if not query_lower:
        return []

    results = []
    for kw_list, node_file in entries:
        cluster_lower = [k.strip().lower() for k in kw_list if k.strip()]
        if not cluster_lower:
            continue

        # Direct match count (exact + substring for CJK support)
        matched = 0
        for q in query_lower:
            for c in cluster_lower:
                if q in c or c in q:
                    matched += 1
                    break
        if matched == 0:
            continue

        # Score = matched query words / total query words
        score = matched / len(query_lower)
        # Add cluster coverage bonus
        coverage = matched / len(cluster_lower)
        combined = score + coverage * 0.2  # 20% weight on coverage

        if combined < min_score:
            continue

        results.append({
            "keywords": kw_list,
            "node": node_file,
            "score": round(combined, 3),
            "details": {
                "matched": matched,
                "total": len(query_lower),
                "cluster": ", ".join(kw_list),
                "coverage": f"{matched}/{len(cluster_lower)}",
            },
        })

    results.sort(key=lambda r: r["score"], reverse=True)
    return results
