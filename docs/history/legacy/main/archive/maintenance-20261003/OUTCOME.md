# Repository consolidation result

Current checkout: D:/test/CimStats

Remote: https://github.com/JEREMETRO/CimStats

Commit: 28732690730b3aac4f6b7d27e1334942ca5e4693

Local main and origin/main have no commits ahead or behind. The current
checkout is clean; only dist/ is ignored and retained for local use. The
295 tracked files include the parser dependencies and reference catalogs,
but no private saves, runtime outputs or build caches. The existing Test
release and its executable are unchanged.

## Verification

- 978 source tests passed; one optional local-sample test skipped.
- All 40 tools tests passed after aligning two obsolete spec tests with
  the existing one-file release configuration.
- A fresh GitHub clone passed all 40 tools tests, source/bundle inventory
  validation, GUI startup and navigation through all three pages.
- Single-player and multiplayer saves parsed successfully in the current
  checkout. A fresh GitHub clone also parsed the single-player save and
  produced 15 CSV files and both workbooks using its own bundled assemblies.
- The retained EXE matches the published release's SHA256.

Reports and details: verification-summary.json, tools-results.xml,
clone-tools-results.xml and source-and-tools-before-tool-alignment.xml.

## Cleanup

113 targets totaling 20.095 GiB were moved into the Windows Recycle Bin.
All 113 metadata records and recycled payloads were verified to exist.
Nothing was permanently deleted. Records are in recycle-results.json;
the original inventory and preservation hashes are in cleanup-manifest.json.

Old source, Git history, original input saves and all four worktrees remain
under D:/test/CIM2_SaveStats. Preserved scripts and small review records are
under preserved/. Other projects under D:/test were not changed.

One target remains: D:/test/CIM2_SaveStats/build/onefile-dist. Its CimStats.exe
is still running and locked by Windows. It was left in place while awaiting
permission to close the old instance. The new executable is available at
D:/test/CimStats/dist/CimStats.exe. The recycle helper can resume after the
old instance exits, without repeating completed operations.
