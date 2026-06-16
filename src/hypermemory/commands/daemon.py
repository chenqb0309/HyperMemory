"""hm daemon — 內建排程器"""

import os
import sys
import time
import signal
import json
import subprocess
from pathlib import Path
from datetime import datetime, timezone, timedelta

from hypermemory.core.pool import resolve_pool, ensure_pool


def _hm_home():
    return Path(os.environ.get("HYPERMEMORY_HOME", Path.home() / ".hypermemory"))


PID_FILE = "daemon.pid"
LOG_FILE = "daemon.log"
SCHED_FILE = "daemon_schedule.json"

# 預設排程（24h 制）
DEFAULT_SCHEDULE = {
    "recalc": {"hour": 3, "minute": 0, "dow": None},        # 每天 03:00
    "dreamloop": {"hour": 4, "minute": 0, "dow": 6},         # 每週日 04:00 (6 = Sunday)
    "reflect": {"hour": 23, "minute": 0, "dow": None},       # 每天 23:00
}

ACTION_NAMES = {
    "recalc": "Recalc (權重重算)",
    "dreamloop": "DreamLoop (關鍵字去重)",
    "reflect": "Reflection (自動刻錄)",
}

SYSTEMD_UNIT_DIR = Path.home() / ".config" / "systemd" / "user"
SYSTEMD_UNIT_NAME = "hypermemory.service"


def _pid_path():
    return _hm_home() / PID_FILE


def _log_path():
    return _hm_home() / LOG_FILE


def _sched_path():
    return _hm_home() / SCHED_FILE


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        _log_path().parent.mkdir(parents=True, exist_ok=True)
        with open(_log_path(), "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def run_maintain(pool, action):
    """Execute a maintain action by importing and calling directly."""
    from hypermemory.commands.maintain import _recalc, _dreamloop, _reflect

    log(f"=== Starting {ACTION_NAMES.get(action, action)} ===")
    try:
        if action == "recalc":
            _recalc(pool)
        elif action == "dreamloop":
            _dreamloop(pool)
        elif action == "reflect":
            _reflect(pool, days=3)
        elif action == "all":
            _recalc(pool)
            _dreamloop(pool)
            _reflect(pool, days=3)
        log(f"=== Finished {ACTION_NAMES.get(action, action)} ===")
    except Exception as e:
        log(f"ERROR in {action}: {e}")
        import traceback
        for line in traceback.format_exc().split("\n"):
            if line.strip():
                log(f"  {line}")


def next_run(schedule):
    """Calculate next run time for each task and return sorted list."""
    now = datetime.now()
    results = []

    for action, cfg in schedule.items():
        target = now.replace(hour=cfg["hour"], minute=cfg["minute"], second=0, microsecond=0)

        # If today's time has passed, move to next day
        if target <= now:
            target += timedelta(days=1)

        # If DOW is specified, advance to next matching DOW
        if cfg["dow"] is not None:
            days_ahead = cfg["dow"] - target.weekday()
            # Note: datetime uses Monday=0, Sunday=6
            if days_ahead <= 0:
                days_ahead += 7
            target += timedelta(days=days_ahead)

        results.append((target, action))

    return sorted(results)


def daemon_loop(pool, schedule=None):
    """Main daemon loop."""
    if schedule is None:
        schedule = DEFAULT_SCHEDULE

    log("Daemon started")
    log(f"Schedule: {json.dumps(schedule, ensure_ascii=False)}")
    log(f"Pool: {pool}")

    # Save schedule to file for status queries
    sched_path = _sched_path()
    try:
        sched_path.parent.mkdir(parents=True, exist_ok=True)
        with open(sched_path, "w") as f:
            json.dump(schedule, f, ensure_ascii=False)
    except OSError:
        pass

    # Graceful shutdown flag — use file-based sentinel for reliability
    stop_sentinel = _pid_path().with_suffix(".stop")
    shutdown = [False]

    def on_signal(signum, frame):
        """Signal handler — create sentinel file for main loop to detect."""
        shutdown[0] = True
        try:
            stop_sentinel.touch()
        except OSError:
            pass
        log(f"Received signal {signum}, shutting down...")

    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)

    while not shutdown[0]:
        try:
            now = datetime.now()
            tasks = next_run(schedule)

            if not tasks:
                time.sleep(60)
                continue

            next_time, next_action = tasks[0]

            # Wait until it's precisely time to execute next_action.
            # next_time is computed ONCE per cycle — we never recompute it
            # mid-wait, which avoids the race where a recomputed target
            # is always "past" due to <= comparison in next_run().
            while not shutdown[0] and not stop_sentinel.exists():
                now = datetime.now()
                delay = (next_time - now).total_seconds()

                if delay <= 0:
                    break  # time to execute

                # Cap at 60s for responsive shutdown
                time.sleep(min(delay, 60.0))

            if shutdown[0] or stop_sentinel.exists():
                break

            run_maintain(pool, next_action)
            # loop re-enters -> recompute next schedule naturally
        except KeyboardInterrupt:
            shutdown[0] = True
            break
        except Exception as e:
            log(f"Daemon error: {e}")
            time.sleep(60)

    # Cleanup sentinel
    try:
        stop_sentinel.unlink(missing_ok=True)
    except OSError:
        pass
    log("Daemon stopped")


