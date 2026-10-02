$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$fixture = [IO.Path]::GetFullPath((Join-Path $repo ('jobs/migration-test-' + [guid]::NewGuid().ToString('N'))))
if (-not $fixture.StartsWith($repo + [IO.Path]::DirectorySeparatorChar)) { throw 'Invalid test workspace' }
foreach ($dir in @('tools','dist/jobs/same-id','dist/v0.5.0/jobs/same-id','dist/repaired','archive/versions/v0.4-schedule-editor/package/jobs/same-id','archive/versions/v0.5.0/package')) {
    New-Item -ItemType Directory -Force -Path (Join-Path $fixture $dir) | Out-Null
}
Copy-Item -LiteralPath (Join-Path $repo 'tools/migrate_legacy_layout.ps1') -Destination (Join-Path $fixture 'tools')
foreach ($pair in @(@('dist','v0.4-schedule-editor'),@('dist/v0.5.0','v0.5.0'))) {
    $package = Join-Path $fixture "archive/versions/$($pair[1])/package"
    $dist = Join-Path $fixture $pair[0]
    $pair[1] | Set-Content -LiteralPath (Join-Path $package 'CIM2_SaveStats.exe')
    'same readme' | Set-Content -LiteralPath (Join-Path $package 'README.md')
    Copy-Item -LiteralPath (Join-Path $package 'CIM2_SaveStats.exe') -Destination $dist
    Copy-Item -LiteralPath (Join-Path $package 'README.md') -Destination (Join-Path $dist 'CIM2_SaveStats_README.md')
}
'intermediate' | Set-Content -LiteralPath (Join-Path $fixture 'dist/repaired/CIM2_SaveStats.exe')
foreach ($dir in @('dist/jobs','dist/v0.5.0/jobs','archive/versions/v0.4-schedule-editor/package/jobs')) {
    $dir | Set-Content -LiteralPath (Join-Path $fixture "$dir/same-id/data.txt")
}
try {
    & (Join-Path $fixture 'tools/migrate_legacy_layout.ps1')
    if (@(Get-ChildItem -LiteralPath (Join-Path $fixture 'dist') -Force).Count) { throw 'dist not empty' }
    $record = Get-Content -LiteralPath (Join-Path $fixture 'jobs/migrated/2026-09-25/migration.json') -Raw | ConvertFrom-Json
    $moved = @($record | Where-Object { $_.files })
    if ($moved.Count -ne 3) { throw 'Missing migrated job trees' }
    foreach ($entry in $moved) {
        if ($entry.status -ne 'verified') { throw 'Unverified migration' }
        foreach ($file in $entry.files) {
            if ((Get-FileHash -LiteralPath (Join-Path (Join-Path $fixture $entry.destination) $file.path)).Hash -ne $file.sha256) { throw 'Hash mismatch' }
        }
    }
    Write-Host "Migration checks passed: colliding job IDs preserved, hashes verified, duplicates removed. Fixture: $fixture"
} finally { Set-Location -LiteralPath $repo }
