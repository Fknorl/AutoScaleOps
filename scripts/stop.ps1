# ═══════════════════════════════════════════════════════════════════════════
# AutoScaleOps - Stop Script
# ═══════════════════════════════════════════════════════════════════════════
# Usage: .\scripts\stop.ps1

param(
    [switch]$StopMinikube = $false   # Pass -StopMinikube to also stop the cluster
)

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Yellow
Write-Host "║             🛑 AutoScaleOps - Stopping System               ║" -ForegroundColor Yellow
Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Yellow
Write-Host ""

# ─── Read Instance ID ────────────────────────────────────────────────────────
$instanceFile = "$env:USERPROFILE\.autoscaleops\instance.json"

if (Test-Path $instanceFile) {
    $instanceData = Get-Content $instanceFile | ConvertFrom-Json
    $INSTANCE_ID  = $instanceData.instance_id
    $NAMESPACE    = $instanceData.namespace
    $PROFILE      = "autoscaleops-$INSTANCE_ID"
} else {
    Write-Host "⚠️  Instance file not found, stopping all services..." -ForegroundColor Yellow
    $PROFILE = $null
}

# ─── Step 1: Stop Dashboard ───────────────────────────────────────────────────
Write-Host "┌─────────────────────────────────────────────────────────────┐" -ForegroundColor DarkGray
Write-Host "│ Step 1/3: Stopping Dashboard...                             │" -ForegroundColor DarkGray
Write-Host "└─────────────────────────────────────────────────────────────┘" -ForegroundColor DarkGray

$streamlitProcs = Get-Process -Name "streamlit" -ErrorAction SilentlyContinue
if ($streamlitProcs) {
    $streamlitProcs | Stop-Process -Force
    Write-Host "  ✅ Dashboard stopped" -ForegroundColor Green
} else {
    Write-Host "  ℹ️  Dashboard was not running" -ForegroundColor DarkGray
}

# ─── Step 2: Stop Port Forwards ──────────────────────────────────────────────
Write-Host ""
Write-Host "┌─────────────────────────────────────────────────────────────┐" -ForegroundColor DarkGray
Write-Host "│ Step 2/3: Stopping port forwards...                         │" -ForegroundColor DarkGray
Write-Host "└─────────────────────────────────────────────────────────────┘" -ForegroundColor DarkGray

$kubectlProcs = Get-Process -Name "kubectl" -ErrorAction SilentlyContinue
if ($kubectlProcs) {
    $kubectlProcs | Stop-Process -Force
    Write-Host "  ✅ Port forwards stopped" -ForegroundColor Green
} else {
    Write-Host "  ℹ️  No port forwards were running" -ForegroundColor DarkGray
}

# ─── Step 3: Stop Minikube (Optional) ────────────────────────────────────────
Write-Host ""
Write-Host "┌─────────────────────────────────────────────────────────────┐" -ForegroundColor DarkGray
Write-Host "│ Step 3/3: Minikube...                                       │" -ForegroundColor DarkGray
Write-Host "└─────────────────────────────────────────────────────────────┘" -ForegroundColor DarkGray

if ($StopMinikube -and $PROFILE) {
    Write-Host "  ⏳ Stopping Minikube cluster: $PROFILE ..." -ForegroundColor Yellow
    minikube stop -p $PROFILE
    Write-Host "  ✅ Minikube stopped" -ForegroundColor Green
} else {
    Write-Host "  ℹ️  Minikube left running (use -StopMinikube flag to stop it)" -ForegroundColor DarkGray
    Write-Host "     Next start will be faster!" -ForegroundColor DarkGray
}

# ─── Summary ─────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Yellow
Write-Host "║              🛑 AutoScaleOps Stopped                        ║" -ForegroundColor Yellow
Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Yellow
Write-Host ""
Write-Host "  To start again : .\scripts\start.ps1" -ForegroundColor DarkGray
Write-Host "  To also stop cluster: .\scripts\stop.ps1 -StopMinikube" -ForegroundColor DarkGray
Write-Host ""