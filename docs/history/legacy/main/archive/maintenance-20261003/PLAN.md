# CimStats Repository Consolidation

Goal: Make D:/test/CimStats the current local checkout of JEREMETRO/CimStats,
with all files needed to launch and parse saves. Keep the previous project
and its unfinished branches separate. Send generated working files to the
Windows Recycle Bin, preserving source files, input saves and review summaries.

1. Clone the existing published source locally, retain its Git history and
   align the local main branch with origin/main.
2. Include the required runtime dependencies and reference catalogs. Update
   setup documentation and ignore generated files.
3. Validate startup, parsing and the relevant existing tests from the new
   directory without relying on the previous checkout.
4. Commit and push the consolidated checkout. Verify the remote commit and
   runtime files.
5. Inventory generated files, keep review summaries and input data, then
   recycle the inventoried outputs with a record of completed operations.

Constraints: No permanent deletion, no overwritten user changes, no force
push, no removal of unfinished worktrees, and no public maintenance notes
about local staging or previous release audits.
