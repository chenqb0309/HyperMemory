#!/usr/bin/env bash
set -euo pipefail

# HyperMemory 安裝腳本
# 用法: curl -fsSL https://raw.githubusercontent.com/chenqb0309/HyperMemory/main/install.sh | bash

REPO_URL="https://github.com/chenqb0309/HyperMemory.git"
INSTALL_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/hypermemory"
BIN_DIR="${XDG_BIN_HOME:-$HOME/.local/bin}"
PYTHON=""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }

# --- Find Python ---
find_python() {
    for cmd in python3 python; do
        if command -v "$cmd" &>/dev/null; then
            ver=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0")
            major="${ver%.*}"
            minor="${ver#*.}"
            if [ "$major" -ge 3 ] && [ "$minor" -ge 9 ]; then
                PYTHON="$cmd"
                return 0
            fi
        fi
    done
    return 1
}

# --- Detect OS ---
detect_os() {
    case "$(uname -s)" in
        Linux*)  echo "linux" ;;
        Darwin*) echo "macos" ;;
        MINGW*|MSYS*) echo "windows" ;;
        *)       echo "unknown" ;;
    esac
}

# --- Main ---
main() {
    echo ""
    echo "  HyperMemory Installer"
    echo "  ===================="
    echo ""

    OS=$(detect_os)
    info "Detected OS: $OS"

    # 1. Check Python
    if ! find_python; then
        error "Python 3.9+ not found. Please install Python 3.9 or later."
        exit 1
    fi
    info "Found: $PYTHON ($("$PYTHON" --version 2>&1))"

    # 2. Clone or update repo
    if [ -d "$INSTALL_DIR" ]; then
        info "Updating existing installation at $INSTALL_DIR"
        cd "$INSTALL_DIR"
        git pull --ff-only 2>/dev/null || warn "git pull failed, using existing files"
    else
        info "Cloning HyperMemory to $INSTALL_DIR"
        mkdir -p "$(dirname "$INSTALL_DIR")"
        git clone "$REPO_URL" "$INSTALL_DIR"
    fi

    cd "$INSTALL_DIR"

    # 3. Create venv with uv (preferred) or venv
    VENV_DIR="$INSTALL_DIR/.venv"
    if command -v uv &>/dev/null; then
        info "Creating venv with uv..."
        uv venv "$VENV_DIR" 2>/dev/null || "$PYTHON" -m venv "$VENV_DIR"
    else
        info "Creating venv with python3 -m venv..."
        "$PYTHON" -m venv "$VENV_DIR"
    fi

    # 4. Install package
    info "Installing HyperMemory..."
    if [ -f "$VENV_DIR/bin/activate" ]; then
        source "$VENV_DIR/bin/activate"
    elif [ -f "$VENV_DIR/Scripts/activate" ]; then
        source "$VENV_DIR/Scripts/activate"
    fi
    pip install -e . 2>/dev/null || "$PYTHON" -m pip install -e .

    # 5. Create hm symlink
    mkdir -p "$BIN_DIR"
    HM_SRC="$VENV_DIR/bin/hm"
    if [ ! -f "$HM_SRC" ]; then
        HM_SRC="$VENV_DIR/Scripts/hm"
    fi
    if [ -f "$HM_SRC" ]; then
        ln -sf "$HM_SRC" "$BIN_DIR/hm" 2>/dev/null || warn "Could not create symlink to $BIN_DIR/hm"
        info "hm command linked to $BIN_DIR/hm"
    else
        # Fallback: wrapper script
        cat > "$BIN_DIR/hm" << WRAPPER
#!/usr/bin/env bash
exec "$VENV_DIR/bin/python" -m hypermemory "\$@"
WRAPPER
        chmod +x "$BIN_DIR/hm"
        info "hm wrapper created at $BIN_DIR/hm"
    fi

    # 6. Create default pool
    mkdir -p "$HOME/.hypermemory/pools/default"
    if [ ! -f "$HOME/.hypermemory/pools/default/index.md" ]; then
        echo "# HyperMemory Pool Index" > "$HOME/.hypermemory/pools/default/index.md"
    fi

    # 7. PATH提示
    case ":$PATH:" in
        *":$BIN_DIR:"*) ;;
        *) warn "Add $BIN_DIR to your PATH to use 'hm' directly"
           warn "  echo 'export PATH=\"\$PATH:$BIN_DIR\"' >> ~/.bashrc" ;;
    esac

    echo ""
    info "HyperMemory installed successfully!"
    echo ""
    echo "  hm list         查看 cluster"
    echo "  hm think <query> 習慣性回想"
    echo "  hm info         記憶池狀態"
    echo "  hm serve        啟動 MCP server"
    echo ""
    echo "  完整文件: https://github.com/chenqb0309/HyperMemory"
}

main
