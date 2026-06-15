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