def cmd_start(args):
    """hm daemon start"""
    pid_path = _pid_path()

    # Check if already running
    if pid_path.exists():
        try:
            pid = int(pid_path.read_text().strip())
            os.kill(pid, 0)  # Check if alive
            print(f"Daemon already running (PID {pid})")
            print(f"  Stop: hm daemon stop")
            return
        except (OSError, ValueError):
            # PID file stale
            pid_path.unlink(missing_ok=True)

    # Ensure hm_home
    _hm_home().mkdir(parents=True, exist_ok=True)

    # Fork
    pid = os.fork()
    if pid > 0:
        # Parent
        pid_path.write_text(str(pid))
        print(f"Daemon started (PID {pid})")
        print(f"  Log: {_log_path()}")
        return

    # Child (daemon)
    # Detach from parent
    os.setsid()

    # Redirect stdio
    sys.stdin.close()
    sys.stdout = open(os.devnull, "w")
    sys.stderr = open(os.devnull, "w")

    # Resolve pool
    pool = resolve_pool(args.pool)
    ensure_pool(pool)

    daemon_loop(pool)


def cmd_stop(args):
    """hm daemon stop"""
    import time as _t
    pid_path = _pid_path()
    stop_sentinel = pid_path.with_suffix(".stop")

    if not pid_path.exists():
        print("Daemon not running (no PID file)")
        return

    try:
        pid = int(pid_path.read_text().strip())

        # Create stop sentinel first
        try:
            stop_sentinel.touch()
        except OSError:
            pass

        # Send SIGTERM
        os.kill(pid, signal.SIGTERM)

        # Wait up to 10 seconds for graceful shutdown
        for _ in range(20):
            import time as _t
            _t.sleep(0.5)
            try:
                os.kill(pid, 0)
            except OSError:
                # Process exited
                break
        else:
            # Still alive, force kill
            try:
                os.kill(pid, signal.SIGKILL)
                _t.sleep(0.5)
            except OSError:
                pass

        pid_path.unlink(missing_ok=True)
        stop_sentinel.unlink(missing_ok=True)
        print(f"Daemon (PID {pid}) stopped")
    except OSError as e:
        print(f"Error: {e}")
        pid_path.unlink(missing_ok=True)
        stop_sentinel.unlink(missing_ok=True)


