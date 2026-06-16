"""HyperMemory 核心 — 語義聯想（第三層 Associative Recall）

從 node body 提取關鍵詞 → 二次 query index → 回傳 suggestions。
純 keyword-space 處理，不引入 embedding 或外部 API。
"""

import re
import string
from pathlib import Path

from hypermemory.core.cluster import find_all_clusters
from hypermemory.core.node import parse_frontmatter, extract_title
from hypermemory.core.index import parse_index


# ─── 停止詞 ─────────────────────────────────────────────

STOPWORDS_CJK = {
    "一個", "可以", "這個", "那個", "什麼", "沒有", "我們", "他們",
    "因為", "所以", "但是", "如果", "就是", "不是", "還是", "或者",
    "而且", "然後", "之後", "之前", "這裡", "那裡", "怎麼", "如何",
    "很", "的", "了", "是", "在", "和", "與", "也", "就", "都", "而",
    "及", "等", "或", "被", "把", "讓", "從", "到", "對", "向", "跟",
    "比", "用", "以", "為", "因", "由", "于", "關", "於", "上", "下",
    "中", "內", "外", "前", "後", "不", "一", "有", "這",
}

# Single-character stopwords extracted from STOPWORDS_CJK for CJK segment filtering
_SINGLE_CHAR_STOPWORDS = {c for c in STOPWORDS_CJK if len(c) == 1}

ENGLISH_STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "because", "as", "what",
    "which", "this", "that", "these", "those", "then", "just", "so", "than",
    "such", "both", "through", "about", "for", "is", "of", "while", "during",
    "to", "from", "in", "on", "by", "with", "without", "at", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will", "would",
    "can", "could", "should", "may", "might", "shall", "need", "dare",
    "ought", "used", "was", "were", "are", "am", "is",
    "not", "no", "nor", "it", "its", "i", "we", "you", "they", "he", "she",
    "them", "their", "our", "my", "your", "his", "her", "me", "us", "mine",
    "yours", "ours", "theirs", "itself", "himself", "herself", "myself",
    "yourself", "ourselves", "themselves", "each", "every", "all", "any",
    "some", "few", "many", "much", "more", "most", "other", "another",
    "here", "there", "where", "when", "why", "how", "too", "very",
    "really", "quite", "still", "already", "also", "ever", "even",
    "always", "never", "often", "sometimes", "usually", "then", "now",
    "once", "again", "well", "only", "own", "same", "until",
    "above", "below", "up", "down", "out", "off", "over", "under",
    "further", "against", "between", "into",
}


# ─── Body 關鍵詞提取 ────────────────────────────────────


def _cjk_segments(text):
    """從文字中提取 CJK 2-3 字關鍵詞。

    對每個 [\\u4e00-\\u9fff]+ 片語，取所有長度 2-3 的子字串，
    過濾掉首字為單字停止詞的 segment，以及全段在 STOPWORDS_CJK 中的 segment。
    回傳有序、去重列表。
    """
    results = []
    phrases = re.findall(r"[\u4e00-\u9fff]+", text)
    for phrase in phrases:
        if len(phrase) < 2:
            continue
        for length in (2, 3):
            if length > len(phrase):
                continue
            for i in range(len(phrase) - length + 1):
                seg = phrase[i : i + length]
                # 全段在 STOPWORDS_CJK 中 → 跳過
                if seg in STOPWORDS_CJK:
                    continue
                # 首字是單字停止詞（的、了、是、關、比等）→ 跳過
                if seg[0] in _SINGLE_CHAR_STOPWORDS:
                    continue
                results.append(seg)
    # 去重，保留順序
    seen = set()
    deduped = []
    for r in results:
        if r not in seen:
            seen.add(r)
            deduped.append(r)
    return deduped


def _english_keywords(text):
    """從文字中提取英文關鍵詞。

    逐詞 split，strip punctuation，lowercase，
    過濾 stopwords 和長度 <= 2 的詞。
    回傳有序、去重列表。
    """
    results = []
    for word in text.split():
        w = word.strip(string.punctuation)
        if not w:
            continue
        w = w.lower()
        if len(w) <= 2:
            continue
        if w in ENGLISH_STOPWORDS:
            continue
        results.append(w)
    seen = set()
    deduped = []
    for r in results:
        if r not in seen:
            seen.add(r)
            deduped.append(r)
    return deduped


