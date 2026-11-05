"""Native waypoint classification hides annotations without changing routes."""
from dataclasses import asdict, replace
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtGui import QImage, QPainter

from map_canvas import MapCanvas, MapSearchResult, _FrameSurface, MAP_BACKGROUND
from map_geometry import (SCHEMA_VERSION, _decode_snapshot, _read_geometry_ndjson,
                          _write_geometry_ndjson, snapshot_from_data)
from map_model import MapRoute, MapSnapshot, MapStop, RouteDirection


def test_packaged_stop_catalog_preserves_confirmed_native_waypoint_booleans():
    catalog=json.loads((Path(__file__).resolve().parents[1]/'data/map_assets.json').read_text(encoding='utf8'))
    stops=[record for record in catalog.values() if record.get('class_name')=='StopObject']
    assert len(stops)==19 and all(type(record.get('waypoint')) is bool for record in stops)
    assert sum(record['waypoint'] for record in stops)==5


def test_native_stop_records_use_confirmed_prefab_evidence_in_both_collections(monkeypatch):
    import map_geometry
    import map_native_coverage
    from test_runtime_direction_time import runtime_helpers

    class NativeObject:
        def __init__(self,kind,**values):self.kind,self.values=kind,values
        def GetType(self):
            return SimpleNamespace(Name=self.kind,GetFields=lambda _:[],GetField=lambda name,_:
                SimpleNamespace(FieldType=SimpleNamespace(IsValueType=False,FullName=''),
                                GetValue=lambda obj:obj.values.get(name)))
    field=lambda obj,name:obj.values.get(name) if obj is not None else None
    records=[];catalog={}
    for identity,waypoint,count in ((1,True,1),(2,False,0),(3,None,None)):
        asset=str(identity)
        catalog[asset]=dict(id=asset,class_name='StopObject',waypoint=waypoint)
        records.append(NativeObject('StopData',m_objectID=identity,m_name='same',m_lineCount=count,
            m_position=NativeObject('FixedVector3D',x=identity*1024,y=0,z=0),
            m_prefabObject=NativeObject('StopObject',m_id=asset,m_waypoint=False)))
    line=NativeObject('LineData',m_objectID=10,m_number=10,
        m_stops=[NativeObject('Stop',m_stop=stop,m_path=[],m_timeOffset=i) for i,stop in enumerate(records)])
    cell=NativeObject('Division',m_smallObjects=records,m_largeObjects=[])
    divisions=SimpleNamespace(GetLength=lambda _:1,GetValue=lambda *_:cell)
    root=NativeObject('Root',m_objectManagerData=NativeObject('Manager',m_divisions=divisions),
        m_transportManagerData=NativeObject('Transport',m_firstLine=line,m_lineCount=1),m_players=[])
    helpers=runtime_helpers();helpers['field']=field
    runtime=SimpleNamespace(FLAGS=0,field=field,array_values=lambda v:list(v) if v is not None else [],
        can_stop_here_serialized=helpers['can_stop_here_serialized'],
        ASM=SimpleNamespace(GetType=lambda _:SimpleNamespace(GetMethod=lambda *_:None)),
        System=SimpleNamespace(Exception=RuntimeError),line_mode=lambda _:'bus')
    monkeypatch.setattr(map_geometry,'_citizen_reader',lambda _:(_ for _ in ()).throw(AttributeError()))
    monkeypatch.setattr(map_native_coverage,'NativeCoverageQuery',lambda *_args,**_kwargs:
                        SimpleNamespace(diagnostic=None))
    raw=map_geometry._extract_objects(runtime,root,catalog,distribution_tables={})
    assert tuple(stop['can_stop'] for stop in raw['stops'].values())==(False,True,None)
    assert tuple(stop['can_stop'] for stop in raw['lines'][0]['stops'])==(False,True,None)
    assert snapshot_from_data(raw).routes[0].stop_ids==(1,2,3)


