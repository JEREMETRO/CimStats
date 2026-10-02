"""Read-only IL inspection; no game assemblies are modified."""
import argparse

import dnfile
from dncil.cil.body import CilMethodBody
from dncil.cil.body.reader import CilMethodBodyReaderBytes


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("assembly")
    parser.add_argument("types", nargs="+")
    args = parser.parse_args()
    pe = dnfile.dnPE(args.assembly)
    owners = {}
    for t in pe.net.mdtables.TypeDef:
        for index in t.MethodList:
            owners[id(index.row)] = str(t.TypeName)
        for index in t.FieldList:
            owners[id(index.row)] = str(t.TypeName)

    def describe(token):
        if not hasattr(token, "table"):
            return str(token)
        if token.table == 0x70:
            return repr(pe.net.user_strings.get(token.rid).value)
        table = pe.net.mdtables.tables.get(token.table)
        if not table:
            return str(token)
        row = table.rows[token.rid - 1]
        if token.table == 0x2B:
            row = row.Method.row
        return owners.get(id(row), "") + "::" + str(getattr(row, "Name", getattr(row, "TypeName", token)))

    for t in pe.net.mdtables.TypeDef:
        if str(t.TypeName) not in args.types:
            continue
        for index in t.MethodList:
            m = index.row
            if not m.Rva:
                continue
            print("\nMETHOD", t.TypeName, m.Name, "RVA", hex(m.Rva))
            body = CilMethodBody(CilMethodBodyReaderBytes(pe.get_data(m.Rva)))
            for instruction in body.instructions:
                print(f" {instruction.offset:04x} {str(instruction.opcode):20} {describe(instruction.operand)}")


if __name__ == "__main__":
    main()
