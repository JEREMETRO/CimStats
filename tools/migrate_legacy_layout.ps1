# One-time migration of the audited 2026-09-25 layout. No user data is deleted.
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
Set-Location -LiteralPath $repo
function Inside([string]$Relative) {
    $full = [IO.Path]::GetFullPath((Join-Path $repo $Relative))
    if (-not $full.StartsWith($repo + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'Path escapes repository' }
    $cursor = $full
    while ($cursor -and $cursor -ne $repo) {
        if ((Test-Path -LiteralPath $cursor) -and ((Get-Item -LiteralPath $cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw "Redirected path: $cursor" }
        $cursor = Split-Path -Parent $cursor
    }
    return $full
}
$running = @(Get-CimInstance Win32_Process -Filter "Name='CIM2_SaveStats.exe'" | Where-Object { $_.ExecutablePath -and $_.ExecutablePath.StartsWith($repo + '\', [StringComparison]::OrdinalIgnoreCase) })
if ($running.Count) { throw 'Close SaveStats before migrating its jobs' }
$recordPath = Inside 'jobs/migrated/2026-09-25/migration.json'
if (Test-Path -LiteralPath $recordPath) { throw 'Migration ledger already exists; inspect instead of repeating' }
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $recordPath) | Out-Null
$records = [Collections.Generic.List[object]]::new()
function Record([object]$Entry) {
    $records.Add($Entry)
    ConvertTo-Json -InputObject @($records.ToArray()) -Depth 6 | Set-Content -LiteralPath $recordPath -Encoding utf8
}
foreach ($relative in @('dist/jobs', 'dist/v0.5.0/jobs', 'dist/repaired/jobs', 'archive/versions/v0.4-schedule-editor/package/jobs', 'archive/versions/v0.5.0/package/jobs')) {
    $source = Inside $relative
    if (-not (Test-Path -LiteralPath $source)) { continue }
    $destination = Inside ('jobs/migrated/2026-09-25/' + $relative.Replace('/', '__'))
    if (Test-Path -LiteralPath $destination) { throw 'Migration target exists' }
    $entries = @(Get-ChildItem -LiteralPath $source -Recurse -Force)
    if (@($entries | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint }).Count) { throw 'Source contains redirected paths' }
    $hashes = @($entries | Where-Object { -not $_.PSIsContainer } | ForEach-Object {
        [ordered]@{ path = $_.FullName.Substring($source.Length + 1); bytes = $_.Length; sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash }
    })
    $entry = [ordered]@{ source = $relative; destination = $destination.Substring($repo.Length + 1); status = 'prepared'; files = $hashes }
    Record $entry
    Move-Item -LiteralPath $source -Destination $destination
    foreach ($file in $hashes) {
        if ((Get-FileHash -LiteralPath (Join-Path $destination $file.path) -Algorithm SHA256).Hash -ne $file.sha256) { throw 'Migration checksum mismatch' }
    }
    $entry.status = 'verified'
    ConvertTo-Json -InputObject @($records.ToArray()) -Depth 6 | Set-Content -LiteralPath $recordPath -Encoding utf8
}
$buildArchive = Inside 'archive/builds/2026-09-25-layout-cleanup'
New-Item -ItemType Directory -Force -Path $buildArchive | Out-Null
$candidate = Inside 'dist/repaired'
if (Test-Path -LiteralPath $candidate) {
    $destination = Inside 'archive/builds/2026-09-25-layout-cleanup/repaired'
    if (Test-Path -LiteralPath $destination) { throw 'Candidate archive exists' }
    $hash = (Get-FileHash -LiteralPath (Join-Path $candidate 'CIM2_SaveStats.exe')).Hash
    Move-Item -LiteralPath $candidate -Destination $destination
    if ((Get-FileHash -LiteralPath (Join-Path $destination 'CIM2_SaveStats.exe')).Hash -ne $hash) { throw 'Candidate archive mismatch' }
    Record ([ordered]@{ source = 'dist/repaired'; destination = 'archive/builds/2026-09-25-layout-cleanup/repaired'; status = 'verified'; sha256 = $hash })
}
foreach ($pair in @(
    @('dist/CIM2_SaveStats.exe', 'archive/versions/v0.4-schedule-editor/package/CIM2_SaveStats.exe'),
    @('dist/CIM2_SaveStats_README.md', 'archive/versions/v0.4-schedule-editor/package/README.md'),
    @('dist/v0.5.0/CIM2_SaveStats.exe', 'archive/versions/v0.5.0/package/CIM2_SaveStats.exe'),
    @('dist/v0.5.0/CIM2_SaveStats_README.md', 'archive/versions/v0.5.0/package/README.md')
)) {
    $source = Inside $pair[0]
    if (-not (Test-Path -LiteralPath $source)) { continue }
    $archived = Inside $pair[1]
    $hash = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash
    if ($hash -eq (Get-FileHash -LiteralPath $archived -Algorithm SHA256).Hash) {
        Remove-Item -LiteralPath $source
        Record ([ordered]@{ source = $pair[0]; duplicate_of = $pair[1]; status = 'duplicate_removed'; sha256 = $hash })
    } else {
        $destination = Inside ('archive/builds/2026-09-25-layout-cleanup/' + $pair[0].Replace('/', '__'))
        if (Test-Path -LiteralPath $destination) { throw 'Unexpected file already archived' }
        Move-Item -LiteralPath $source -Destination $destination
        Record ([ordered]@{ source = $pair[0]; destination = $destination.Substring($repo.Length + 1); status = 'preserved_different_file'; sha256 = $hash })
    }
}
$oldFolder = Inside 'dist/v0.5.0'
if ((Test-Path -LiteralPath $oldFolder) -and @(Get-ChildItem -LiteralPath $oldFolder -Force).Count -eq 0) { Remove-Item -LiteralPath $oldFolder }
if (@(Get-ChildItem -LiteralPath (Inside 'dist') -Force).Count) { throw 'Unexpected dist leftovers; no new release should be promoted yet' }
Write-Host "Migration verified. Ledger: $recordPath"
