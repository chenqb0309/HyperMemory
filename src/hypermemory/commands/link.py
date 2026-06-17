"""hm link hook — 將 HM 掛接到支援的 agent 框架"""

import os
import sys
from pathlib import Path

HERMES_PLUGIN_DIR = Path.home() / ".hermes" / "plugins" / "hm-loop"

PLUGIN_YAML = """name: hm-loop
version: "1.0"
description: "HyperMemory 自動 hook — 每輪自動 recall/confirm/imprint"
"""

INIT_PY = r'''"""HM Loop Plugin — 橋接 hypermemory.plugin.load() 到 Hermes hook 系統"""
from hypermemory.plugin import load

def register(ctx):
    for name, fn in load().items():
        ctx.register_hook(name, fn)
'''


def run(args):
    if args.link_action != "hook":
        print("目前僅支援 hm link hook")
        sys.exit(1)

    if args.unlink:
        _unlink(args.agent)
    else:
        _link(args.agent)


def _link(agent: str):
    if agent == "hermes":
        _link_hermes()
    else:
        print(f"不支援的 agent: {agent}（目前僅支援 hermes）")
        sys.exit(1)


def _unlink(agent: str):
    if agent == "hermes":
        _unlink_hermes()
    else:
        print(f"不支援的 agent: {agent}（目前僅支援 hermes）")
        sys.exit(1)


def _link_hermes():
    HERMES_PLUGIN_DIR.mkdir(parents=True, exist_ok=True)

    yaml_path = HERMES_PLUGIN_DIR / "plugin.yaml"
    if not yaml_path.exists():
        yaml_path.write_text(PLUGIN_YAML)
        print(f"  建立 {yaml_path}")

    init_path = HERMES_PLUGIN_DIR / "__init__.py"
    if not init_path.exists():
        init_path.write_text(INIT_PY)
        print(f"  建立 {init_path}")

    print()
    print("  ✅ HM plugin 檔案已就緒")
    print()
    print("  請執行以下指令啟用並重啟 Hermes：")
    print()
    print("    hermes plugins enable hm-loop")
    print("    hermes gateway restart")
    print()
    print("  啟用後，HM 會自動在每輪 recall、terminal 後 confirm、對話結束 imprint。")
    print("  移除此橋接：hm link hook --unlink")


def _unlink_hermes():
    if not HERMES_PLUGIN_DIR.exists():
        print("  HM plugin 尚未安裝，無需移除")
        return

    import shutil
    shutil.rmtree(HERMES_PLUGIN_DIR)
    print(f"  移除 {HERMES_PLUGIN_DIR}/")
    print()
    print("  ✅ 已移除 HM plugin 橋接檔案")
    print()
    print("  建議先執行 hermes plugins disable hm-loop 停用 plugin，再重啟。")
    print()
    print("  完整移除步驟：")
    print()
    print("    hermes plugins disable hm-loop")
    print("    hermes gateway restart")
    print(f"    hm link hook --agent hermes --unlink")
