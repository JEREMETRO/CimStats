"""Native-query regressions use the actual game methods on controlled object graphs."""
import os
from pathlib import Path
from types import SimpleNamespace
import pytest

@pytest.fixture(scope='module')
def native():
    import clr, System
    base=Path(__file__).resolve().parents[1]
    managed=Path(os.environ.get('CIM2_MANAGED_ROOT',base/'game_runtime/Managed'))
    def resolve(_sender,args):
        p=managed/(args.Name.split(',')[0]+'.dll')
        return System.Reflection.Assembly.LoadFile(str(p)) if p.is_file() else None
    System.AppDomain.CurrentDomain.AssemblyResolve+=resolve
    clr.AddReference(str(base/'data/UnityEngine.dll'))
    assembly=System.Reflection.Assembly.LoadFile(str(base/'data/Assembly-CSharp.probe.dll'))
    flags=System.Reflection.BindingFlags.Public|System.Reflection.BindingFlags.NonPublic|System.Reflection.BindingFlags.Instance
    def field(obj,key):
        if obj is None:return None
        f=obj.GetType().GetField(key,flags)
        return f.GetValue(obj) if f is not None else None
    def new(name):return System.Runtime.Serialization.FormatterServices.GetUninitializedObject(assembly.GetType(name))
    def set_(obj,key,value):
        f=obj.GetType().GetField(key,flags)
        if str(f.FieldType)=='System.Int32':value=System.Int32(value)
        elif str(f.FieldType)=='System.UInt32':value=System.UInt32(value)
        elif str(f.FieldType)=='System.Boolean':value=System.Boolean(value)
        f.SetValue(obj,value)
    def vector(x,y=0,z=0):
        v=System.Activator.CreateInstance(assembly.GetType('FixedVector3D'))
        for axis,value in zip(('x','y','z'),(x,y,z)):set_(v,axis,value)
        return v
    e=SimpleNamespace(System=System,ASM=assembly,FLAGS=flags,field=field,array_values=lambda v:[] if v is None else list(v))
    return SimpleNamespace(e=e,new=new,set=set_,vector=vector)


def graph(native, *, stop_x=0, stop_y=0, lines=2, rules=(), missing=None, duplicate=True):
    n=native;e=n.e;S=e.System
    root=n.new('GameState+SerializableData');transport=n.new('TransportManager+SerializableData')
    grid=S.Array.CreateInstance(e.ASM.GetType('LineData+Stop'),64,64)
    n.set(transport,'m_stops',grid);n.set(root,'m_transportManagerData',transport)
    ruleset=n.new('RulesetData');rulefield=ruleset.GetType().GetField('m_items',e.FLAGS)
    dictionary=S.Activator.CreateInstance(rulefield.FieldType)
    keytype=dictionary.GetType().GetGenericArguments()[0]
    for category,identity,value in rules:
        key=S.Activator.CreateInstance(keytype);n.set(key,'m_category',category);n.set(key,'m_id',identity)
        dictionary.Add(key,S.Int32(value))
    n.set(ruleset,'m_items',dictionary);manager=n.new('RulesetManager+SerializableData');n.set(manager,'m_ruleset',ruleset);n.set(root,'m_rulesetManagerData',manager)
    owners=[n.new('CompanyData'),n.new('CompanyData')]
    typ=n.new('StopObject');n.set(typ,'m_id','native-stop')
    stop=n.new('StopData');n.set(stop,'m_prefabObject',typ);n.set(stop,'m_position',n.vector(stop_x,stop_y));n.set(stop,'m_objectID',10)
    actual=[];previous=None
    for i in reversed(range(lines)):
        line=n.new('LineData');n.set(line,'m_objectID',i+1);n.set(line,'m_owner',owners[i%2]);n.set(line,'m_active',False)
        node=n.new('LineData+Stop');n.set(node,'m_line',line);n.set(node,'m_stop',stop);n.set(node,'m_nextInDivision',previous);previous=node;actual.insert(0,line)
    if duplicate and actual:
        node=n.new('LineData+Stop');n.set(node,'m_line',actual[0]);n.set(node,'m_stop',stop);n.set(node,'m_nextInDivision',previous);previous=node
    x=max(0,min(63,(stop_x+4194304)>>17));grid.SetValue(previous,x,32)
    n.set(transport,'m_firstLine',actual[0] if actual else None)
    for a,b in zip(actual,actual[1:]):n.set(a,'m_nextLine',b)
    n.set(transport,'m_lineCount',lines)
    n.set(root,'m_transportManagerData',transport)
    catalog={
        'coverage:catalog':dict(class_name='NativeCoverageCatalog',public_type_ids=['bus','trolley']),
        'vehicletype:bus':dict(id='bus',class_name='VehicleTypeObject',public_transport=True,registered=True),
        'vehicletype:trolley':dict(id='trolley',class_name='VehicleTypeObject',public_transport=True,registered=True),
        'native-stop':dict(id='native-stop',class_name='StopObject',type_ids=['bus','trolley'],catchment_area=150),
    }
    if missing:catalog.pop(missing)
    return root,catalog,owners


