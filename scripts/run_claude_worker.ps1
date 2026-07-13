<#
.SYNOPSIS
Runs a bounded auxiliary Claude worker packet, or previews the invocation with -DryRun.

.DESCRIPTION
TaskId and PromptFile are intentionally required, including for -DryRun. A dry
run still validates that the prompt file is inside `.agent_tasks/<TaskId>/` and
writes only ignored runtime artifacts under that task directory.

.EXAMPLE
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_claude_worker.ps1 -TaskId verify-workflow-stabilization -PromptFile .agent_tasks\verify-workflow-stabilization\prompt.txt -ModelTier flash -WorkerRole "Auxiliary Worker" -ReasoningEffort medium -DryRun
#>

param(
  [Parameter(Mandatory = $true)][string]$TaskId,
  [Parameter(Mandatory = $true)][string]$PromptFile,
  [string]$ModelTier = "default",
  [string]$ModelId = "",
  [string]$WorkerRole = "Auxiliary Worker",
  [string]$ReasoningEffort = "medium",
  [switch]$DryRun,
  [ValidateRange(1, 3600)][int]$HeartbeatIntervalSeconds = 10,
  [ValidateRange(1, 86400)][int]$HeartbeatStaleThresholdSeconds = 30,
  [ValidateRange(1, 86400)][int]$StartupTimeoutSeconds = 30
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$taskRoot = Join-Path $repoRoot ".agent_tasks"
$taskDir = Join-Path $taskRoot $TaskId
$taskPacketPath = Join-Path $taskDir "task_packet.md"
$statusPath = Join-Path $taskDir "worker_status.json"
$heartbeatPath = Join-Path $taskDir "worker_heartbeat.json"
$failureReportPath = Join-Path $taskDir "failure_report.md"
$implementationReportPath = Join-Path $taskDir "implementation_report.md"
$humanObservationPath = Join-Path $taskDir "human_observation.md"
$logPath = Join-Path $taskDir "worker_log.ndjson"
$errorPath = Join-Path $taskDir "worker_error.log"
$testOutputPath = Join-Path $taskDir "test_output.txt"
$stdoutCapturePath = Join-Path $taskDir "worker_stdout.tmp"
$initialDiffSummary = ""
$lastDiffAt = ""
$lastTestOutputAt = ""
$lastProgressSignal = $null
$initialTestOutputLength = 0

if ($TaskId -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$') {
  throw "TaskId must be a safe .agent_tasks folder name: $TaskId"
}

New-Item -ItemType Directory -Force -Path $taskRoot | Out-Null
$taskRootPath = (Resolve-Path -LiteralPath $taskRoot).Path.TrimEnd('\')
$resolvedTaskDirCandidate = [System.IO.Path]::GetFullPath($taskDir)
if (-not ($resolvedTaskDirCandidate.StartsWith($taskRootPath + "\", [System.StringComparison]::OrdinalIgnoreCase))) {
  throw "Task directory must stay under .agent_tasks: $resolvedTaskDirCandidate"
}

New-Item -ItemType Directory -Force -Path $taskDir | Out-Null

function Get-UtcTimestamp {
  return [DateTimeOffset]::UtcNow.ToString("o")
}

function Write-JsonFile {
  param(
    [Parameter(Mandatory = $true)]$InputObject,
    [Parameter(Mandatory = $true)][string]$LiteralPath
  )

  $InputObject | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $LiteralPath -Encoding UTF8
}

function Write-LogEvent {
  param(
    [Parameter(Mandatory = $true)][string]$Type,
    [Parameter(Mandatory = $true)]$Payload
  )

  $event = [ordered]@{
    timestamp = Get-UtcTimestamp
    type = $Type
    payload = $Payload
  }
  Add-Content -LiteralPath $logPath -Encoding UTF8 -Value ($event | ConvertTo-Json -Depth 8 -Compress)
}

function Get-PromptRedactionPlaceholder {
  return "<prompt redacted; chars=$($promptText.Length)>"
}

function Redact-StringValue {
  param(
    [AllowNull()][string]$Value
  )

  if ($null -eq $Value) {
    return $null
  }

  if ([string]::IsNullOrEmpty($Value)) {
    return $Value
  }

  $placeholder = Get-PromptRedactionPlaceholder
  $redacted = $Value
  if (-not [string]::IsNullOrEmpty($promptText)) {
    $redacted = $redacted.Replace($promptText, $placeholder)
  }

  return $redacted
}

function Redact-ObjectValue {
  param(
    [AllowNull()]$Value
  )

  if ($null -eq $Value) {
    return $null
  }

  if ($Value -is [string]) {
    return (Redact-StringValue -Value $Value)
  }

  if ($Value -is [System.Collections.IDictionary]) {
    $copy = [ordered]@{}
    foreach ($key in $Value.Keys) {
      $copy[$key] = Redact-ObjectValue -Value $Value[$key]
    }
    return $copy
  }

  if ($Value -is [System.Collections.IEnumerable] -and -not ($Value -is [string])) {
    $items = New-Object System.Collections.Generic.List[object]
    foreach ($item in $Value) {
      $null = $items.Add((Redact-ObjectValue -Value $item))
    }
    return @($items)
  }

  if ($Value.PSObject -and $Value.PSObject.Properties.Count -gt 0) {
    $copy = [ordered]@{}
    foreach ($property in $Value.PSObject.Properties) {
      $copy[$property.Name] = Redact-ObjectValue -Value $property.Value
    }
    return $copy
  }

  return $Value
}

function ConvertTo-SafeLogLine {
  param(
    [Parameter(Mandatory = $true)][string]$Line
  )

  $redactedLiteral = Redact-StringValue -Value $Line
  try {
    $parsed = $Line | ConvertFrom-Json -ErrorAction Stop
    $safeObject = Redact-ObjectValue -Value $parsed
    return ($safeObject | ConvertTo-Json -Depth 12 -Compress)
  }
  catch {
    return $redactedLiteral
  }
}

function Get-ReportField {
  param(
    [Parameter(Mandatory = $true)][string]$LiteralPath,
    [Parameter(Mandatory = $true)][string]$FieldName
  )

  $pattern = '^\s*-\s*' + [regex]::Escape($FieldName) + '\s*:\s*(.*?)\s*$'
  foreach ($line in Get-Content -LiteralPath $LiteralPath -Encoding UTF8) {
    if ($line -match $pattern) {
      return $Matches[1].Trim()
    }
  }

  return $null
}

function Resolve-TerminalArtifact {
  $hasImplementationReport = Test-Path -LiteralPath $implementationReportPath -PathType Leaf
  $hasFailureReport = Test-Path -LiteralPath $failureReportPath -PathType Leaf

  if ($hasImplementationReport -eq $hasFailureReport) {
    $reason = if ($hasImplementationReport) { "Both terminal reports exist." } else { "No terminal report exists." }
    return [pscustomobject]@{
      valid = $false
      state = "failed"
      failure_class = "artifact_contract"
      message = $reason
    }
  }

  if ($hasImplementationReport) {
    $finalState = Get-ReportField -LiteralPath $implementationReportPath -FieldName "final_state"
    if ($finalState -ne "completed") {
      return [pscustomobject]@{
        valid = $false
        state = "failed"
        failure_class = "artifact_contract"
        message = "implementation_report.md requires final_state: completed."
      }
    }

    return [pscustomobject]@{
      valid = $true
      state = "completed"
      failure_class = $null
      message = "Worker completed with implementation_report.md."
    }
  }

  $finalState = Get-ReportField -LiteralPath $failureReportPath -FieldName "final_state"
  if ($finalState -notin @("stalled", "blocked", "failed")) {
    return [pscustomobject]@{
      valid = $false
      state = "failed"
      failure_class = "artifact_contract"
      message = "failure_report.md requires final_state: stalled, blocked, or failed."
    }
  }

  $failureClass = Get-ReportField -LiteralPath $failureReportPath -FieldName "failure_class"
  return [pscustomobject]@{
    valid = $true
    state = $finalState
    failure_class = if ([string]::IsNullOrWhiteSpace($failureClass)) { $null } else { $failureClass }
    message = "Worker ended as $finalState with failure_report.md."
  }
}

function Write-Status {
  param(
    [Parameter(Mandatory = $true)][string]$State,
    [string]$Phase = $State,
    [Nullable[int]]$ProcessId = $null,
    [Nullable[int]]$ExitCode = $null,
    [string]$Message = "",
    [hashtable]$Extra = @{}
  )

  $artifacts = [ordered]@{
    task_packet = $taskPacketPath
    status = $statusPath
    heartbeat = $heartbeatPath
    human_observation = $humanObservationPath
    log = $logPath
    error = $errorPath
    test_output = $testOutputPath
  }
  if ($State -eq "completed") {
    $artifacts["implementation_report"] = $implementationReportPath
  }
  elseif ($State -in @("failed", "blocked", "stalled")) {
    $artifacts["failure_report"] = $failureReportPath
  }

  $status = [ordered]@{
    packet_id = $TaskId
    worker_role = $WorkerRole
    worker_model = if ([string]::IsNullOrWhiteSpace($ModelId)) { $ModelTier } else { $ModelId }
    reasoning_effort = $ReasoningEffort
    state = $State
    final_state = if ($State -in @("completed", "failed", "blocked", "stalled")) { $State } else { $null }
    phase = $Phase
    dry_run = [bool]$DryRun
    repo_root = $repoRoot
    task_dir = $taskDir
    prompt_file = $PromptFile
    model_tier = $ModelTier
    model_id = $ModelId
    heartbeat_interval_seconds = $HeartbeatIntervalSeconds
    heartbeat_stale_threshold_seconds = $HeartbeatStaleThresholdSeconds
    startup_timeout_seconds = $StartupTimeoutSeconds
    updated_at = Get-UtcTimestamp
    pid = $ProcessId
    exit_code = $ExitCode
    message = $Message
    failure_class = $Extra["failure_class"]
    blocker_kind = $Extra["blocker_kind"]
    last_progress_signal = $Extra["last_progress_signal"]
    summary = @()
    changed_files = @(Get-ChangedFiles)
    verification = @()
    artifacts = $artifacts
  }

  foreach ($key in $Extra.Keys) {
    $status[$key] = $Extra[$key]
  }

  Write-JsonFile -InputObject $status -LiteralPath $statusPath
}

function Write-Heartbeat {
  param(
    [Parameter(Mandatory = $true)][string]$Phase,
    [Nullable[int]]$ProcessId = $null,
    [int]$OutputLines = 0,
    [int]$ErrorLines = 0,
    [string]$LastOutputAt = "",
    [string]$LastErrorAt = "",
    [string]$LastDiffAt = "",
    [string]$LastTestOutputAt = "",
    [AllowNull()][string]$LastProgressSignal = $null
  )

  $heartbeat = [ordered]@{
    packet_id = $TaskId
    worker_role = $WorkerRole
    worker_model = if ([string]::IsNullOrWhiteSpace($ModelId)) { $ModelTier } else { $ModelId }
    reasoning_effort = $ReasoningEffort
    state = if ($Phase -eq "completed" -or $Phase -eq "dry-run") { "completed" } elseif ($Phase -in @("stalled", "blocked", "failed")) { $Phase } else { "busy" }
    phase = $Phase
    dry_run = [bool]$DryRun
    updated_at = Get-UtcTimestamp
    heartbeat_interval_seconds = $HeartbeatIntervalSeconds
    heartbeat_stale_threshold_seconds = $HeartbeatStaleThresholdSeconds
    pid = $ProcessId
    output_lines = $OutputLines
    error_lines = $ErrorLines
    last_output_at = $LastOutputAt
    last_error_at = $LastErrorAt
    last_stream_event_at = $LastOutputAt
    last_diff_at = $LastDiffAt
    last_test_output_at = $LastTestOutputAt
    last_progress_signal = $LastProgressSignal
    blocker_kind = $null
    failure_class = $null
    current_step = $Phase
    changed_files = @(Get-ChangedFiles)
    next_expected_signal = "Final status artifact or another heartbeat within bounded time."
    signal_summary = [ordered]@{
      stdout_fresh = -not [string]::IsNullOrWhiteSpace($LastOutputAt)
      diff_fresh = -not [string]::IsNullOrWhiteSpace($LastDiffAt)
      test_output_fresh = -not [string]::IsNullOrWhiteSpace($LastTestOutputAt)
      child_process_active = $null -ne $ProcessId
    }
  }

  Write-JsonFile -InputObject $heartbeat -LiteralPath $heartbeatPath
}

function Get-GitDiffSummary {
  try {
    $summary = & git -C $repoRoot diff --shortstat 2>$null
    if ($LASTEXITCODE -ne 0 -or $null -eq $summary) {
      return ""
    }
    return ($summary -join " ").Trim()
  }
  catch {
    return ""
  }
}

function Get-ChangedFiles {
  $result = New-Object System.Collections.Generic.List[string]

  try {
    $files = & git -C $repoRoot diff --name-only 2>$null
    if ($LASTEXITCODE -eq 0 -and $null -ne $files) {
      foreach ($file in $files) {
        if (-not [string]::IsNullOrWhiteSpace($file) -and -not $result.Contains($file)) {
          $null = $result.Add($file)
        }
      }
    }
  }
  catch {
  }

  try {
    $statusLines = & git -C $repoRoot status --short --untracked-files=all 2>$null
    if ($LASTEXITCODE -eq 0 -and $null -ne $statusLines) {
      foreach ($line in $statusLines) {
        if ([string]::IsNullOrWhiteSpace($line)) {
          continue
        }

        $candidate = $line
        if ($candidate.Length -ge 3) {
          $candidate = $candidate.Substring(3).Trim()
        }

        if ([string]::IsNullOrWhiteSpace($candidate)) {
          continue
        }

        if ($candidate.Contains(" -> ")) {
          $candidate = ($candidate -split " -> ", 2)[1].Trim()
        }

        if (-not $result.Contains($candidate)) {
          $null = $result.Add($candidate)
        }
      }
    }
  }
  catch {
  }

  return @($result)
}

function Get-FileLengthOrZero {
  param([Parameter(Mandatory = $true)][string]$LiteralPath)

  if (-not (Test-Path -LiteralPath $LiteralPath -PathType Leaf)) {
    return 0
  }

  return (Get-Item -LiteralPath $LiteralPath).Length
}

function Read-NewLines {
  param(
    [Parameter(Mandatory = $true)][string]$LiteralPath,
    [Parameter(Mandatory = $true)][ref]$Position
  )

  if (-not (Test-Path -LiteralPath $LiteralPath)) {
    return @()
  }

  $stream = [System.IO.File]::Open($LiteralPath, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
  try {
    $stream.Seek($Position.Value, [System.IO.SeekOrigin]::Begin) | Out-Null
    $reader = New-Object System.IO.StreamReader($stream, [System.Text.Encoding]::UTF8, $true, 1024, $true)
    try {
      $content = $reader.ReadToEnd()
      $Position.Value = $stream.Position
    }
    finally {
      $reader.Dispose()
    }
  }
  finally {
    $stream.Dispose()
  }

  if ([string]::IsNullOrEmpty($content)) {
    return @()
  }

  return @($content -split "`r?`n" | Where-Object { $_ -ne "" })
}

if (-not (Test-Path -LiteralPath $PromptFile -PathType Leaf)) {
  throw "Prompt file not found: $PromptFile"
}

$promptPath = (Resolve-Path -LiteralPath $PromptFile).Path
$taskDirPath = (Resolve-Path -LiteralPath $taskDir).Path.TrimEnd('\')
if (-not ($promptPath.StartsWith($taskDirPath + "\", [System.StringComparison]::OrdinalIgnoreCase))) {
  throw "PromptFile must be inside the approved task packet directory: $taskDirPath"
}
$PromptFile = $promptPath

$promptText = Get-Content -LiteralPath $promptPath -Raw -Encoding UTF8
$promptRedactionPlaceholder = Get-PromptRedactionPlaceholder
$initialDiffSummary = Get-GitDiffSummary
$initialTestOutputLength = Get-FileLengthOrZero -LiteralPath $testOutputPath

"" | Set-Content -LiteralPath $logPath -Encoding UTF8
"" | Set-Content -LiteralPath $errorPath -Encoding UTF8

$commandArgs = @("-p", $promptText, "--output-format", "stream-json", "--verbose")
if (-not [string]::IsNullOrWhiteSpace($ModelId)) {
  $commandArgs += @("--model", $ModelId)
}
$displayCommandArgs = @("-p", "<prompt redacted; see promptFile>", "--output-format", "stream-json", "--verbose")
if (-not [string]::IsNullOrWhiteSpace($ModelId)) {
  $displayCommandArgs += @("--model", $ModelId)
}

Write-Status -State "busy" -Phase "setup" -Message "Wrapper initialized."
Write-Heartbeat -Phase "setup"
  Write-LogEvent -Type "wrapper.started" -Payload ([ordered]@{
    command = "claude"
    arguments = $displayCommandArgs
    prompt_file = $promptPath
    prompt_characters = $promptText.Length
    prompt_preview = $promptRedactionPlaceholder
    dry_run = [bool]$DryRun
  })

if ($DryRun) {
  $preview = [ordered]@{
    repo_root = $repoRoot
    task_dir = $taskDir
    command = "claude"
    arguments = $displayCommandArgs
    prompt_characters = $promptText.Length
    prompt_preview = $promptRedactionPlaceholder
    dry_run = $true
  }
  $preview | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $testOutputPath -Encoding UTF8
  Write-Heartbeat -Phase "dry-run" -OutputLines 1
  Write-LogEvent -Type "wrapper.dry_run" -Payload $preview
  Write-Status -State "completed" -Phase "dry-run" -ExitCode 0 -Message "Dry run completed without launching claude."
  exit 0
}

foreach ($terminalReportPath in @($implementationReportPath, $failureReportPath)) {
  if (Test-Path -LiteralPath $terminalReportPath -PathType Leaf) {
    Remove-Item -LiteralPath $terminalReportPath -Force
  }
}

if (Test-Path -LiteralPath $stdoutCapturePath) {
  Remove-Item -LiteralPath $stdoutCapturePath -Force
}

$stdoutPosition = 0L
$errorPosition = 0L
$stdoutLineCount = 0
$errorLineCount = 0
$lastOutputAt = ""
$lastErrorAt = ""
$claudeProcess = $null

Push-Location $repoRoot
try {
  $claudeProcess = Start-Process -FilePath "claude" -ArgumentList $commandArgs -WorkingDirectory $repoRoot -RedirectStandardOutput $stdoutCapturePath -RedirectStandardError $errorPath -NoNewWindow -PassThru
  Write-Status -State "busy" -Phase "spawned" -ProcessId $claudeProcess.Id -Message "Claude worker process started."
  Write-Heartbeat -Phase "spawned" -ProcessId $claudeProcess.Id
  Write-LogEvent -Type "wrapper.spawned" -Payload ([ordered]@{
    pid = $claudeProcess.Id
    workingDirectory = $repoRoot
  })

  $startupDeadline = (Get-Date).AddSeconds($StartupTimeoutSeconds)
  while (-not $claudeProcess.HasExited) {
    $stdoutLines = Read-NewLines -LiteralPath $stdoutCapturePath -Position ([ref]$stdoutPosition)
    foreach ($line in $stdoutLines) {
      Add-Content -LiteralPath $logPath -Encoding UTF8 -Value (ConvertTo-SafeLogLine -Line $line)
      $stdoutLineCount += 1
      $lastOutputAt = Get-UtcTimestamp
    }

    $errorLines = Read-NewLines -LiteralPath $errorPath -Position ([ref]$errorPosition)
    if ($errorLines.Count -gt 0) {
      $errorLineCount += $errorLines.Count
      $lastErrorAt = Get-UtcTimestamp
    }

    $phase = if ((Get-Date) -lt $startupDeadline -and $stdoutLineCount -eq 0) { "starting" } else { "running" }
    $currentDiffSummary = Get-GitDiffSummary
    if ($currentDiffSummary -ne $initialDiffSummary -and -not [string]::IsNullOrWhiteSpace($currentDiffSummary)) {
      $lastDiffAt = Get-UtcTimestamp
      $lastProgressSignal = "git_diff"
      $initialDiffSummary = $currentDiffSummary
    }
    $currentTestOutputLength = Get-FileLengthOrZero -LiteralPath $testOutputPath
    if ($currentTestOutputLength -gt $initialTestOutputLength) {
      $lastTestOutputAt = Get-UtcTimestamp
      $lastProgressSignal = "test_output"
      $initialTestOutputLength = $currentTestOutputLength
    }
    if (-not [string]::IsNullOrWhiteSpace($lastOutputAt)) {
      $lastProgressSignal = "stream_event"
    }
    Write-Heartbeat -Phase $phase -ProcessId $claudeProcess.Id -OutputLines $stdoutLineCount -ErrorLines $errorLineCount -LastOutputAt $lastOutputAt -LastErrorAt $lastErrorAt -LastDiffAt $lastDiffAt -LastTestOutputAt $lastTestOutputAt -LastProgressSignal $lastProgressSignal
    Write-Status -State "busy" -Phase $phase -ProcessId $claudeProcess.Id -Message "Claude worker process is active." -Extra @{
      output_lines = $stdoutLineCount
      error_lines = $errorLineCount
      last_output_at = $lastOutputAt
      last_error_at = $lastErrorAt
      last_diff_at = $lastDiffAt
      last_test_output_at = $lastTestOutputAt
      last_progress_signal = $lastProgressSignal
      failure_class = $null
      blocker_kind = $null
    }

    Start-Sleep -Seconds $HeartbeatIntervalSeconds
  }

  $claudeProcess.WaitForExit()

  $remainingStdout = Read-NewLines -LiteralPath $stdoutCapturePath -Position ([ref]$stdoutPosition)
  foreach ($line in $remainingStdout) {
    Add-Content -LiteralPath $logPath -Encoding UTF8 -Value (ConvertTo-SafeLogLine -Line $line)
    $stdoutLineCount += 1
    $lastOutputAt = Get-UtcTimestamp
  }

  $remainingErrors = Read-NewLines -LiteralPath $errorPath -Position ([ref]$errorPosition)
  if ($remainingErrors.Count -gt 0) {
    $errorLineCount += $remainingErrors.Count
    $lastErrorAt = Get-UtcTimestamp
  }

  $terminal = Resolve-TerminalArtifact
  if (-not $terminal.valid) {
    $artifactExitCode = 2
    Write-Heartbeat -Phase "failed" -ProcessId $claudeProcess.Id -OutputLines $stdoutLineCount -ErrorLines $errorLineCount -LastOutputAt $lastOutputAt -LastErrorAt $lastErrorAt -LastDiffAt $lastDiffAt -LastTestOutputAt $lastTestOutputAt -LastProgressSignal $lastProgressSignal
    Write-LogEvent -Type "wrapper.artifact_contract_failed" -Payload ([ordered]@{
      pid = $claudeProcess.Id
      process_exit_code = $claudeProcess.ExitCode
      message = $terminal.message
    })
    Write-Status -State "failed" -Phase "failed" -ProcessId $claudeProcess.Id -ExitCode $artifactExitCode -Message $terminal.message -Extra @{
      output_lines = $stdoutLineCount
      error_lines = $errorLineCount
      last_output_at = $lastOutputAt
      last_error_at = $lastErrorAt
      last_diff_at = $lastDiffAt
      last_test_output_at = $lastTestOutputAt
      last_progress_signal = $lastProgressSignal
      failure_class = "artifact_contract"
      blocker_kind = "terminal_report"
    }
    exit $artifactExitCode
  }

  Write-Heartbeat -Phase $terminal.state -ProcessId $claudeProcess.Id -OutputLines $stdoutLineCount -ErrorLines $errorLineCount -LastOutputAt $lastOutputAt -LastErrorAt $lastErrorAt -LastDiffAt $lastDiffAt -LastTestOutputAt $lastTestOutputAt -LastProgressSignal $lastProgressSignal
  Write-LogEvent -Type "wrapper.terminal" -Payload ([ordered]@{
    pid = $claudeProcess.Id
    process_exit_code = $claudeProcess.ExitCode
    final_state = $terminal.state
    output_lines = $stdoutLineCount
    error_lines = $errorLineCount
  })
  Write-Status -State $terminal.state -Phase $terminal.state -ProcessId $claudeProcess.Id -ExitCode $claudeProcess.ExitCode -Message $terminal.message -Extra @{
    output_lines = $stdoutLineCount
    error_lines = $errorLineCount
    last_output_at = $lastOutputAt
    last_error_at = $lastErrorAt
    last_diff_at = $lastDiffAt
    last_test_output_at = $lastTestOutputAt
    last_progress_signal = $lastProgressSignal
    failure_class = $terminal.failure_class
    blocker_kind = $null
  }
  if ($claudeProcess.ExitCode -ne 0) {
    exit $claudeProcess.ExitCode
  }
}
catch {
  $message = $_.Exception.Message
  Add-Content -LiteralPath $errorPath -Encoding UTF8 -Value $message
  Write-LogEvent -Type "wrapper.exception" -Payload ([ordered]@{
    message = $message
  })
  $pidValue = if ($null -ne $claudeProcess) { $claudeProcess.Id } else { $null }
  Write-Heartbeat -Phase "failed" -ProcessId $pidValue -OutputLines $stdoutLineCount -ErrorLines $errorLineCount -LastOutputAt $lastOutputAt -LastErrorAt $lastErrorAt -LastDiffAt $lastDiffAt -LastTestOutputAt $lastTestOutputAt -LastProgressSignal $lastProgressSignal
  Write-Status -State "failed" -Phase "failed" -ProcessId $pidValue -Message $message -Extra @{
    output_lines = $stdoutLineCount
    error_lines = $errorLineCount
    last_output_at = $lastOutputAt
    last_error_at = $lastErrorAt
    last_diff_at = $lastDiffAt
    last_test_output_at = $lastTestOutputAt
    last_progress_signal = $lastProgressSignal
    failure_class = "environment_runtime"
    blocker_kind = "wrapper_exception"
  }
  throw
}
finally {
  Pop-Location
  if (Test-Path -LiteralPath $stdoutCapturePath) {
    Remove-Item -LiteralPath $stdoutCapturePath -Force
  }
}
