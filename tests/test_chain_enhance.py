"""HyperMemory 測試 — ref_by 排序 + 5M1E chain 過濾"""

import sys
import os
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from hypermemory.core.pool import resolve_chain_length
from hypermemory.core.explore import explore_chain


def _chain_pool():
    """建立有鏈結構 + ref_by 的暫存池。"""
    tmp = Path(tempfile.mkdtemp(prefix="hm_test_ref_"))

    # A (intensity=9) → B (intensity=7) → C (intensity=5)
    # A ref_by: D, E
    # D: intensity=3, E: intensity=8
    nodes = {
        "A.md": {
            "intensity": 9, "mentions": 5,
            "prenode": None, "nextnodes": ["B.md"],
            "ref_by": ["D.md", "E.md"],
            "tags": ["test"],
            "dimensions": {"機": "WSL", "料": "Python"},
            "body": "Node A content about WSL Python debugging.",
        },
        "B.md": {
            "intensity": 7, "mentions": 3,
            "prenode": "A.md", "nextnodes": ["C.md"],
            "ref_by": [],
            "tags": ["test"],
            "dimensions": {"機": "WSL", "料": "Python"},
            "body": "Node B follows from A.",
        },
        "C.md": {
            "intensity": 5, "mentions": 1,
            "prenode": "B.md", "nextnodes": [],
            "ref_by": [],
            "tags": ["test"],
            "dimensions": {"機": "Linux", "料": "Bash"},
            "body": "Node C on Linux Bash.",
        },
        "D.md": {
            "intensity": 3, "mentions": 0,
            "prenode": None, "nextnodes": [],
            "ref_by": [],
            "tags": ["old"],
            "body": "Old low-weight node.",
        },
        "E.md": {
            "intensity": 8, "mentions": 2,
            "prenode": None, "nextnodes": [],
            "ref_by": [],
            "tags": ["important"],
            "body": "High-intensity referenced node.",
        },
    }

    for fname, data in nodes.items():
        dims = data.get("dimensions", {})
        dim_lines = "\n".join(f"  {k}: {v}" for k, v in dims.items()) if dims else ""
        refs = data.get("ref_by", [])
        ref_line = "\n".join(f"  - [[{r}]]" for r in refs) if refs else "null"
        nxt = data.get("nextnodes", [])
        nxt_line = "\n".join(f"  - [[{n}]]" for n in nxt) if nxt else "null"
        pre = f"[[{data['prenode']}]]" if data["prenode"] else "null"

        content = f"""---
type: 2
timestamp: 2026-06-01T00:00:00+00:00
node_type: 2
prenode: {pre}
nextnodes:
{nxt_line}
ref_by:
{ref_line}
intensity: {data['intensity']}
total_mentions: {data['mentions']}
tags: [{', '.join(f'"{t}"' for t in data['tags'])}]
dimensions:
{dim_lines}
---

# {fname.replace('.md','')}
{data['body']}
"""
        (tmp / fname).write_text(content)

    (tmp / "index.md").write_text(
        "# Index\n"
        + "\n".join(f"《cluster: [{n.replace('.md','')}]》 → [[{n}]]" for n in nodes)
    )
    return tmp


def test_ref_by_is_list():
    """ref_by 應回傳 list。"""
    pool = _chain_pool()
    from hypermemory.core.node import parse_frontmatter
    content = (pool / "A.md").read_text()
    fm = parse_frontmatter(content)
    assert isinstance(fm.get("ref_by"), list)


def test_chain_length_calculated():
    """resolve_chain_length 應回傳 > 1 的鏈長度。"""
    pool = _chain_pool()
    from hypermemory.core.node import parse_frontmatter

    content = (pool / "A.md").read_text()
    fm = parse_frontmatter(content)
    cl = resolve_chain_length(pool, "A.md", fm)
    # A → B → C = 3 nodes
    assert cl >= 2, f"Chain of 3 should have length >= 2, got {cl}"


def test_explore_with_dimensions():
    """explore_chain 支援 dimensions context 過濾。"""
    pool = _chain_pool()

    # 從 A 出發 forward，限制 context_dims={機: WSL}
    # B (WSL) 應包含、C (Linux) 應被過濾
    result = explore_chain(
        pool, "A.md", direction="forward", depth=5,
        context_dims={"機": "WSL"},
    )
    assert result["found"]
    nodes = [n["node"] for n in result["chain"]]
    assert "B.md" in nodes, "B (WSL) should pass filter"
    assert "C.md" not in nodes, "C (Linux) should be filtered out"


def test_explore_dimensions_all_pass():
    """無 context_dims → 全部通過（不過濾）。"""
    pool = _chain_pool()
    result = explore_chain(pool, "A.md", direction="forward", depth=5)
    assert result["found"]
    nodes = [n["node"] for n in result["chain"]]
    assert "B.md" in nodes
    assert "C.md" in nodes


def test_explore_dimensions_no_match():
    """沒有任和 node 匹配 context → 空 chain。"""
    pool = _chain_pool()
    result = explore_chain(
        pool, "A.md", direction="forward", depth=5,
        context_dims={"料": "Go"},
    )
    assert result["found"]
    assert len(result["chain"]) == 0, "No node should match Go"
