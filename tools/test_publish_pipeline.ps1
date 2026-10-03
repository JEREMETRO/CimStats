# Read-only release guard checks. No synthetic Git repository, package copying,
# dist promotion, file deletion or real build is performed.
param([string]$PythonExe = '')
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
if (-not $PythonExe) { $PythonExe = Join-Path $env:LOCALAPPDATA 'Programs/Python/Python312/python.exe' }
Set-Location -LiteralPath $repo
$gitIndex = & git -c "safe.directory=$repo" rev-parse --git-path index
if ($LASTEXITCODE -ne 0) { throw 'Cannot locate the current checkout index' }
$gitIndex = if ([IO.Path]::IsPathRooted($gitIndex)) { $gitIndex } else { Join-Path $repo $gitIndex }
$protected = @($gitIndex, (Join-Path $repo 'VERSION'), (Join-Path $repo 'README.md'))
foreach ($name in @('dist/CIM2_SaveStats.exe','archive/versions/v1.0.0/source.zip')) {
    $path = Join-Path $repo $name
    if (Test-Path -LiteralPath $path -PathType Leaf) { $protected += $path }
}
$before = @{}
foreach ($name in $protected) { $before[$name] = (Get-FileHash -LiteralPath $name -Algorithm SHA256).Hash }
foreach ($script in @('build_portable.ps1','publish_release.ps1')) {
    $tokens = $null; $errors = $null
    $ast = [Management.Automation.Language.Parser]::ParseFile((Join-Path $repo $script),[ref]$tokens,[ref]$errors)
    if ($errors.Count) { throw "Syntax error: $script" }
    $unsafe = @($ast.FindAll({param($node) $node -is [Management.Automation.Language.CommandAst] -and $node.GetCommandName() -match '^(Remove-Item|Move-Item|git|gh|Start-Process)$'},$true))
    if ($unsafe.Count) { throw "Unexpected mutation command in $script" }
}
$candidatesExisted = Test-Path -LiteralPath (Join-Path $repo 'build/candidates')
$plan = (& (Join-Path $repo 'build_portable.ps1') | Out-String | ConvertFrom-Json)
if ($plan.build_requested -ne $false -or $plan.public_release_allowed -ne $false) { throw 'Default entry must be preparation only' }
if (-not $candidatesExisted -and (Test-Path -LiteralPath (Join-Path $repo 'build/candidates'))) { throw 'Default entry created a candidate directory' }
$rejected = $false
try { & (Join-Path $repo 'publish_release.ps1') -CandidatePath (Join-Path $repo '../outside-candidate') -PythonExe $PythonExe } catch { $rejected = $true }
if (-not $rejected) { throw 'Outside-project candidate was not rejected' }
foreach ($name in $protected) {
    if ((Get-FileHash -LiteralPath $name -Algorithm SHA256).Hash -ne $before[$name]) { throw "Protected artifact changed: $name" }
}
Write-Host 'Read-only pipeline checks passed: syntax, default no-build, no promotion/deletion/upload, outside-path rejection, protected artifact hashes.'
$global:LASTEXITCODE = 0
