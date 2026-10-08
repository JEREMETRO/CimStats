"""Read-only binding of CIM2's actual building coverage query.

The returned associations are runtime TransportManager.ListLines results, not
lists serialized in BuildingData. All geometry/radius decisions stay inside
original game methods, on the saved fixed-point positions and transport grid.
CLR is supplied by the isolated map worker; importing this module is pure.
"""
from __future__ import annotations
from map_model import BuildingServiceLines

SOURCE = 'native:TransportManager.ListLines:all-companies'


class NativeCoverageQuery:
    def __init__(self, runtime, root, catalog, *, field=None, cancelled=None):
        self.e = runtime
        self.field = field or runtime.field
        self.manager = None
        self.method = None
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

    def query(self, position, *, company=None, cancelled=None):
        self._cancel(cancelled)
        if self.manager is None or position is None:
            return BuildingServiceLines(complete=False, diagnostic=self.diagnostic or 'native_coverage_position_unavailable')
        e = self.e
        buffer = e.System.Array.CreateInstance(e.ASM.GetType('LineData'), 256)
        # Native InfoTool allocates 256; original ListLines owns order/dedup,
        # strict 3D radius boundaries and original chain traversal safeguards.
        try:
            count = int(self.method.Invoke(self.manager, [buffer, position, company]))
        except e.System.Reflection.TargetInvocationException as error:
            self.diagnostic = f'native_coverage_query_failed:{error.InnerException}'
            return BuildingServiceLines(complete=False, diagnostic=self.diagnostic)
        self._cancel(cancelled)
        ids, unresolved = [], []
        duplicate_identity = False
        for index in range(count):
            self._cancel(cancelled)
            line = buffer.GetValue(index)
            identity = self.field(line, 'm_objectID')
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
