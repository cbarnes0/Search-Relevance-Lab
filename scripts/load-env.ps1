# Load KEY=VALUE pairs from the repo-root .env into the current PowerShell
# session, so host-side tools (eval runner, ad-hoc scripts) see the same
# values compose gives the containers.
#
# Must be DOT-SOURCED so the variables land in your session, not a child
# scope that vanishes when the script ends:
#
#   . .\scripts\load-env.ps1

$envFile = Join-Path $PSScriptRoot "..\.env"
if (-not (Test-Path $envFile)) {
    Write-Error ".env not found at $envFile"
    return
}

Get-Content $envFile | ForEach-Object {
    $line = $_.Trim()
    if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
        $name, $value = $line -split "=", 2
        Set-Item -Path "env:$($name.Trim())" -Value $value.Trim().Trim('"').Trim("'")
    }
}
Write-Host "Loaded .env into session: $((Get-Content $envFile | Where-Object { $_ -match '^\s*[^#].*=' }).Count) variables"
