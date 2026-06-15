"""HyperMemory 核心 — Node Frontmatter 解析"""

import re


def parse_frontmatter(content):
    """解析 node 檔案的 frontmatter，回傳 dict。

    支援 scalar（prenode）和 list（nextnodes, ref_by, tags）格式。
    """
    fm = {}

    fm_match = re.search(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
    if not fm_match:
        return fm
    
    fm_text = fm_match.group(1)

    # Simple scalar fields
    for field in ["type", "timestamp", "node_type", "intensity", "total_mentions"]:
        m = re.search(rf'^{field}:\s*(.+)', fm_text, re.MULTILINE)
        if m:
            fm[field] = m.group(1).strip()

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
            # Check for single-line wikilinks
            links = re.findall(r'\[\[(.+?)\]\]', val)
            if links:
                return links
            # For tags
            if field == "tags":
                tags = [t.strip().strip("'\"") for t in val.strip("[]").split(",")]
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
