# HyperMemory Windows Installer
# 用法: powershell -c "irm https://raw.githubusercontent.com/chenqb0309/HyperMemory/main/install.ps1 | iex"

$REPO_URL = "https://github.com/chenqb0309/HyperMemory.git"
$INSTALL_DIR = "$env:USERPROFILE\source\HyperMemory"

Write-Host "`n  HyperMemory Installer (Windows)" -ForegroundColor Green
Write-Host "  ==============================`n"

# 1. Check Python
$python = Get-Command "python" -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "[ERROR] Python not found. Please install Python 3.9+ from python.org" -ForegroundColor Red
    exit 1
}
$ver = & python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
Write-Host "[INFO] Found Python $ver" -ForegroundColor Green

# 2. Clone repo
if (Test-Path $INSTALL_DIR) {
    Write-Host "[INFO] Updating existing installation..." -ForegroundColor Green
    Set-Location $INSTALL_DIR
    git pull --ff-only 2>$null
} else {
    Write-Host "[INFO] Cloning HyperMemory to $INSTALL_DIR" -ForegroundColor Green
    git clone $REPO_URL $INSTALL_DIR
    Set-Location $INSTALL_DIR
}

# 3. Install
Write-Host "[INFO] Installing HyperMemory..." -ForegroundColor Green
python -m pip install -e .

# 4. Create default pool
$poolDir = "$env:USERPROFILE\.hypermemory\pools\default"
if (-not (Test-Path $poolDir)) {
    New-Item -ItemType Directory -Path $poolDir -Force | Out-Null
    "# HyperMemory Pool Index" | Out-File "$poolDir\index.md" -Encoding UTF8
}

Write-Host "`n[INFO] HyperMemory installed successfully!" -ForegroundColor Green
Write-Host "`n  hm list         查看 cluster"
Write-Host "  hm think <query> 習慣性回想"
Write-Host "  hm info         記憶池狀態"
Write-Host "  hm serve        啟動 MCP server"
Write-Host "`n  完整文件: https://github.com/chenqb0309/HyperMemory"