def test_native_grid_dedup_order_owner_scope_and_inactive_lines(native):
    from map_native_coverage import NativeCoverageQuery
    root,catalog,owners=graph(native)
    query=NativeCoverageQuery(native.e,root,catalog)
    result=query.query(native.vector(0))
    assert result.known and result.route_ids==(1,2) and result.source=='native:TransportManager.ListLines:all-companies'
    assert query.query(native.vector(0),company=owners[1]).route_ids==(2,)
    assert query.query(native.vector(151*1024)).known and query.query(native.vector(151*1024)).route_ids==()

@pytest.mark.parametrize('x,y,want',[(149*1024,0,True),(150*1024,0,False),(90*1024,120*1024,False),(90*1024,119*1024,True)])
def test_native_strict_three_dimensional_radius(native,x,y,want):
    from map_native_coverage import NativeCoverageQuery
    root,catalog,_=graph(native)
    result=NativeCoverageQuery(native.e,root,catalog).query(native.vector(x,y))
    assert bool(result.route_ids) is want


def test_native_saved_rules_apply_global_multiplier_sqrt_mixed_types_and_max_cap(native):
    from map_native_coverage import NativeCoverageQuery
    root,catalog,_=graph(native,rules=(('bus','stop-catchment',400),('vehicletypes','stop-catchment',100)))
    query=NativeCoverageQuery(native.e,root,catalog)
    assert query.max_catchment_fixed==400*1024
    # Native mixed stop average (sqrt40000+sqrt10000)/2=150; 150m*1.5=225m.
    assert query.query(native.vector(224*1024)).route_ids==(1,2)
    assert query.query(native.vector(225*1024)).route_ids==()
    # Radius500m still subject to native global cap400m; no custom extrapolation.
    catalog['native-stop']['catchment_area']=500
    query=NativeCoverageQuery(native.e,root,catalog)
    assert query.query(native.vector(399*1024)).route_ids==(1,2)
    assert query.query(native.vector(400*1024)).route_ids==()


def test_native_buffer_limit_and_missing_dependency_not_known_empty(native):
    from map_native_coverage import NativeCoverageQuery
    root,catalog,_=graph(native,lines=260,duplicate=False)
    result=NativeCoverageQuery(native.e,root,catalog).query(native.vector(0))
    assert result.route_ids==tuple(range(1,257))
    root,catalog,_=graph(native,missing='vehicletype:bus')
    result=NativeCoverageQuery(native.e,root,catalog).query(native.vector(0))
    assert not result.known and result.route_ids==()


def test_native_cancellation_does_not_publish_partial_associations(native):
    from map_native_coverage import NativeCoverageQuery
    from map_geometry import MapCancelled
    root,catalog,_=graph(native)
    with pytest.raises(MapCancelled):NativeCoverageQuery(native.e,root,catalog,cancelled=lambda:True)
    query=NativeCoverageQuery(native.e,root,catalog)
    with pytest.raises(MapCancelled):query.query(native.vector(0),cancelled=lambda:True)


def test_native_limits_have_internal_incomplete_diagnostics_and_guarded_empty_is_unknown(native):
    from map_native_coverage import NativeCoverageQuery
    root,catalog,_=graph(native,lines=260,duplicate=False)
    result=NativeCoverageQuery(native.e,root,catalog).query(native.vector(0))
    assert result.known and result.complete is False and 'buffer' in result.diagnostic
    root,catalog,_=graph(native,lines=1,duplicate=False)
    grid=native.e.field(native.e.field(root,'m_transportManagerData'),'m_stops')
    node=grid.GetValue(32,32);native.set(node,'m_nextInDivision',node)
    query=NativeCoverageQuery(native.e,root,catalog)
    result=query.query(native.vector(0))
    assert result.known and result.complete is False and 'guard' in result.diagnostic
    result=query.query(native.vector(151*1024))
    assert not result.known and result.complete is False and 'guard' in result.diagnostic
    # An unrelated remote window stays a proved complete empty result.
    result=query.query(native.vector(-4096*1024))
    assert result.known and result.route_ids==() and result.complete is True


