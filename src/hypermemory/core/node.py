"""HyperMemory 核心 — Node Frontmatter 解析"""

import re


# ─── Memory Marker ────────────────────────────────────────
#
# 設計約束 7：所有 node 檔案必須以 marker 包覆，標示「這是記憶，不是事實」。
# 三個路徑強制：CLI imprint、MCP imprint、reflect。parse_frontmatter 自動跳過 marker。

MARKER_START = "^HM_MEMORY_START"
MARKER_DISC = "# HyperMemory 經驗記錄 — 非當前事實，使用前請確認時效性與場景適用性"
MARKER_END = "^HM_MEMORY_END"


def has_marker(content: str) -> bool:
    """檢查 node 內容是否已包含 marker。"""
    lines = content.strip("\n").split("\n")
    return (
        len(lines) >= 4
        and lines[0].strip() == MARKER_START
        and lines[-1].strip() == MARKER_END
    )


def wrap_markers(content: str) -> str:
    """為 node 內容加上 marker 包覆。已存在則略過（idempotent）。"""
    if has_marker(content):
        return content
    return (
        MARKER_START + "\n"
        + MARKER_DISC + "\n"
        + content.rstrip("\n") + "\n"
        + MARKER_END + "\n"
    )


def strip_markers(content: str) -> str:
    """移除 marker 包覆，還原純 node 內容。
    無 marker 則原樣回傳（idempotent）。
    """
    if not content.startswith(MARKER_START):
        return content
    # Skip first two lines (START + DISC), then find END marker
    lines = content.split("\n")
    end_idx = None
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip() == MARKER_END:
            end_idx = i
            break
    if end_idx is not None:
        return "\n".join(lines[2:end_idx]) + "\n"
    return content


# ─── 別名（向後相容）────────────────────────────────────────

wrap_marker = wrap_markers
unwrap_marker = strip_markers


# ─── Frontmatter Parsing ──────────────────────────────────


