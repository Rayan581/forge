# FORGE ML pipeline for Windows PowerShell. Run from the repository root (X:\FAST Tasks\FYP):
#   .\ml\run_pipeline.ps1 player            # one stage
#   .\ml\run_pipeline.ps1 all               # stages 1-7
#   .\ml\run_pipeline.ps1 smoke             # dry run of every stage on synthetic data
#   .\ml\run_pipeline.ps1 ppo -Config ml\configs\default.json -Set "ppo.total_timesteps=200000"
param(
    [Parameter(Mandatory = $true)][string]$Stage,
    [string]$Config = "ml\configs\default.json",
    [string[]]$Set = @()
)
$ErrorActionPreference = "Stop"
$extra = @()
foreach ($s in $Set) { $extra += @("--set", $s) }
if ($Stage -eq "smoke") {
    python -m ml.pipeline all --config ml\configs\smoke.json @extra
} elseif ($Stage -eq "test") {
    python -m pytest ml\tests -v
} else {
    python -m ml.pipeline $Stage --config $Config @extra
}
exit $LASTEXITCODE
