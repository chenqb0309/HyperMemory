"""hm log — Session log 操作"""

import sys

from hypermemory.core.log import capture, recent, stats as log_stats


def run(args):
    action = args.log_action
    if action == "capture":
        text = " ".join(args.text) if args.text else sys.stdin.read().strip()
        if not text:
            print("No content to capture.")
            return
        entry = capture(text, tags=args.tag or [])
        print(f"Captured ({entry['timestamp'][:19]})")

    elif action == "recent":
        entries = recent(days=args.days)
        if not entries:
            print(f"No log entries in the last {args.days} days.")
            return
        print(f"Recent {args.days}-day log ({len(entries)} entries):")
        print()
        for e in entries[-20:]:
            ts = e.get("timestamp", "")[:16]
            content = e.get("content", "")[:120].replace("\n", " ")
            tags = f" [{', '.join(e.get('tags', []))}]" if e.get("tags") else ""
            print(f"  {ts}  {content}{tags}")

    elif action == "stats":
        s = log_stats(days=args.days)
        print(f"Log stats (last {args.days} days):")
        print(f"  Total entries: {s['total_entries']}")
        print(f"  Days covered:  {s['days_covered']}")
