# Observational Windows hook template for Agent Speed Layer v0.1.1.
# This template logs a diagnostic result. It does not replace host context,
# approve tools, block tools, or install itself.
param(
    [string]$Python = "python.exe",
    [string]$RawStore = "$env:USERPROFILE\.agent-speed-layer\raw"
)

$ErrorActionPreference = "Stop"
$utf8 = New-Object System.Text.UTF8Encoding($false)
[Console]::InputEncoding = $utf8
[Console]::OutputEncoding = $utf8
$OutputEncoding = $utf8
$env:AGENT_SPEED_RAW_STORE = $RawStore
$payload = [Console]::In.ReadToEnd()
$payload | & $Python -X utf8 (Join-Path $PSScriptRoot "copilot_filter_hook.py")
exit $LASTEXITCODE

# Configure only after review against the installed host contract.
# Do not register this script as an automatic context-replacement hook.