def cmd_status(args):
    """hm daemon status"""
    pid_path = _pid_path()
    log_path = _log_path()

    if pid_path.exists():
        try:
            pid = int(pid_path.read_text().strip())
            os.kill(pid, 0)
            print(f"Status: RUNNING (PID {pid})")
        except OSError:
            print("Status: STOPPED (stale PID file)")
            pid_path.unlink(missing_ok=True)
            return
    else:
        print("Status: STOPPED")
        return

    # Show schedule
    sched_path = _sched_path()
    if sched_path.exists():
        try:
            with open(sched_path) as f:
                schedule = json.load(f)
            from datetime import datetime, timedelta
            now = datetime.now()
            tasks = []
            for action, cfg in schedule.items():
                target = now.replace(hour=cfg["hour"], minute=cfg["minute"], second=0, microsecond=0)
                if target <= now:
                    target += timedelta(days=1)
                if cfg["dow"] is not None:
                    days_ahead = cfg["dow"] - target.weekday()
                    if days_ahead <= 0:
                        days_ahead += 7
                    target += timedelta(days=days_ahead)
                tasks.append((target, action))

            print(f"Schedule:")
            for t, a in sorted(tasks):
                label = ACTION_NAMES.get(a, a)
                remaining = (t - now).total_seconds()
                h = int(remaining // 3600)
                m = int((remaining % 3600) // 60)
                if h > 0:
                    print(f"  {label}: {t.strftime('%Y-%m-%d %H:%M')} ({h}h{m}m from now)")
                else:
                    print(f"  {label}: {t.strftime('%Y-%m-%d %H:%M')} ({m}m from now)")
        except Exception as e:
            print(f"  Schedule info unavailable: {e}")

    # Last log lines
    if log_path.exists():
        try:
            with open(log_path) as f:
                lines = f.readlines()
            if len(lines) > 5:
                lines = lines[-5:]
            print(f"\nRecent log:")
            for line in lines:
                print(f"  {line.rstrip()}")
        except OSError:
            pass


def cmd_log(args):
    """hm daemon log"""
    log_path = _log_path()

    if not log_path.exists():
        print("No daemon log found.")
        return

    try:
        with open(log_path) as f:
            sys.stdout.write(f.read())
    except OSError as e:
        print(f"Error reading log: {e}")


def _unit_path() -> Path:
    return SYSTEMD_UNIT_DIR / SYSTEMD_UNIT_NAME


def generate_unit_content(hm_path: str | None = None, pool: str | None = None) -> str:
    """產生 systemd unit file 內容。

    Parameters
    ----------
    hm_path : str | None
        hm 執行檔路徑（預設從 sys.argv 推測）
    pool : str | None
        記憶池路徑（預設用 resolve_pool）

    Returns
    -------
    str : systemd unit file 內容
    """
    if hm_path is None:
        hm_path = os.path.abspath(sys.argv[0]) if sys.argv[0] and sys.argv[0] != "-m" else "hm"
    if pool is None:
        pool = str(resolve_pool(None))

    return f"""\
[Unit]
Description=HyperMemory Daemon — AI 記憶放大器排程器
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart={hm_path} daemon start
ExecStop={hm_path} daemon stop
Restart=on-failure
RestartSec=30
Environment=HYPERMEMORY_POOL={pool}

[Install]
WantedBy=default.target
"""


def cmd_install(args, dry_run=False, hm_path=None, pool=None):
    """hm daemon install

    dry_run=True 時只輸出 unit file 內容，不實際寫入或呼叫 systemctl。
    hm_path 和 pool 用於測試注入。
    """
    # Check CLI --dry-run flag
    if args is not None and hasattr(args, 'dry_run') and args.dry_run:
        dry_run = True

    unit_path = _unit_path()
    if hm_path is None:
        hm_path = os.path.abspath(sys.argv[0]) if sys.argv[0] and sys.argv[0] != "-m" else "hm"
    if pool is None:
        pool = str(resolve_pool(None))

    content = generate_unit_content(hm_path=hm_path, pool=pool)

    if dry_run:
        print(content)
        return

    # Write unit file
    unit_path.parent.mkdir(parents=True, exist_ok=True)
    unit_path.write_text(content, encoding="utf-8")
    print(f"Unit file created: {unit_path}")

    # systemctl enable + start
    try:
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
        result = subprocess.run(
            ["systemctl", "--user", "enable", "--now", SYSTEMD_UNIT_NAME],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            print("Daemon installed and started as systemd user service.")
        else:
            print(f"systemctl output: {result.stderr.strip() or result.stdout.strip()}")
            print("You may need to run: systemctl --user enable --now hypermemory.service")
    except FileNotFoundError:
        print("systemctl not found — unit file created manually.")
        print(f"To enable: systemctl --user enable --now {unit_path}")

    print()
    print("  Status: systemctl --user status hypermemory.service")
    print("  Logs:   journalctl --user -u hypermemory.service -f")
    print("  Stop:   systemctl --user stop hypermemory.service")
    print("  Start:  systemctl --user start hypermemory.service")


def cmd_uninstall(args, dry_run=False):
    """hm daemon uninstall"""
    unit_path = _unit_path()

    if not unit_path.exists() and not dry_run:
        print("HyperMemory service is not installed.")
        return

    if not dry_run:
        # Disable + stop
        try:
            subprocess.run(
                ["systemctl", "--user", "disable", "--now", SYSTEMD_UNIT_NAME],
                capture_output=True,
            )
        except FileNotFoundError:
            pass

        # Remove unit file
        if unit_path.exists():
            unit_path.unlink()
            print(f"Unit file removed: {unit_path}")

        # daemon-reload
        try:
            subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
        except FileNotFoundError:
            pass

    print("HyperMemory systemd service uninstalled.")


def run(args):
    """Route to subcommand handler."""
    action = args.daemon_action

    if action == "start":
        cmd_start(args)
    elif action == "stop":
        cmd_stop(args)
    elif action == "status":
        cmd_status(args)
    elif action == "log":
        cmd_log(args)
    elif action == "install":
        cmd_install(args)
    elif action == "uninstall":
        cmd_uninstall(args)
    else:
        print(f"Unknown daemon action: {action}")
        sys.exit(1)
