from pathlib import Path
import os
import dnfile

PROJECT = Path(__file__).resolve().parents[1]
SRC = Path(os.environ.get(
    "CIM2_ASSEMBLY_SOURCE",
    str(PROJECT / "game_runtime" / "Managed" / "Assembly-CSharp.dll"),
))
if not SRC.exists():
    SRC = Path(os.environ.get("CIM2_ASSEMBLY_SOURCE", "")) or SRC
DST = Path(os.environ.get("CIM2_PROBE_OUTPUT", str(PROJECT / "data" / "Assembly-CSharp.probe.dll")))
if not SRC.exists():
    raise FileNotFoundError(f"找不到待补丁的 Assembly-CSharp.dll：{SRC}")
DST.parent.mkdir(parents=True, exist_ok=True)
METHOD_FILE_OFFSET = 1013776
HEADER_SIZE = 12
CODE_SIZE = 140
GET_VEHICLE_FILE_OFFSET = 821300
GET_VEHICLE_HEADER_SIZE = 12
GET_VEHICLE_CODE_SIZE = 21
GET_PLACEABLE_FILE_OFFSET = 821192
GET_PLACEABLE_HEADER_SIZE = 12
GET_PLACEABLE_CODE_SIZE = 21
GET_ROADTYPE_FILE_OFFSET = 821228
GET_VEHICLEINFO_FILE_OFFSET = 821264
GET_TEXTURE_FILE_OFFSET = 821156
GET_CHARACTER_FILE_OFFSET = 821336
GET_MENU_FILE_OFFSET = 821372
GET_PERSON_FILE_OFFSET = 821408
GET_AUDIO_FILE_OFFSET = 821444
GET_ATLAS_FILE_OFFSET = 821480
GET_CAMPAIGN_FILE_OFFSET = 821516
LINE_AFTER_FILE_OFFSET = 514572
LINE_DESERIALIZE_GETTYPE_OFFSET = 0x7D852
CODEBUG_WARN_FILE_OFFSET = 960836

data = bytearray(SRC.read_bytes())
out = bytearray(data)

def patch_ret_at(offset):
    """Replace a managed method body with a valid one-byte `ret`."""
    first = out[offset]
    if first & 0x3 == 0x2:  # tiny header: (code_size << 2) | 2
        out[offset] = 0x06
        out[offset + 1] = 0x2A
    else:  # fat header; code size is the fourth header word
        out[offset + 4:offset + 8] = (1).to_bytes(4, 'little')
        out[offset + 12] = 0x2A


def patch_null_return_at(offset):
    """Replace a reference-returning method with valid ``ldnull; ret`` IL."""
    first = out[offset]
    if first & 0x3 == 0x2:  # tiny header: (code_size << 2) | 2
        out[offset] = (2 << 2) | 2
        out[offset + 1:offset + 3] = b"\x14\x2a"
    else:  # fat header; code size is the fourth header word
        out[offset + 4:offset + 8] = (2).to_bytes(4, 'little')
        out[offset + 12:offset + 14] = b"\x14\x2a"


def patch_method_body(method, body: bytes):
    """Write a small replacement body using the method's actual metadata RVA."""
    offset = pe.get_offset_from_rva(method.Rva)
    first = out[offset]
    if first & 0x3 == 0x2:
        capacity = first >> 2
        if len(body) > capacity:
            raise ValueError(f"replacement body is larger than tiny method {method.Name}")
        out[offset] = (len(body) << 2) | 2
        out[offset + 1:offset + 1 + len(body)] = body
    else:
        capacity = int.from_bytes(out[offset + 4:offset + 8], 'little')
        if len(body) > capacity:
            raise ValueError(f"replacement body is larger than method {method.Name}")
        out[offset + 4:offset + 8] = len(body).to_bytes(4, 'little')
        out[offset + 12:offset + 12 + len(body)] = body

# AfterDeserialize hooks normally perform runtime graph fixups. The default
# standalone probe suppresses them because some callbacks require Unity
# singletons.  Graph experiments can retain them by setting the environment
# switch below; they do not read the serialized stream.
pe = dnfile.dnPE(str(SRC))
keep_after = os.environ.get("CIM2_KEEP_AFTER_DESERIALIZE", "0") == "1"
keep_types = {
    name.strip() for name in os.environ.get("CIM2_KEEP_AFTER_TYPES", "").split(",")
    if name.strip()
}
for td in pe.net.mdtables.TypeDef:
    type_name = str(td.TypeName)
    for fr in td.MethodList:
        method = fr.row
        if str(method.Name) == 'AfterDeserialize' and method.Rva:
            if keep_after and (not keep_types or type_name in keep_types):
                continue
            patch_ret_at(pe.get_offset_from_rva(method.Rva))

# SingletonGameObject<T>.get_instance is an InternalCall in the game build.
# DataSerializer can reach it from LineData.Deserialize even though the
# surrounding AfterDeserialize hooks are disabled.  There is no Unity scene
# in the standalone parser, so invoke-time ECall resolution raises a
# SecurityException before the serialized fields can be inspected.  Returning
# the default reference value (null) lets the serializer continue; callers
# that require a live Unity object are separately guarded by the lookup
# patches below.
for td in pe.net.mdtables.TypeDef:
    if str(td.TypeName).startswith("SingletonGameObject"):
        for fr in td.MethodList:
            method = fr.row
            if str(method.Name) == "get_instance" and method.Rva:
                patch_null_return_at(pe.get_offset_from_rva(method.Rva))
