#requires -Version 5.1
# Run from PowerShell: .\install.ps1
$ErrorActionPreference = 'Stop'

$adtUv = Get-Command uv -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $adtUv) {
    if (-not (Get-Command winget -CommandType Application -ErrorAction SilentlyContinue)) {
        throw 'Install uv first: https://docs.astral.sh/uv/getting-started/installation/'
    }
    $adtAnswer = Read-Host 'uv is required. Install it using WinGet? [Y/n]'
    if ($adtAnswer -notin @('', 'y', 'yes')) {
        Write-Host 'Installation cancelled.'
        return
    }
    & winget install --id astral-sh.uv --exact --source winget
    if ($LASTEXITCODE -ne 0) {
        throw "WinGet failed (exit $LASTEXITCODE). Resolve the error before trying again."
    }
    # Keep the current session entries, including custom SDK locations.
    $env:PATH = $env:PATH + ';' + [Environment]::GetEnvironmentVariable('Path', 'User') +
        ';' + [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $adtUv = Get-Command uv -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $adtUv) {
        throw 'uv was installed. Open a new terminal and run .\install.ps1 again.'
    }
}

Write-Host 'Installing ADT and its runtime dependencies...'
# A project-local cache also works when the default uv cache is not writable.
$adtCache = Join-Path $PSScriptRoot '.adt-local/uv-cache'
& $adtUv.Source --cache-dir $adtCache tool install --python 3.12 --reinstall $PSScriptRoot
if ($LASTEXITCODE -ne 0) {
    throw "ADT installation failed (exit $LASTEXITCODE). Resolve the error before trying again."
}

$adtToolBin = (& $adtUv.Source tool dir --bin | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or -not $adtToolBin) {
    throw 'Cannot determine the uv tool executable directory.'
}
$adtExecutable = Join-Path $adtToolBin 'adt.exe'
& $adtExecutable --version
if ($LASTEXITCODE -ne 0) {
    throw 'The installed ADT executable could not start.'
}
$env:PATH = "$adtToolBin;$env:PATH"

$adtUserPath = [Environment]::GetEnvironmentVariable('Path', 'User')
$adtSavedPaths = ($adtUserPath + ';' + [Environment]::GetEnvironmentVariable('Path', 'Machine')) -split ';'
if ($adtToolBin.TrimEnd('\') -notin @($adtSavedPaths | ForEach-Object { $_.TrimEnd('\') })) {
    $adtAnswer = Read-Host 'Make adt available in future terminals by adding its folder to your user PATH? [Y/n]'
    if ($adtAnswer -in @('', 'y', 'yes')) {
        [Environment]::SetEnvironmentVariable('Path', "$adtToolBin;$adtUserPath".TrimEnd(';'), 'User')
        Write-Host 'User PATH updated. New terminals can also run adt.'
    }
    else {
        Write-Host 'User PATH unchanged. adt is available in this terminal.'
    }
}
Write-Host 'Ready. Type adt to start, or adt --help for direct commands.'
