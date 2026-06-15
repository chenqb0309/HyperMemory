"""HyperMemory 核心 — 安全輸出（跨平台 Unicode）"""

import sys

_CP950 = (sys.platform == "win32" and sys.stdout.encoding and
          sys.stdout.encoding.lower() in ("cp950", "cp936", "big5", "gbk"))


def safe_print(*args, sep=" ", end="\n", **kwargs):
    """print 的安全版本。Windows cp950 遇到無法顯示的字元時自動降級。"""
    if not _CP950:
        print(*args, sep=sep, end=end, **kwargs)
        return
    text = sep.join(str(a) for a in args) + end
    try:
        print(text, end="", **kwargs)
    except UnicodeEncodeError:
        sys.stdout.buffer.write(text.encode("utf-8", errors="replace"))
