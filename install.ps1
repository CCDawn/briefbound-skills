param(
    [ValidateSet("claude", "codex", "grok", "agents", "codex-agents", "codex-grok", "all")]
    [string]$Agent = "codex",

    [string[]]$Skill,

    [string]$HomeDir,

    [ValidateSet("warn", "disable", "restore", "ignore")]
    [string]$ProcessSkillConflicts = "disable",

    [ValidateSet("warn", "install", "remove", "ignore")]
    [string]$RouterActivation = "install",

    [switch]$List,
    [switch]$DryRun,
    [switch]$VerifyOnly
)

$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $PSCommandPath
$installer = Join-Path $repo "scripts\install_codex_library.py"

$installerArgs = @(
    $installer,
    "--agent", $Agent,
    "--process-skill-conflicts", $ProcessSkillConflicts,
    "--router-activation", $RouterActivation
)
if ($HomeDir) {
    $installerArgs += @("--home", $HomeDir)
}
foreach ($name in $Skill) {
    $installerArgs += @("--skill", $name)
}
if ($List) {
    $installerArgs += "--list"
}
if ($DryRun) {
    $installerArgs += "--dry-run"
}
if ($VerifyOnly) {
    $installerArgs += "--verify-only"
}

if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 @installerArgs
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    & python @installerArgs
} else {
    throw "Python was not found. Install Python 3 or run the installer with an available Python executable."
}

exit $LASTEXITCODE
