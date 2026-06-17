"""hm think — 習慣性回想（委派至 HMTools）"""

from hypermemory.core.pool import resolve_pool
from hypermemory.core.hm_tools import HMTools
from hypermemory.core.weight import format_score


def run(args):
    pool = resolve_pool(args.pool)
    tools = HMTools(str(pool))
    query = " ".join(args.query)
    result = tools.think(query, dry_run=getattr(args, "dry_run", False))

    if not result.get("found"):
        print("No relevant experience found.")
        return

    best = result["result"]

    print(f"Related experience found (newest):")
    print()
    print(f"  Title:      {best['title']}")
    print(f"  Node:       {best['node']}")
    print(f"  Type:       T{best.get('type', '?')}")
    print(f"  Strength:   {best.get('intensity', '?')}/10 (weight: {format_score(best.get('weight', 0))})")
    print(f"  Maturation: {best.get('maturation', 0)} (P={best.get('maturation_detail', {}).get('positive_events', 0)}"
          f"/N={best.get('maturation_detail', {}).get('negative_events', 0)})")
    if best.get("tags"):
        print(f"  Tags:       {', '.join(best['tags'])}")
    if best.get("dimensions"):
        dim_str = ", ".join(f"{k}={v}" for k, v in best["dimensions"].items())
        print(f"  Dimensions: {dim_str}")
    print(f"  Date:       {(best.get('timestamp') or '')[:19]}")

    # Chain info
    pre = best.get("prenode")
    if pre:
        print(f"  ↑ Chain:   {pre}")
    nexts = best.get("nextnodes", [])
    if nexts:
        print(f"  ↓ Chain:   {', '.join(nexts[:3])}" + (" ..." if len(nexts) > 3 else ""))

    # Body preview
    summary = best.get("summary", "")
    if summary:
        print(f"\n{summary}")

    # Suggestions
    suggestions = best.get("suggestions", [])
    if suggestions:
        s_str = ", ".join(s["title"][:25] for s in suggestions[:3])
        print(f"  Related: {s_str}" + (" ..." if len(suggestions) > 3 else ""))

    # Pending skills hint
    ps = best.get("pending_skills", 0)
    if ps > 0:
        print(f"\n  ⚠ {ps} skill-ready node(s) pending — run 'hm maintain muscle'")
