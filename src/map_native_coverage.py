"""Read-only binding of CIM2's actual building coverage query.

The returned associations are runtime TransportManager.ListLines results, not
lists serialized in BuildingData. All geometry/radius decisions stay inside
original game methods, on the saved fixed-point positions and transport grid.
CLR is supplied by the isolated map worker; importing this module is pure.
"""
from __future__ import annotations
from map_model import BuildingServiceLines

SOURCE = 'native:TransportManager.ListLines:all-companies'


def _coverage_reader(runtime, method):
    """Call the original query and copy its ordered IDs inside managed code.

    Reflection.Emit is part of the existing CLR runtime. The reader is private
    to this extraction and emits no assembly/file or replacement query logic.
    Only native returned references cross back as primitive integers; -1 keeps
    a null reference distinct from the real serialized zero identity.
    """
    import clr
    import System.Reflection.Emit
    S=runtime.System
    O=S.Reflection.Emit.OpCodes
    parameters=method.GetParameters()
    line_type=parameters[0].ParameterType.GetElementType()
    manager_type=method.DeclaringType
    result_type=S.Array[S.Int64]
    dynamic=S.Reflection.Emit.DynamicMethod('ReadNativeCoverageIDs',S.Object,
        S.Array[S.Type]([S.Object,S.Object,S.Object]),manager_type.Module,True)
    il=dynamic.GetILGenerator()
    buffer=il.DeclareLocal(parameters[0].ParameterType)
    count=il.DeclareLocal(S.Int32)
    result=il.DeclareLocal(result_type)
    index=il.DeclareLocal(S.Int32)
    line=il.DeclareLocal(line_type)
    check=il.DefineLabel();loop=il.DefineLabel();present=il.DefineLabel();store=il.DefineLabel()
    def emit(op,operand=None):
        if operand is None:il.Emit(op)
        else:il.Emit(op,clr.GetClrType(operand) if isinstance(operand,type) else operand)
    emit(O.Ldc_I4,S.Int32(256));emit(O.Newarr,line_type);emit(O.Stloc,buffer)
    emit(O.Ldarg_0);emit(O.Castclass,manager_type);emit(O.Ldloc,buffer)
    emit(O.Ldarg_1);emit(O.Unbox_Any,parameters[1].ParameterType)
    emit(O.Ldarg_2);emit(O.Castclass,parameters[2].ParameterType)
    emit(O.Callvirt,method);emit(O.Stloc,count)
    emit(O.Ldloc,count);emit(O.Ldc_I4_1);emit(O.Add);emit(O.Newarr,S.Int64);emit(O.Stloc,result)
    emit(O.Ldloc,result);emit(O.Ldc_I4_0);emit(O.Ldloc,count);emit(O.Conv_I8);emit(O.Stelem_I8)
    emit(O.Ldc_I4_0);emit(O.Stloc,index);emit(O.Br,check)
    il.MarkLabel(loop)
    emit(O.Ldloc,buffer);emit(O.Ldloc,index);emit(O.Ldelem_Ref);emit(O.Stloc,line)
    emit(O.Ldloc,result);emit(O.Ldloc,index);emit(O.Ldc_I4_1);emit(O.Add)
    emit(O.Ldloc,line);emit(O.Brtrue,present)
    emit(O.Ldc_I4_M1);emit(O.Conv_I8);emit(O.Br,store)
    il.MarkLabel(present)
    emit(O.Ldloc,line);emit(O.Ldfld,line_type.GetField('m_objectID',runtime.FLAGS));emit(O.Conv_U8)
    il.MarkLabel(store)
    emit(O.Stelem_I8)
    emit(O.Ldloc,index);emit(O.Ldc_I4_1);emit(O.Add);emit(O.Stloc,index)
    il.MarkLabel(check)
    emit(O.Ldloc,index);emit(O.Ldloc,count);emit(O.Blt,loop)
    emit(O.Ldloc,result);emit(O.Ret)
    return dynamic.CreateDelegate(S.Func[S.Object,S.Object,S.Object,S.Object])