def test_native_missing_rules_and_null_returned_identity_stay_distinct(native):
    from map_native_coverage import NativeCoverageQuery
    root,catalog,_=graph(native,lines=1,duplicate=False)
    transport=native.e.field(root,'m_transportManagerData')
    native.set(native.e.field(transport,'m_firstLine'),'m_objectID',0)
    result=NativeCoverageQuery(native.e,root,catalog).query(native.vector(0))
    assert result.known and result.unresolved_refs==(0,) and result.route_ids==()
    assert result.complete is False and 'identity' in result.diagnostic
    native.set(root,'m_rulesetManagerData',None)
    query=NativeCoverageQuery(native.e,root,catalog)
    assert not query.query(native.vector(0)).known
    assert 'ruleset' in query.diagnostic


def test_packaged_asset_dependencies_produce_actual_native_mixed_stop_radius(native):
    import json
    from map_native_coverage import NativeCoverageQuery
    root,_,_=graph(native,lines=1,duplicate=False)
    grid=native.e.field(native.e.field(root,'m_transportManagerData'),'m_stops')
    prefab=native.e.field(native.e.field(grid.GetValue(32,32),'m_stop'),'m_prefabObject')
    native.set(prefab,'m_id','bus-tram-stop-01')
    catalog=json.loads((Path(__file__).resolve().parents[1]/'data/map_assets.json').read_text(encoding='utf-8'))
    query=NativeCoverageQuery(native.e,root,catalog)
    assert query.query(native.vector(159*1024)).route_ids==(1,)
    assert query.query(native.vector(160*1024)).known and query.query(native.vector(160*1024)).route_ids==()


def test_native_coverage_complete_and_diagnostic_survive_snapshot_and_stream_roundtrip(tmp_path):
    from dataclasses import asdict
    from map_geometry import snapshot_from_data,_write_geometry_ndjson,_read_geometry_ndjson,_decode_snapshot
    import json
    raw={'roads':{},'buildings':[{'id':1,'position':[0,0,0],'service_lines':{'known':True,'route_ids':[5],
        'unresolved_refs':[0],'source':'native:TransportManager.ListLines:all-companies',
        'complete':False,'diagnostic':'native_coverage_buffer_limit'}}]}
    raw['buildings'].extend([
        {'id':2,'position':(1,2,3),'service_lines':dict(known=True,route_ids=(),unresolved_refs=(),
            source='native:TransportManager.ListLines:all-companies',complete=True,diagnostic=None)},
        {'id':3,'position':(4,5,6),'service_lines':dict(known=False,route_ids=(),unresolved_refs=(),
            source=None,complete=False,diagnostic='native_coverage_unavailable:missing catalog')},
        {'id':4,'position':(7,8,9),'service_lines':dict(known=True,route_ids=(9,2),unresolved_refs=(),
            source='native:TransportManager.ListLines:all-companies',complete=True,diagnostic=None)},
    ])
    snapshot=snapshot_from_data(raw)
    assert snapshot.buildings[0].service_lines.complete is False
    assert snapshot.buildings[0].service_lines.diagnostic=='native_coverage_buffer_limit'
    assert _decode_snapshot(json.loads(json.dumps(asdict(snapshot))))==snapshot
    raw.update(stops={},lines=[],diagnostics=[],junctions=[])
    output=tmp_path/'native.ndjson';_write_geometry_ndjson(raw,output)
    streamed=snapshot_from_data(_read_geometry_ndjson(output))
    assert streamed==snapshot
    assert streamed.buildings[1].service_lines.known and streamed.buildings[1].service_lines.complete
    assert not streamed.buildings[2].service_lines.known
    assert streamed.buildings[3].service_lines.route_ids==(9,2)


def test_native_distinct_objects_with_colliding_ids_are_flagged_not_claimed_complete(native):
    from map_native_coverage import NativeCoverageQuery
    root,catalog,_=graph(native,lines=2,duplicate=False)
    grid=native.e.field(native.e.field(root,'m_transportManagerData'),'m_stops')
    first=grid.GetValue(32,32);second=native.e.field(first,'m_nextInDivision')
    native.set(native.e.field(second,'m_line'),'m_objectID',1)
    result=NativeCoverageQuery(native.e,root,catalog).query(native.vector(0))
    assert result.known and result.route_ids==(1,)
    assert result.complete is False and 'duplicate_identity' in result.diagnostic
