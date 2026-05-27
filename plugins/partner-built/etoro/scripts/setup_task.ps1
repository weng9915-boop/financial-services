# setup_task.ps1 — registers the eToro bot as a Windows Task Scheduler job.
#
# USAGE (run once, in PowerShell as Administrator):
#   cd C:\path\to\financial-services
#   powershell -ExecutionPolicy Bypass -File plugins\partner-built\etoro\scripts\setup_task.ps1
#
# The task fires at 9:45 AM your local time, Mon–Fri.
# If you are NOT in Eastern Time, adjust $TriggerTime below to the
# ET-equivalent in your timezone:
#   ET  → use 09:45
#   CT  → use 08:45
#   MT  → use 07:45
#   PT  → use 06:45
#   UTC → use 13:45
#   SGT → use 21:45
#   JST → use 22:45

$TaskName    = "eToroTradingBot"
$TriggerTime = "09:45"   # <-- change this to your local time equivalent of 9:45 AM ET
$RepoRoot    = (Resolve-Path "$PSScriptRoot\..\..\..\..").Path
$BatFile     = Join-Path $RepoRoot "plugins\partner-built\etoro\scripts\run_bot.bat"

# Verify Python is available
$PythonPath = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $PythonPath) {
    Write-Error "Python not found in PATH. Install from https://www.python.org and re-run."
    exit 1
}
Write-Host "Python found: $PythonPath"

# Verify .env exists
$EnvFile = Join-Path $RepoRoot ".env"
if (-not (Test-Path $EnvFile)) {
    Write-Error ".env file not found at $EnvFile — create it with your eToro credentials."
    exit 1
}
Write-Host ".env found: $EnvFile"

# Install required Python package
Write-Host "Installing requests..."
python -m pip install requests urllib3 --quiet

# Build the scheduled task
$Action   = New-ScheduledTaskAction `
    -Execute "cmd.exe" `
    -Argument "/c `"$BatFile`"" `
    -WorkingDirectory $RepoRoot

$Trigger  = New-ScheduledTaskTrigger `
    -Weekly `
    -DaysOfWeek Monday, Tuesday, Wednesday, Thursday, Friday `
    -At $TriggerTime

$Settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
    -StartWhenAvailable `       # runs at next opportunity if machine was off at trigger time
    -WakeToRun $false `
    -MultipleInstances IgnoreNew

# Remove existing task if present
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

# Register — prompts once for your Windows password so the task runs when locked
Register-ScheduledTask `
    -TaskName $TaskName `
    -Action   $Action `
    -Trigger  $Trigger `
    -Settings $Settings `
    -RunLevel Highest `
    -Force

Write-Host ""
Write-Host "Task registered: '$TaskName'"
Write-Host "Schedule: Mon-Fri at $TriggerTime (local time)"
Write-Host "Logs: $RepoRoot\logs\bot.log"
Write-Host ""
Write-Host "To run manually right now:"
Write-Host "  cmd /c `"$BatFile`""
Write-Host ""
Write-Host "To check the task:"
Write-Host "  Get-ScheduledTask -TaskName '$TaskName'"
Write-Host ""
Write-Host "To remove the task:"
Write-Host "  Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false"