class NativeCoverageQuery:
    def __init__(self, runtime, root, catalog, *, field=None, cancelled=None):
        self.e = runtime
        self.field = field or runtime.field
        self.manager = None
        self.method = None
        self._read_ids = None
        self.max_catchment_fixed = None
        self.diagnostic = None
        self._guarded_cells = set()
        self._cancel(cancelled)
        try:
            self._bind(root, catalog, cancelled)
        except (ValueError, KeyError, AttributeError, TypeError, ZeroDivisionError) as error:
            self.diagnostic = f'native_coverage_unavailable:{type(error).__name__}:{error}'
        except runtime.System.Exception as error:
            self.diagnostic = f'native_coverage_unavailable:{error}'

    @staticmethod
    def _cancel(cancelled):
        # Delay import so the runtime adapter does not form an import cycle.
        if cancelled and cancelled():
            from map_geometry import MapCancelled
            raise MapCancelled('Native coverage query cancelled')

    def _bind(self, root, catalog, cancelled):
        e, field = self.e, self.field
        S = e.System
        new = S.Runtime.Serialization.FormatterServices.GetUninitializedObject
        manifest = catalog.get('coverage:catalog', {})
        ids = manifest.get('public_type_ids')
        if not ids or len(ids) != len(set(ids)):
            raise ValueError('Missing complete native public vehicle type catalog')
        rules = field(field(root, 'm_rulesetManagerData'), 'm_ruleset')
        if rules is None or field(rules, 'm_items') is None:
            raise ValueError('Missing saved native ruleset')
        apply = rules.GetType().GetMethod('ApplyTotalValue', e.FLAGS)
        static = e.FLAGS | S.Reflection.BindingFlags.Static
        sqrt = next(m for m in e.ASM.GetType('FixedMath').GetMethods(static)
                    if m.Name == 'Sqrt' and str(m.GetParameters()[0].ParameterType) == 'System.Int64')
        vehicle_type = e.ASM.GetType('VehicleTypeObject')
        types = {}
        max_rule = 1
        for identity in ids:
            self._cancel(cancelled)
            metadata = catalog.get('vehicletype:' + identity)
            if not metadata or not metadata.get('public_transport') or not metadata.get('registered'):
                raise ValueError(f'Missing registered native vehicle type:{identity}')
            # This is RulesetData.Apply's original expression and functions;
            # the radius itself is still evaluated by StopObject.GetCatchmentArea.
            total = int(apply.Invoke(rules, [S.String(identity), S.String('stop-catchment')]))
            product = ((total * 100 + (1 << 31)) % (1 << 32)) - (1 << 31)
            rule = int(sqrt.Invoke(None, [S.Int64(product)]))
            typ = new(vehicle_type)
            vehicle_type.GetField('m_id', e.FLAGS).SetValue(typ, identity)
            vehicle_type.GetField('m_stopCatchmentRule', e.FLAGS).SetValue(typ, S.Int32(rule))
            types[identity] = typ
            max_rule = max(max_rule, rule)
        self.max_catchment_fixed = (2 * max_rule) << 10
        transport = field(root, 'm_transportManagerData')
        grid = field(transport, 'm_stops')
        if grid is None or grid.Rank != 2 or grid.GetLength(0) != 64 or grid.GetLength(1) != 64:
            raise ValueError('Missing native 64x64 transport stop grid')
        # Bind only metadata to each actual saved StopData's prefab. Never
        # rebuild or reorder the saved cell heads/nextInDivision links.
        prefabs = {}
        for x in range(64):
            self._cancel(cancelled)
            for z in range(64):
                node = grid.GetValue(x, z)
                for _ in range(1024):
                    if node is None:
                        break
                    line, stop = field(node, 'm_line'), field(node, 'm_stop')
                    if line is not None and stop is not None:
                        prefab = field(stop, 'm_prefabObject')
                        identity = str(field(prefab, 'm_id') or '')
                        meta = catalog.get(identity)
                        if not meta or meta.get('class_name') != 'StopObject':
                            raise ValueError(f'Missing native stop asset:{identity}')
                        if identity not in prefabs:
                            type_ids = meta.get('type_ids')
                            area = meta.get('catchment_area')
                            if not type_ids or type(area) is not int or any(k not in types for k in type_ids):
                                raise ValueError(f'Missing native stop coverage metadata:{identity}')
                            bound = prefab
                            bound.GetType().GetField('m_catchmentArea', e.FLAGS).SetValue(bound, S.Int32(area))
                            values = S.Array.CreateInstance(vehicle_type, len(type_ids))
                            for index, key in enumerate(type_ids):
                                values.SetValue(types[key], index)
                            bound.GetType().GetField('m_types', e.FLAGS).SetValue(bound, values)
                            # Validate the actual game method before publishing
                            # a query capable of treating an empty hit as known.
                            bound.GetType().GetMethod('GetCatchmentArea', e.FLAGS).Invoke(bound, None)
                            prefabs[identity] = bound
                        stop.GetType().GetField('m_prefabObject', e.FLAGS).SetValue(stop, prefabs[identity])
                    node = field(node, 'm_nextInDivision')
                if node is not None:
                    self._guarded_cells.add((x, z))
        self._cancel(cancelled)
        state = new(e.ASM.GetType('GameState'))
        state.GetType().GetField('m_maxCatchmentArea', e.FLAGS).SetValue(state, S.Int32(self.max_catchment_fixed))
        manager_type = e.ASM.GetType('TransportManager')
        manager = new(manager_type)
        manager_type.GetField('m_gameState', e.FLAGS).SetValue(manager, state)
        manager_type.GetField('m_stops', e.FLAGS).SetValue(manager, grid)
        self.method = next(m for m in manager_type.GetMethods(e.FLAGS)
                           if m.Name == 'ListLines' and len(m.GetParameters()) == 3)
        self.manager = manager
        try:
            self._read_ids = _coverage_reader(e,self.method)
        except (S.Exception,ImportError,TypeError,AttributeError):
            # Some CLR hosts disallow dynamic readers. The original reflection
            # path retains the same data and completeness semantics there.
            self._read_ids = None

    def query(self, position, *, company=None, cancelled=None):
        self._cancel(cancelled)
        if self.manager is None or position is None:
            return BuildingServiceLines(complete=False, diagnostic=self.diagnostic or 'native_coverage_position_unavailable')
        e = self.e
        # Native InfoTool allocates 256; original ListLines owns order/dedup,
        # strict 3D radius boundaries and original chain traversal safeguards.
        try:
            if self._read_ids is not None:
                values = memoryview(self._read_ids(self.manager,position,company)).tolist()
                count = values[0]
                identities = [None if value == -1 else value for value in values[1:]]
            else:
                buffer = e.System.Array.CreateInstance(e.ASM.GetType('LineData'), 256)
                count = int(self.method.Invoke(self.manager, [buffer, position, company]))
                identities = [self.field(buffer.GetValue(index),'m_objectID') for index in range(count)]
        except e.System.Reflection.TargetInvocationException as error:
            self.diagnostic = f'native_coverage_query_failed:{error.InnerException}'
            return BuildingServiceLines(complete=False, diagnostic=self.diagnostic)
        except e.System.Exception as error:
            self.diagnostic = f'native_coverage_query_failed:{error}'
            return BuildingServiceLines(complete=False, diagnostic=self.diagnostic)
        self._cancel(cancelled)
        ids, unresolved = [], []
        duplicate_identity = False
        for identity in identities:
            self._cancel(cancelled)
            if identity is None or int(identity) <= 0:
                unresolved.append(None if identity is None else int(identity))
            elif int(identity) not in ids:
                ids.append(int(identity))
            else:
                duplicate_identity = True
        diagnostics = []
        if count == 256:
            diagnostics.append('native_coverage_buffer_limit')
        # Same native integer cell bounds, solely to label original traversal
        # guard truncation; associations still come from ListLines unchanged.
        radius = self.max_catchment_fixed
        x, z = int(self.field(position, 'x')), int(self.field(position, 'z'))
        lower_x, upper_x = max(0, (x+4194304-radius) >> 17), min(63, (x+4194304+radius) >> 17)
        lower_z, upper_z = max(0, (z+4194304-radius) >> 17), min(63, (z+4194304+radius) >> 17)
        if any(lower_x <= x <= upper_x and lower_z <= z <= upper_z for x, z in self._guarded_cells):
            diagnostics.append('native_coverage_chain_guard')
        if unresolved:
            diagnostics.append('native_coverage_unresolved_identity')
        if duplicate_identity:
            diagnostics.append('native_coverage_duplicate_identity')
        complete = not diagnostics
        return BuildingServiceLines(bool(ids or unresolved) or complete, tuple(ids), tuple(unresolved),
                                    SOURCE if company is None else 'native:TransportManager.ListLines:company',
                                    complete, ';'.join(diagnostics) or None)
