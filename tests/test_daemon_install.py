"""HyperMemory 測試 — hm daemon install/uninstall（systemd 服務安裝）

測試 systemd unit file 產生、install、uninstall 邏輯。
"""

import sys
import os
import subprocess
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from hypermemory.commands.daemon import (
    generate_unit_content,
    _unit_path,
    cmd_install,
    cmd_uninstall,
    _hm_home,
)


# ─── Unit file 內容測試 ───


def test_unit_content_has_required_fields():
    """unit file 應包含必要欄位。"""
    content = generate_unit_content(hm_path="hm", pool="/tmp/test-pool")
    assert "[Unit]" in content
    assert "[Service]" in content
    assert "[Install]" in content
    assert "Description=" in content
    assert "ExecStart=" in content
    assert "ExecStop=" in content
    assert "WantedBy=" in content


def test_unit_content_uses_pool():
    """unit file 應包含正確的 pool 路徑。"""
    content = generate_unit_content(hm_path="hm", pool="/tmp/my-pool")
    assert "HYPERMEMORY_POOL=/tmp/my-pool" in content


def test_unit_content_uses_hm_path():
    """unit file 應包含正確的 hm 執行路徑。"""
    content = generate_unit_content(hm_path="/usr/local/bin/hm", pool="/tmp/p")
    assert "ExecStart=/usr/local/bin/hm" in content
    assert "ExecStop=/usr/local/bin/hm" in content


def test_unit_content_restart_policy():
    """應包含 restart 策略。"""
    content = generate_unit_content()
    assert "Restart=on-failure" in content
    assert "RestartSec=" in content


def test_unit_content_network_dependency():
    """應宣告 network 依存。"""
    content = generate_unit_content()
    assert "After=network-online.target" in content
    assert "Wants=network-online.target" in content


def test_unit_path_is_correct():
    """unit file 路徑應在 ~/.config/systemd/user/ 下。"""
    path = _unit_path()
    assert str(path).endswith("/.config/systemd/user/hypermemory.service")
    assert str(path).startswith(str(Path.home()))


# ─── 安裝/卸載測試（dry-run） ───


def _systemctl_available():
    """檢查系統是否支援 systemctl --user。"""
    try:
        result = subprocess.run(
            ["systemctl", "--user", "--version"],
            capture_output=True, timeout=3,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def test_install_dry_run_prints_unit():
    """dry-run 時應輸出 unit file 內容而不實際寫入。"""
    unit_path = _unit_path()
    # 確保測試前檔案不存在
    if unit_path.exists():
        unit_path.unlink()

    cmd_install(None, dry_run=True, hm_path="hm", pool="/tmp/dry-run-pool")

    # 不應實際建立檔案
    assert not unit_path.exists(), "dry-run 不應寫入檔案"


def test_install_dry_run_output_pool_in_content(capsys):
    """dry-run 輸出應包含 pool 路徑。"""
    cmd_install(None, dry_run=True, hm_path="hm", pool="/tmp/output-pool")

    captured = capsys.readouterr()
    assert "/tmp/output-pool" in captured.out


def test_uninstall_dry_run_no_error():
    """dry-run uninstall 應正常執行不報錯（即使 service 不存在）。"""
    try:
        cmd_uninstall(None, dry_run=True)
    except Exception as e:
        assert False, f"dry-run uninstall 不應拋出異常: {e}"


# ─── 真實 systemd 測試（跳過 if systemd unavailable） ───


def test_install_with_systemd():
    """若 systemd 可用，install 應實際上線。"""
    if not _systemctl_available():
        pytest.skip("systemd --user not available")

    unit_path = _unit_path()
    if unit_path.exists():
        unit_path.unlink()

    # 安裝（不 dry-run）
    cmd_install(None, dry_run=False)

    # unit file 應被建立
    assert unit_path.exists()

    # 清理
    cmd_uninstall(None, dry_run=False)
    assert not unit_path.exists()
