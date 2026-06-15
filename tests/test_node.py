"""HyperMemory 核心測試 — node"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from hypermemory.core.node import parse_frontmatter, extract_title, extract_body_link_section


SAMPLE_NODE = """---
type: episodic_memory
timestamp: 2026-06-11T17:00:00+08:00
node_type: 2
prenode: [[2026-06-10-parent.md]]
nextnodes:
  - [[2026-06-12-child-a.md]]
  - [[2026-06-12-child-b.md]]
ref_by: null
intensity: 7
total_mentions: 2
tags: [hypermemory, test]
---

# Test Node Title

## 關聯

- 前驅：[[2026-06-10-parent.md]]
- 後繼：[[2026-06-12-child-a.md]]、[[2026-06-12-child-b.md]]

## 正文

This is the body content.
"""

SAMPLE_NODE_LIST_NEXTNODES = """---
type: episodic_memory
timestamp: 2026-06-15T10:00:00+08:00
node_type: 3
prenode: [[parent.md]]
nextnodes:
  - [[child-a.md]]
  - [[child-b.md]]
ref_by: null
intensity: 5
total_mentions: 1
tags: [test]
---
"""


def test_parse_frontmatter_basic():
    fm = parse_frontmatter(SAMPLE_NODE)
    assert fm.get("type") == "episodic_memory"
    assert fm.get("node_type") == 2
    assert fm.get("intensity") == 7
    assert fm.get("total_mentions") == 2
    assert fm.get("prenode") == "2026-06-10-parent.md"


def test_parse_nextnodes():
    fm = parse_frontmatter(SAMPLE_NODE)
    assert "2026-06-12-child-a.md" in fm.get("nextnodes", [])
    assert "2026-06-12-child-b.md" in fm.get("nextnodes", [])
    assert len(fm.get("nextnodes", [])) == 2


def test_parse_ref_by_null():
    fm = parse_frontmatter(SAMPLE_NODE)
    assert fm.get("ref_by") == []


def test_parse_tags():
    fm = parse_frontmatter(SAMPLE_NODE)
    assert "hypermemory" in fm.get("tags", [])
    assert "test" in fm.get("tags", [])


def test_parse_list_format_nextnodes():
    fm = parse_frontmatter(SAMPLE_NODE_LIST_NEXTNODES)
    nn = fm.get("nextnodes", [])
    assert len(nn) == 2
    assert "child-a.md" in nn
    assert "child-b.md" in nn


def test_extract_title():
    assert extract_title(SAMPLE_NODE) == "Test Node Title"


def test_extract_title_fallback():
    """H2 heading 作為 fallback"""
    content = "## Fallback Title\n\nbody"
    assert extract_title(content) == "Fallback Title"


def test_extract_title_none():
    assert extract_title("no heading here") == "(untitled)"


def test_extract_body_link_section():
    links = extract_body_link_section(SAMPLE_NODE)
    assert links is not None
    assert "前驅" in links
    assert "後繼" in links


def test_parse_no_frontmatter():
    content = "# Just content\n\nNo frontmatter here."
    fm = parse_frontmatter(content)
    assert fm == {}