def test_classification_survives_global_and_route_records_and_temporary_handoff(tmp_path):
    records=[dict(id=i,name='same name',position=[i*20,0,0],can_stop=value)
             for i,value in ((1,True),(2,False),(3,None))]
    raw=dict(roads={},buildings=[],stops={str(r['id']):r for r in records},
             lines=[dict(id=10,stops=records,legs=[])],diagnostics=[],junctions=[])
    target=tmp_path/'classification.ndjson'
    _write_geometry_ndjson(raw,target)
    snapshot=snapshot_from_data(_read_geometry_ndjson(target))
    assert tuple(getattr(stop,'can_stop',None) for stop in snapshot.stops)==(True,False,None)
    assert snapshot.routes[0].stop_ids==(1,2,3)
    assert len(snapshot.routes[0].leg_paths)==2
    assert snapshot.schema_version==SCHEMA_VERSION==14
    assert _decode_snapshot(json.loads(json.dumps(asdict(snapshot))))==snapshot
    # Standalone stops use the same classification as route occurrences.
    raw['lines']=[]
    assert tuple(stop.can_stop for stop in snapshot_from_data(raw).stops)==(True,False,None)


def test_legacy_json_stop_remains_unknown():
    raw=asdict(MapSnapshot(stops=(MapStop(7,'legacy',(0.,0.,0.)),)))
    raw['schema_version']=13
    raw['stops'][0].pop('can_stop')
    assert _decode_snapshot(raw).stops[0].can_stop is None


def scene(qt_application):
    # Deliberately identical names: names and position do not classify a stop.
    stops=tuple(MapStop(i,'same name',(x,0.,0.),value)
                for i,x,value in ((1,-80.,True),(2,0.,False),(3,80.,None)))
    points=tuple(stop.position for stop in stops)
    route=MapRoute(10,'route',10,'c','company','bus',(1,2,3),(points,),
                   RouteDirection('one_way'),tuple(((a,b),) for a,b in zip(points,points[1:])))
    canvas=MapCanvas();canvas.resize(400,300)
    canvas.set_snapshot(MapSnapshot(stops=stops,routes=(route,),bounds=(-100.,-100.,100.,100.)))
    canvas.set_options(roads=False,buildings=False,line_numbers=False,stop_names=True)
    canvas.center=(0.,0.);canvas.zoom=1.
    return canvas,route


def test_only_confirmed_waypoint_is_hidden_from_annotations_search_and_focus(qt_application):
    canvas,route=scene(qt_application)
    try:
        assert tuple(stop.id for stop,_ in canvas._display_stops((route,),clip=False))==(1,3)
        assert {result.id for result in canvas.search('same name')}=={1,3}
        assert canvas.search('2')==[]
        old=MapSearchResult('stop',2,'same name',(-1.,-1.,1.,1.))
        assert not canvas.focus_result(old)
        canvas._indexes_ready=False
        assert not canvas.focus_result(old)
        assert canvas._pending_focus is None
        assert canvas.snapshot.routes==(route,)
        assert route.stop_ids==(1,2,3) and len(route.leg_paths)==2
    finally:canvas.close()


@pytest.mark.parametrize('direction,expected',[('up',(3,)),('down',(1,)),('whole',(1,3))])
def test_waypoint_retains_operating_leg_indices_for_both_directions(qt_application,direction,expected):
    canvas,route=scene(qt_application)
    try:
        route=replace(route,direction=RouteDirection('roundtrip',1))
        canvas.set_snapshot(replace(canvas.snapshot,routes=(route,)))
        canvas.set_options(direction=direction)
        assert tuple(stop.id for stop,_ in canvas._display_stops((route,),clip=False))==expected
        assert route.stop_ids==(1,2,3) and len(route.leg_paths)==2
        assert canvas.snapshot.routes[0] is route
    finally:canvas.close()


@pytest.mark.parametrize('renderer',['canvas','vector','gpu_annotations'])
def test_waypoint_has_no_symbol_or_name_in_any_renderer(qt_application,renderer):
    from map_gpu_annotations import AnnotationCache,paint_annotations
    from map_vector import build_vector_map,paint_vector_map
    canvas,route=scene(qt_application)
    def render():
        surface=_FrameSurface(canvas);prepared=build_vector_map(surface)
        image=QImage(400,300,QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(MAP_BACKGROUND);painter=QPainter(image)
        try:
            if renderer=='canvas':surface._paint(painter,overlays=False)
            elif renderer=='vector':paint_vector_map(painter,surface,prepared,overlays=False)
            else:paint_annotations(painter,surface,prepared,AnnotationCache(surface,prepared))
        finally:painter.end()
        return bytes(image.constBits())
    try:
        actual=render()
        # Removing the annotation record, while keeping every route control
        # and path, is the exact visual reference for a hidden waypoint.
        canvas.set_snapshot(replace(canvas.snapshot,stops=tuple(s for s in canvas.snapshot.stops if s.id!=2)))
        assert actual==render()
        assert canvas.snapshot.routes==(route,)
    finally:canvas.close()