# CODebug's public logging wrappers eventually call UnityEngine's native
# Debug implementation.  Deserializers use these calls only for diagnostics,
# but invoking them outside the Unity player raises an ECall SecurityException.
# Suppress the void wrappers so malformed-data checks can still follow their
# normal managed control flow without requiring a live Unity runtime.
for td in pe.net.mdtables.TypeDef:
    if str(td.TypeName) != "CODebug":
        continue
    for fr in td.MethodList:
        method = fr.row
        if str(method.Name) in {"Warn", "Error", "Log"} and method.Rva:
            patch_method_body(method, b"\x2a")
# VehicleTypeObject derives from a Unity-backed native object.  Its managed
# constructor is an ECall in the game build, so invoking `new VehicleTypeObject`
# from the replacement lookup would otherwise fail before m_id can be assigned.
# Replace only that constructor with a normal managed `ret`; the object remains
# usable for the serialized identifier field we populate below.
for td in pe.net.mdtables.TypeDef:
    if str(td.TypeName) != 'VehicleTypeObject':
        continue
    for fr in td.MethodList:
        method = fr.row
        if str(method.Name) == '.ctor' and method.Rva:
            patch_ret_at(pe.get_offset_from_rva(method.Rva))
# DataStoreManager.GetVehicleTypeInfo is a static lookup that dereferences
# Unity-backed state. Return a minimal VehicleTypeObject carrying the exact
# serialized string ID, which is all line classification needs.  Build the
# newobj/stfld tokens from the current metadata rather than hard-coding row
# numbers from an older Assembly-CSharp build.
method_token = {}
for index, method in enumerate(pe.net.mdtables.MethodDef, 1):
    method_token[id(method)] = 0x06000000 | index
field_token = {}
for index, field in enumerate(pe.net.mdtables.Field, 1):
    field_token[id(field)] = 0x04000000 | index
vehicle_ctor_token = None
vehicle_id_token = None
for td in pe.net.mdtables.TypeDef:
    if str(td.TypeName) != "VehicleTypeObject":
        continue
    for fr in td.MethodList:
        if str(fr.row.Name) == ".ctor":
            vehicle_ctor_token = method_token.get(id(fr.row))
    for fr in td.FieldList:
        if str(fr.row.Name) == "m_id":
            vehicle_id_token = field_token.get(id(fr.row))
if vehicle_ctor_token is None or vehicle_id_token is None:
    raise RuntimeError("无法定位 VehicleTypeObject 的构造函数或 m_id 字段")
vehicle_type_body = (
    b"\x73" + vehicle_ctor_token.to_bytes(4, "little") +
    b"\x25\x02\x7d" + vehicle_id_token.to_bytes(4, "little") + b"\x2a"
)

# Optional write-back experiment: StopData.Serialize requires a concrete
# PlaceableObject with a valid m_id.  The normal read-only probe returns null
# for Unity prefabs; when explicitly enabled, return a managed StopObject
# carrying the serialized prefab id.  This is intentionally opt-in until a
# complete no-op round-trip passes.
if os.environ.get("CIM2_ENABLE_WRITE_PROBE", "0") == "1":
    stop_ctor_token = None
    stop_id_token = None
    for td in pe.net.mdtables.TypeDef:
        if str(td.TypeName) == "StopObject":
            for fr in td.MethodList:
                if str(fr.row.Name) == ".ctor":
                    stop_ctor_token = method_token.get(id(fr.row))
        if str(td.TypeName) == "PlaceableObject":
            for fr in td.FieldList:
                if str(fr.row.Name) == "m_id":
                    stop_id_token = field_token.get(id(fr.row))
    if stop_ctor_token and stop_id_token:
        stop_body = (b"\x73" + stop_ctor_token.to_bytes(4, "little") +
                     b"\x25\x02\x7d" + stop_id_token.to_bytes(4, "little") + b"\x2a")
        for td in pe.net.mdtables.TypeDef:
            if str(td.TypeName) == "StopObject":
                for fr in td.MethodList:
                    if str(fr.row.Name) == ".ctor" and fr.row.Rva:
                        patch_method_body(fr.row, b"\x2a")
            if str(td.TypeName) == "DataStoreManager":
                for fr in td.MethodList:
                    if str(fr.row.Name) == "GetPlaceablePrefab" and fr.row.Rva:
                        patch_method_body(fr.row, stop_body)
# The placement/type lookups have the same Unity-backed singleton dependency.
# Locate them by metadata instead of fixed file offsets: Steam hotfixes can
# move method bodies while keeping the public v1.6.3 API unchanged.
for td in pe.net.mdtables.TypeDef:
    if str(td.TypeName) != "DataStoreManager":
        continue
    for fr in td.MethodList:
        method = fr.row
        if not method.Rva:
            continue
        name = str(method.Name)
        if name == "GetVehicleTypeInfo":
            patch_method_body(method, vehicle_type_body)
        elif name in {
            "GetPlaceablePrefab", "GetRoadTypeInfo", "GetVehicleInfo",
            "GetTextureInfo", "GetCharacterInfo", "GetMenu",
            "GetPersonInfo", "GetAudioInfo", "GetAtlasInfo", "GetCampaignInfo",
        }:
            if name == "GetPlaceablePrefab" and os.environ.get("CIM2_ENABLE_WRITE_PROBE", "0") == "1":
                continue
            patch_method_body(method, bytes.fromhex("14 2a"))
# Keep post-processing method body intact; its dependency is patched below.
# Keep LineData's GetVehicleTypeInfo call intact; the patched method above
# returns a minimal object carrying the exact serialized type ID.
DST.write_bytes(out)
print(DST, len(out))