def extract_body_keywords(body_text, max_keywords=8):
    """從 node body 提取高頻實詞。

    Parameters
    ----------
    body_text : str
        Node 的正文內容（不含 frontmatter）
    max_keywords : int
        最多回傳的關鍵詞數量

    Returns
    -------
    list of str
        提取出的關鍵詞（去重、按出現順序）
    """
    if not body_text or len(body_text.strip()) < 20:
        return []

    # CJK 處理
    cjk_kw = _cjk_segments(body_text)

    # 英文處理（排除含 CJK 字元的詞）
    eng_kw = _english_keywords(body_text)

    # 合併：CJK 優先
    combined = cjk_kw + eng_kw

    # 去重（保留第一次出現的順序）
    seen = set()
    result = []
    for kw in combined:
        if kw not in seen:
            seen.add(kw)
            result.append(kw)

    return result[:max_keywords]


# ─── 語義聯想 ───────────────────────────────────────────


def associative_recall(pool, source_node, top_k=3, entries=None):
    """以 source node 的 body 關鍵詞做語義聯想。

    Parameters
    ----------
    pool : Path
        記憶池路徑
    source_node : str
        源 node 檔名
    top_k : int
        最多回傳 suggestions 數
    entries : list | None
        index entries（預設從 index.md 自動讀取）

    Returns
    -------
    dict
    {
        "found": True/False,
        "source_node": str,
        "body_keywords": [...],
        "suggestions": [
            {"node": str, "title": str, "score": float, "match_keywords": [...]},
        ]
    }
    """
    pool = Path(pool)
    node_path = pool / source_node

    # 1. 讀取 source node
    if not node_path.exists():
        return {
            "found": False,
            "source_node": source_node,
            "body_keywords": [],
            "suggestions": [],
        }

    with open(node_path, encoding="utf-8") as f:
        content = f.read()

    fm = parse_frontmatter(content)

    # 分離 body（frontmatter 之後的內容）
    fm_match = re.search(r"^---\s*\n.*?\n---", content, re.DOTALL)
    if fm_match:
        body_text = content[fm_match.end() :].strip()
    else:
        body_text = content.strip()

    # 2. 從 body 提取關鍵詞
    body_keywords = extract_body_keywords(body_text)
    if not body_keywords:
        return {
            "found": True,
            "source_node": source_node,
            "body_keywords": [],
            "suggestions": [],
        }

    # 3. 讀取 index
    if entries is None:
        idx_path = pool / "index.md"
        if not idx_path.exists():
            return {
                "found": True,
                "source_node": source_node,
                "body_keywords": body_keywords,
                "suggestions": [],
            }
        with open(idx_path, encoding="utf-8") as f:
            entries = parse_index(f.read())

    if not entries:
        return {
            "found": True,
            "source_node": source_node,
            "body_keywords": body_keywords,
            "suggestions": [],
        }

    # 4. Query index with body keywords
    matches = find_all_clusters(body_keywords, entries, min_score=0.0)

    if not matches:
        return {
            "found": True,
            "source_node": source_node,
            "body_keywords": body_keywords,
            "suggestions": [],
        }

    # 5. 過濾掉 source node 自己
    matches = [m for m in matches if m["node"] != source_node]

    # 6. 取 top_k
    matches = matches[:top_k]

    # 7. 建立 suggestions
    suggestions = []
    for m in matches:
        # 找出實際匹配到的 body keywords
        cluster_lower = [k.strip().lower() for k in m["keywords"] if k.strip()]
        match_keywords = []
        for bk in body_keywords:
            bk_lower = bk.lower()
            for ck in cluster_lower:
                if bk_lower in ck or ck in bk_lower:
                    match_keywords.append(bk)
                    break

        # 讀取 suggestion node 的 title
        sug_node = m["node"]
        sug_path = pool / sug_node
        if sug_path.exists():
            with open(sug_path, encoding="utf-8") as f:
                sug_content = f.read()
            sug_title = extract_title(sug_content)
        else:
            sug_title = sug_node

        suggestions.append({
            "node": sug_node,
            "title": sug_title,
            "score": round(m["score"], 3),
            "match_keywords": match_keywords,
        })

    return {
        "found": True,
        "source_node": source_node,
        "body_keywords": body_keywords,
        "suggestions": suggestions,
    }
