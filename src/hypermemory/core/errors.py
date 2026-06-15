"""HyperMemory 核心 — 統一錯誤處理"""

import sys


class HMError(Exception):
    """HyperMemory 基礎異常"""
    pass


class PoolNotFoundError(HMError):
    def __init__(self, path):
        super().__init__(f"記憶池不存在：{path}")


class IndexNotFoundError(HMError):
    def __init__(self, path):
        super().__init__(f"Index 不存在：{path}")


class NodeNotFoundError(HMError):
    def __init__(self, name):
        super().__init__(f"Node 不存在：{name}")


class InvalidFrontmatterError(HMError):
    def __init__(self, errors):
        super().__init__(f"Frontmatter 驗證失敗：{'；'.join(errors)}")


def die(msg, exit_code=1):
    """統一的錯誤輸出"""
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(exit_code)
