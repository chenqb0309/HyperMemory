# Changelog

## 1.1.0 (2026-06-15)

### Added
- `hm daemon` command: built-in scheduler with start/stop/status/log
  - Automatic maintenance schedule (Reflection 23:00, Recalc 03:00, DreamLoop Sunday 04:00)
  - PID file management, graceful SIGTERM shutdown
- 3 new MCP tools: `hm_daemon_status`, `hm_pool_info`, `hm_maintain_now`
  - Total 8 MCP tools available via `hm serve`
- systemd user service support in install.sh
- CHANGELOG.md

### Changed
- MCP transport: Content-Length framing → newline-delimited JSON (Python MCP SDK standard)
- Initialize protocol version: static `"0.1.0"` → echo client requested version
- stdin read: `read(4096)` → `read1(4096)` (non-blocking on open pipes)
- Python requirement lowered from 3.10+ to 3.9+
- MCP server no longer requires `mcp` pip package
- README.md: added daemon section, updated MCP tools list, Hermes config example
- MCP_SETUP.md: updated tools list (5→8), transport description, Hermes config example
- install.sh: daemon service installation step

### Fixed
- MCP handshake failure with Hermes/other MCP SDK clients (protocol version reject + wire format mismatch)

## 1.0.0 (2026-06-11)

- Initial release: CLI tools, core memory system, MCP server
