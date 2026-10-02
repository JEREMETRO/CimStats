param(
    [string]$Version = '0.1.0',
    [string]$PythonExe = '',
    [string]$SourceManifest = '',
    [string]$ManagedRoot = '',
    [string]$BaseAssembly = '',
    [string]$CandidateName = '',
    [switch]$Build,
    [switch]$LocalReviewWithGameRuntime
)
$ErrorActionPreference = 'Stop'
$workspaceRoot = (Resolve-Path -LiteralPath $PSScriptRoot).Path
Set-Location -LiteralPath $workspaceRoot
function Assert-BuildPath([string]$Path) {
    $full = [IO.Path]::GetFullPath($Path)
    if (-not $full.StartsWith($workspaceRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'Path outside project' }
    $cursor = $full
    while ($cursor -and $cursor -ne $workspaceRoot) {
        if ((Test-Path -LiteralPath $cursor) -and ((Get-Item -LiteralPath $cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw "Redirected path: $cursor" }
        $cursor = Split-Path -Parent $cursor
    }
    return $full
}
if ($Version -ne '0.1.0') { throw 'This reviewed candidate workflow targets CimStats 0.1.0' }
if (-not $Build) {
    [ordered]@{
        build_requested = $false
        requested_version = $Version
        current_version = (Get-Content -LiteralPath (Join-Path $workspaceRoot 'VERSION') -Raw).Trim()
        layout = 'onedir; package/CimStats/CimStats.exe plus _internal'
        output_parent = 'build/candidates'
        source_freeze_required = $true
        local_game_runtime_requires_explicit_review_flag = $true
        old_dist_and_archives_preserved = $true
        public_release_allowed = $false
        next = 'After the coordinator freezes integrated source, supply -Build -SourceManifest -ManagedRoot -BaseAssembly -LocalReviewWithGameRuntime'
    } | ConvertTo-Json
    return
}
if ((Get-Content -LiteralPath (Join-Path $workspaceRoot 'VERSION') -Raw).Trim() -ne $Version) { throw 'Integrate approved VERSION before building' }
if (-not $LocalReviewWithGameRuntime) { throw 'Current parser requires game runtime. Only an explicitly marked LOCAL REVIEW build is available.' }
if (-not $SourceManifest -or -not $ManagedRoot -or -not $BaseAssembly) { throw 'Supply the frozen source manifest, managed dependency directory and audited original assembly' }
$SourceManifest = Assert-BuildPath $(if ([IO.Path]::IsPathRooted($SourceManifest)) { $SourceManifest } else { Join-Path $workspaceRoot $SourceManifest })
$managedSource = (Resolve-Path -LiteralPath $ManagedRoot).Path
$baseSource = (Resolve-Path -LiteralPath $BaseAssembly).Path
$expectedBase = '2BD1CA1353C228FBBCC04DF2355D9CBC545F29DDD06EC1C10A6DD62D7BFDA4D2'
if ((Get-FileHash -LiteralPath $baseSource -Algorithm SHA256).Hash -ne $expectedBase) { throw 'Base assembly differs from the audited original; never substitute a modded installation file' }
if (-not $PythonExe) {
    if ($env:CIMSTATS_BUILD_PYTHON) { $PythonExe = $env:CIMSTATS_BUILD_PYTHON }
    else { $PythonExe = Join-Path $env:LOCALAPPDATA 'Programs/Python/Python312/python.exe' }
}
$PythonExe = (Resolve-Path -LiteralPath $PythonExe).Path
& $PythonExe -B tools/candidate_package.py check-freeze --source-manifest $SourceManifest
if ($LASTEXITCODE -ne 0) { throw 'Source snapshot missing or changed; no build started' }
& $PythonExe -B -c 'import PyInstaller,dnfile,PySide6,pythonnet; print("Build modules available")'
if ($LASTEXITCODE -ne 0) { throw 'Build dependencies unavailable; no installation attempted' }
if (-not $CandidateName) { $CandidateName = "CimStats-$Version-review-" + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N').Substring(0,8) }
if ($CandidateName -notmatch '^CimStats-0\.1\.0-review-[A-Za-z0-9-]+$') { throw 'Invalid unique local candidate name' }
$candidateRoot = Assert-BuildPath (Join-Path $workspaceRoot "build/candidates/$CandidateName")
if (Test-Path -LiteralPath $candidateRoot) { throw 'Candidate exists; choose a new name. It will not be overwritten.' }
$null = New-Item -ItemType Directory -Path $candidateRoot
$staging = Assert-BuildPath (Join-Path $candidateRoot 'runtime-staging')
$stageManaged = Join-Path $staging 'Managed'
$null = New-Item -ItemType Directory -Path $stageManaged
$managedNames = & $PythonExe -B -c 'import sys,json; sys.path.insert(0,"tools"); from candidate_package import MANAGED_NAMES; print(json.dumps(MANAGED_NAMES))'
if ($LASTEXITCODE -ne 0) { throw 'Cannot read reviewed Managed allowlist' }
$runtimeInputRows = @()
foreach ($name in ($managedNames | ConvertFrom-Json)) {
    $source = if ($name -eq 'Assembly-CSharp.dll') { $baseSource } else { Join-Path $managedSource $name }
    if (-not (Test-Path -LiteralPath $source -PathType Leaf) -or ((Get-Item -LiteralPath $source -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw "Missing or redirected runtime input: $name" }
    $before = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash
    $destination = Join-Path $stageManaged $name
    Copy-Item -LiteralPath $source -Destination $destination
    if ((Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash -ne $before -or (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash -ne $before) { throw "Runtime input changed while staging: $name" }
    $runtimeInputRows += [ordered]@{ name = $name; sha256 = $before.ToLowerInvariant(); publicly_cleared = $false }
}
$runtimeInputRows | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $candidateRoot 'runtime-inputs.json') -Encoding utf8
$environmentNames = @('CIM2_BUILD_MANAGED_ROOT','CIM2_ASSEMBLY_SOURCE','CIM2_PROBE_OUTPUT','CIM2_BUILD_PROBE_PATH','CIMSTATS_LOCAL_REVIEW_BUILD','PYINSTALLER_CONFIG_DIR','PYTHONIOENCODING','PYTHONDONTWRITEBYTECODE')
$previousEnvironment = @{}
foreach ($name in $environmentNames) { $previousEnvironment[$name] = [Environment]::GetEnvironmentVariable($name,'Process') }
try {
    $env:CIM2_BUILD_MANAGED_ROOT = $stageManaged
    $env:CIM2_ASSEMBLY_SOURCE = (Join-Path $stageManaged 'Assembly-CSharp.dll')
    $env:CIM2_PROBE_OUTPUT = (Join-Path $staging 'Assembly-CSharp.probe.dll')
    $env:CIM2_BUILD_PROBE_PATH = $env:CIM2_PROBE_OUTPUT
    $env:CIMSTATS_LOCAL_REVIEW_BUILD = '1'
    $env:PYINSTALLER_CONFIG_DIR = (Join-Path $candidateRoot 'pyinstaller-cache')
    $env:PYTHONIOENCODING = 'utf-8'
    $env:PYTHONDONTWRITEBYTECODE = '1'
    & $PythonExe -B src/patch_singleton_probe.py
    if ($LASTEXITCODE -ne 0) { throw 'Fresh staged probe generation failed' }
    $workPath = Assert-BuildPath (Join-Path $candidateRoot 'pyinstaller-work')
    $outputRoot = Assert-BuildPath (Join-Path $candidateRoot 'package')
    & $PythonExe -B -m PyInstaller --workpath $workPath --distpath $outputRoot CIM2_SaveStats.spec
    if ($LASTEXITCODE -ne 0) { throw 'Directory candidate build failed; evidence remains in its unique directory' }
    $package = Join-Path $outputRoot 'CimStats'
    foreach ($name in @('README.md','LICENSE','THIRD_PARTY_NOTICES.md')) { Copy-Item -LiteralPath (Join-Path $workspaceRoot $name) -Destination (Join-Path $package $name) }
    & $PythonExe -B tools/candidate_package.py finalize --candidate $candidateRoot --source-manifest $SourceManifest
    if ($LASTEXITCODE -ne 0) { throw 'Exact candidate inventory/source verification failed' }
    & $PythonExe -B tools/candidate_package.py verify --candidate $candidateRoot
    if ($LASTEXITCODE -ne 0) { throw 'Candidate integrity verification failed' }
    Write-Host "LOCAL REVIEW ONLY: $candidateRoot"
    Write-Host 'Game runtime is listed by path and SHA-256 in review-inventory.json. Public release remains blocked pending review.'
} finally {
    foreach ($name in $environmentNames) { [Environment]::SetEnvironmentVariable($name,$previousEnvironment[$name],'Process') }
    # Retain stage, caches, logs and failed outputs. No directory deletion or promotion.
}
