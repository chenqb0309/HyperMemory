"""hm info — 記憶池健康狀態"""

import sys

from hypermemory.core.pool import resolve_pool, index_path, list_nodes
from hypermemory.core.index import parse_index
from hypermemory.core.node import parse_frontmatter
from hypermemory.core.weight import calc_weight
from hypermemory.core.print import safe_print


def run(args):
    pool = resolve_pool(args.pool)
    idx = index_path(pool)

    if idx.exists():
        with open(idx, encoding="utf-8") as f:
            entries = parse_index(f.read())
    else:
        entries = []

    nodes = list_nodes(pool)
    node_count = len(nodes)

    dead_index = 0
    total_clusters = len(entries)

    for kw_list, node_file in entries:
        np = pool / node_file
        if not np.exists():
            dead_index += 1

    weights = []
    type_counts = {}
    for n in nodes:
        with open(n, encoding="utf-8") as f:
            content = f.read()
        fm = parse_frontmatter(content)
        type_counts[fm.get("node_type", "?")] = type_counts.get(fm.get("node_type", "?"), 0) + 1
        w = calc_weight(
            fm.get("intensity", 1),
            fm.get("total_mentions", 0),
            fm.get("timestamp"),
            node_type=fm.get("node_type", "經驗"),
        )
        weights.append(w)

    high_intensity = sum(1 for n in nodes if (parse_frontmatter(open(n).read())).get("intensity", 0) >= 8)
    high_intensity_pct = round(high_intensity / node_count * 100) if node_count else 0
    avg_weight = sum(weights) / len(weights) if weights else 0

    safe_print(f"Pool: {pool}")
    safe_print()
    safe_print(f"Nodes:         {node_count}")
    safe_print(f"Clusters:      {total_clusters}")
    safe_print(f"  dead refs: {dead_index}  (index points to missing file)")
    safe_print()
    safe_print("Node Types:")
    for t in sorted(type_counts.keys()):
        label = {1: "Root", 2: "Evolution", 3: "Cross-chain"}.get(t, f"T{t}")
        safe_print(f"  {label}:     {type_counts[t]}")
    safe_print()
    safe_print(f"Avg weight:    {avg_weight:.2f}")
    safe_print(f"High intensity (8+): {high_intensity} ({high_intensity_pct}%)")
