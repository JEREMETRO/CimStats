"""Enumerate managed save/load entry points without loading Unity."""
import sys
import dnfile

pe = dnfile.dnPE(sys.argv[1])
for t in pe.net.mdtables.TypeDef:
    methods = [m.row for m in t.MethodList]
    selected = [m.Name for m in methods if any(k in str(m.Name).lower() for k in ("save", "load", "serialize"))]
    if selected:
        print(str(t.TypeName), ":", ", ".join(map(str, selected)))