def parse_frontmatter(content):
    """解析 node 檔案的 frontmatter，回傳 dict。

    支援 scalar（prenode）和 list（nextnodes, ref_by, tags）格式。
    自動跳過 memory marker 行。
    """
    fm = {}

    # 跳過 memory marker 行（設計約束 7）
    # MARKER_START + MARKER_DISC 共兩行，以及任何 ^ 前綴行
    while content.startswith(("^", MARKER_DISC)):
        content = content.split("\n", 1)[1] if "\n" in content else ""

    fm_match = re.search(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
    if not fm_match:
        return fm
    
    fm_text = fm_match.group(1)

    # Simple scalar fields
    for field in ["type", "timestamp", "node_type", "intensity", "total_mentions"]:
        m = re.search(rf'^{field}:\s*(.+)', fm_text, re.MULTILINE)
        if m:
            fm[field] = m.group(1).strip()

    # Boolean scalar fields
    for field in ["skill_ready", "has_skill"]:
        m = re.search(rf'^{field}:\s*(.+)', fm_text, re.MULTILINE)
        if m:
            val = m.group(1).strip().lower()
            fm[field] = val == "true"

    # String scalar fields (with null support)
    for field in ["skill_ready_at", "skill_path"]:
        m = re.search(rf'^{field}:\s*(.+)', fm_text, re.MULTILINE)
        if m:
            val = m.group(1).strip()
            fm[field] = None if val == "null" else val

    # Convert numeric fields
    if "node_type" in fm:
        fm["node_type"] = int(fm["node_type"])
    if "intensity" in fm:
        fm["intensity"] = int(fm["intensity"])
    if "total_mentions" in fm:
        fm["total_mentions"] = int(fm["total_mentions"])

    # prenode (scalar wikilink)
    m = re.search(r'^prenode:\s*(.+)', fm_text, re.MULTILINE)
    if m:
        val = m.group(1).strip()
        link = re.search(r'\[\[(.+?)\]\]', val)
        if link:
            fm["prenode"] = link.group(1)
        elif val == "null":
            fm["prenode"] = None
        else:
            fm["prenode"] = val

    # List fields: nextnodes, ref_by, tags
    for field in ["nextnodes", "ref_by", "tags"]:
        items = _parse_list_field(fm_text, field)
        fm[field] = items

    # dimensions (nested dict field)
    dims = _parse_dimensions_field(fm_text)
    if dims:
        fm["dimensions"] = dims

    return fm


def _parse_list_field(fm_text, field):
    """解析 YAML list 格式的 frontmatter 欄位"""
    # Try scalar first (horizontal whitespace only, no newline)
    m = re.search(rf'^{field}:[ \t]*(.+)$', fm_text, re.MULTILINE)
    if m:
        val = m.group(1).strip()
        if val == "null":
            return []
        if val:
            # Strip outer YAML list brackets [...]
            # (handles nextnodes: [[wikilink]] → inner [[wikilink]])
            inner = val
            if inner.startswith("[") and inner.endswith("]"):
                inner = inner[1:-1].strip()
            # Check for single-line wikilinks
            links = re.findall(r'\[\[(.+?)\]\]', inner)
            if links:
                return links
            # For tags (not wikilinks)
            if field == "tags":
                tags = [t.strip().strip("'\"") for t in inner.strip("[]").split(",")]
                return [t for t in tags if t]
        # Empty value means list format follows — fall through

    # List format (value on subsequent lines with - prefix)
    items = []
    in_list = False
    for line in fm_text.split("\n"):
        if re.match(rf'^{field}:', line):
            in_list = True
            continue
        if in_list:
            if re.match(r'^\s+-', line):
                link = re.search(r'\[\[(.+?)\]\]', line)
                if link:
                    items.append(link.group(1))
                else:
                    # Plain text item (for tags)
                    tag = re.sub(r'^\s+-\s+', "", line).strip().strip("\"'")
                    if tag:
                        items.append(tag)
            else:
                break
    return items


def _parse_dimensions_field(fm_text):
    """解析 frontmatter 中的 dimensions 巢狀 dict 欄位。

    格式：
    ```
    dimensions:
      機: value
      料: value
    ```

    回傳 dict，無 dimensions 時回傳 None。
    """
    m = re.search(r'^dimensions:\s*$', fm_text, re.MULTILINE)
    if not m:
        return None

    dims = {}
    after = fm_text[m.end():]
    for line in after.split("\n"):
        em = re.match(r'^\s+(\S):\s*(.+)$', line)
        if em:
            dims[em.group(1)] = em.group(2).strip()
        elif line.strip() and not line.startswith(" ") and ":" in line:
            # 已離開 dimensions 區塊（遇到新的 top-level 欄位）
            break
    return dims if dims else None


def extract_title(content):
    """從 node 內容中提取 # Title（支援 ## Title 作為 fallback）"""
    m = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
    if m:
        return m.group(1).strip()
    # Fallback to first ## heading
    m = re.search(r'^##\s+(.+)$', content, re.MULTILINE)
    if m:
        return m.group(1).strip()
    return "(untitled)"


def extract_body_link_section(content):
    """提取 body 中的 ## 關聯 區塊"""
    m = re.search(r'##\s+關聯\n(.*?)(?=\n##|\Z)', content, re.DOTALL)
    if m:
        return m.group(1).strip()
    return None


# ─── Body Link Generation ─────────────────────────────────


def strip_body_links(content):
    """移除 body 中既有的 ## 關聯 區塊（保留 frontmatter 中的 wikilinks）"""
    return re.sub(r'\n##\s*關聯\n.*?(?=\n##|\Z)', '', content, flags=re.DOTALL)


def generate_body_links(content):
    """根據 frontmatter 自動產生 body link ## 關聯 區塊。
    寫入位置：在第一個 heading（# 或 ##）之後，下一個區塊之前。
    """
    fm = parse_frontmatter(content)
    prenode = fm.get("prenode")
    nextnodes = fm.get("nextnodes", [])
    ref_by = fm.get("ref_by", [])

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
        return content

    link_section = "\n\n## 關聯\n" + "\n".join(lines) + "\n"

    heading_match = re.search(r'^#{1,3}\s+.+$', content, re.MULTILINE)
    if not heading_match:
        return content

    insert_pos = heading_match.end()
    return content[:insert_pos] + link_section + content[insert_pos:]


def extract_keywords(fm, filename):
    """從 frontmatter tags + 檔名提取關鍵字"""
    keywords = list(fm.get("tags", []))
    name_part = filename.replace(".md", "").split("-", 3)
    if len(name_part) >= 4:
        desc = name_part[3].replace("-", " ")
        if desc not in keywords:
            keywords.append(desc)
    return keywords
