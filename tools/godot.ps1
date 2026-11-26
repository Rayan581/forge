param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$GodotArgs
)

$GodotExe = "X:\Softwares\Godot_v4.7.2-stable_win64.exe\Godot_v4.7.2-stable_win64.exe"

if (-not (Test-Path $GodotExe)) {
    Write-Host "Godot executable not found: $GodotExe" -ForegroundColor Red
    exit 1
}

& $GodotExe @GodotArgs
exit $LASTEXITCODE