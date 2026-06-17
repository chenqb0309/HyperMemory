"""hm recall — 關鍵字匹配回憶（委派至 HMTools）"""

from hypermemory.core.pool import resolve_pool
from hypermemory.core.hm_tools import HMTools


def run(args):
    pool = resolve_pool(args.pool)
    tools = HMTools(str(pool))

    keywords = " ".join(args.keywords)
    result = tools.recall(keywords, dry_run=getattr(args, "dry_run", False))

    if not result.get("found"):
        print("No matching memories found.")
        if result.get("background"):
            print("(matched from archived background data)")
        return

    print(f"Found {result['total']} result(s):")
    print()

    for i, n in enumerate(result["results"]):
        ts_display = n.get("timestamp", "")[:10] if n.get("timestamp") else "(no date)"
        tags_str = ", ".join(n.get("tags", [])[:3]) if n.get("tags") else ""
        print(f"{i+1}. {n.get('title', '?')}")
        print(f"   Node: {n['node']}")
        print(f"   Type: T{n.get('type', '?')}  Intensity: {n.get('intensity', '?')}  "
              f"Weight: {n.get('weight', '?')}  Date: {ts_display}")
        if tags_str:
            print(f"   Tags: {tags_str}")
        # Chain info
        pre = n.get("prenode")
        if pre:
            print(f"   ↑ {pre}")
        nexts = n.get("nextnodes", [])
        if nexts:
            print(f"   ↓ {', '.join(nexts[:3])}" + (" ..." if len(nexts) > 3 else ""))
        # Suggestions
        suggestions = n.get("suggestions", [])
        if suggestions:
            s_str = ", ".join(s["title"][:20] for s in suggestions[:2])
            print(f"   → {s_str}" + (" ..." if len(suggestions) > 2 else ""))
        print()

    # Display pending skills
    ps = result.get("pending_skills", 0)
    if ps > 0:
        print(f"  ⚠ {ps} skill-ready node(s) pending — run 'hm maintain muscle'")
