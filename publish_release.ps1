param(
    [Parameter(Mandatory=$true)][string]$CandidatePath,
    [string]$PythonExe = '',
    [switch]$CheckPublicRelease
)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not $PythonExe) {
    if ($env:CIMSTATS_BUILD_PYTHON) { $PythonExe = $env:CIMSTATS_BUILD_PYTHON }
    else { $PythonExe = Join-Path $env:LOCALAPPDATA 'Programs/Python/Python312/python.exe' }
}
# Read-only successor to the legacy directory promotion script. No dist moves,
# recursive source archive, deletion, git mutation or GitHub upload is available.
$arguments = @('-B','tools/candidate_package.py','verify','--candidate',$CandidatePath)
if ($CheckPublicRelease) { $arguments += '--public' }
& $PythonExe @arguments
if ($LASTEXITCODE -ne 0) { throw 'Candidate/public-release verification did not pass. No publication or promotion occurred.' }
Write-Host 'Local candidate integrity verified. Submit this exact package for user review before any separate GitHub publication.'
