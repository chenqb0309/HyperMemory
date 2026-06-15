#!/usr/bin/env python3
"""HyperMemory CLI — hm 指令入口"""

import argparse
import sys
import os
from hypermemory.core.pool import ensure_pool


def build_parser():
    parser = argparse.ArgumentParser(
        prog="hm",
        description="HyperMemory — AI 記憶放大器 CLI",
    )
    parser.add_argument(
        "--pool",
        help=(
            "記憶池路徑。預設 ~/.hypermemory/pools/default/，"
            "第一次使用時自動建立。"
            "也可透過 HYPERMEMORY_POOL 環境變數設定。"
        ),
        default=None,
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # hm list
    list_p = subparsers.add_parser("list", help="列出所有 cluster 與當前 node")
    list_p.set_defaults(func="list_cmd")

    # hm recall
    recall_p = subparsers.add_parser("recall", help="關鍵字匹配回憶")
    recall_p.add_argument("keywords", nargs="+", help="查詢關鍵詞")
    recall_p.add_argument("--dry-run", action="store_true", help="不更新 total_mentions")
    recall_p.set_defaults(func="recall")

    # hm inspect
    inspect_p = subparsers.add_parser("inspect", help="檢視單一 node")
    inspect_p.add_argument("node", help="node 檔名（如 2026-06-11-buildout.md）")
    inspect_p.add_argument("--chain", action="store_true", help="走訪整條鏈")
    inspect_p.set_defaults(func="inspect")

    # hm imprint
    imprint_p = subparsers.add_parser("imprint", help="從檔案刻錄新 node")
    imprint_p.add_argument("file", help="含有 frontmatter 的 markdown 檔案路徑")
    imprint_p.add_argument("--name", help="記憶池中的檔名（預設與來源同檔名）")
    imprint_p.add_argument("--force", action="store_true", help="覆蓋已存在的 node")
    imprint_p.set_defaults(func="imprint")

    # hm serve
    serve_p = subparsers.add_parser("serve", help="啟動 MCP server（stdio 協定）")
    serve_p.set_defaults(func="serve")

    return parser


def main():
    parser = build_parser()

    # Allow --pool before or after subcommand
    pool_value = os.environ.get("HYPERMEMORY_POOL")
    filtered_argv = []
    skip_next = False
    for i, arg in enumerate(sys.argv[1:]):
        if skip_next:
            skip_next = False
            continue
        if arg == "--pool" and i + 1 < len(sys.argv[1:]):
            pool_value = sys.argv[1:][i + 1]
            skip_next = True
        elif arg.startswith("--pool="):
            pool_value = arg.split("=", 1)[1]
        else:
            filtered_argv.append(arg)

    args = parser.parse_args(filtered_argv)
    args.pool = pool_value

    # Auto-create pool directory if it doesn't exist
    from hypermemory.core.pool import resolve_pool
    pool_path = resolve_pool(args.pool)
    ensure_pool(pool_path)
    args.pool = str(pool_path)

    # Route to command handler
    if args.func == "serve":
        from hypermemory.mcp_server import main as mcp_main
        mcp_main(pool=args.pool)
    elif args.func == "list_cmd":
        from hypermemory.commands.list_cmd import run
    elif args.func == "recall":
        from hypermemory.commands.recall import run
    elif args.func == "inspect":
        from hypermemory.commands.inspect import run
    elif args.func == "imprint":
        from hypermemory.commands.imprint import run
    else:
        parser.print_help()
        sys.exit(1)

    run(args)


if __name__ == "__main__":
    main()
