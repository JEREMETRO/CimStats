"""Opt-in private-save acceptance; no production imports of experiment data."""
import hashlib
import json
import os
import math
from pathlib import Path
import pytest
from map_geometry import MapGeometryService, SCHEMA_VERSION
from map_model import SOCIAL_GROUPS,building_function_values

ROOT=Path(os.environ.get('CIM2_MAP_REFERENCE_ROOT',''))
SAVES=Path(os.environ.get('CIM2_MAP_TEST_SAVES',''))
pytestmark=pytest.mark.skipif(not os.environ.get('CIM2_MAP_TEST_SAVES') or not os.environ.get('CIM2_MAP_REFERENCE_ROOT'),reason='Private map saves/references not configured')


@pytest.mark.parametrize('save_name,batch',[
    ('秋山市n6 (2).save','qiushan-direction-review-20261007'),
    ('秋山市n6 (4).save','qiushan-extra10-20261007'),
])
def test_thirty_real_line_regressions(save_name,batch):
    save=SAVES/save_name
    before=hashlib.sha256(save.read_bytes()).hexdigest()
    service=MapGeometryService(cache_dir=Path('jobs/map-implementation/real-test-cache'))
    snapshot=service.load(save,use_disk_cache=False)
    assert snapshot.source_hash==before
    assert hashlib.sha256(save.read_bytes()).hexdigest()==before
    assert snapshot.buildings and snapshot.roads
    assert snapshot.schema_version==SCHEMA_VERSION
    assert all(tuple(r.group for r in b.function_capacities)==SOCIAL_GROUPS for b in snapshot.buildings)
    assert all(isinstance(v,int) and v>=0 for b in snapshot.buildings
               for r in b.function_capacities for v in (r.home,r.work,r.leisure))
    assert any(building_function_values(b).home>0 for b in snapshot.buildings)
    assert any(building_function_values(b).work>0 for b in snapshot.buildings)
    assert any(building_function_values(b).leisure>0 for b in snapshot.buildings)
    for b in snapshot.buildings:
        values=building_function_values(b)
        assert values.denominator==max(values.home,values.work,values.leisure)
        assert building_function_values(b,('BlueCollar',)).denominator==values.denominator
        assert all(r.leisure is None for r in b.function_population)
    assert sum(bool(b.polygon) for b in snapshot.buildings)>len(snapshot.buildings)*.95
    assert any(r.track for r in snapshot.roads)
    assert any(r.bridge for r in snapshot.roads)
    assert any(r.tunnel for r in snapshot.roads)
    assert snapshot.junctions
    assert sum(len(j.connections) for j in snapshot.junctions)>len(snapshot.junctions)
    roads={r.id:r for r in snapshot.roads}
    assert all(c.source_road_id in roads and c.target_road_id in roads
               for j in snapshot.junctions for c in j.connections)
    assert all(len(c.paths)==1 and len(c.paths[0])>=9
               for j in snapshot.junctions for c in j.connections)
    assert all(r.company_id and r.company_index is not None for r in snapshot.routes)
    assert all(r.previous_day_passengers is None and r.passenger_diagnostic for r in snapshot.routes)
    displayed=[r for r in snapshot.routes if r.mode!='waterbus']
    assert all(math.dist(a[-1],b[0])<=.05 for r in displayed for leg in r.leg_paths for a,b in zip(leg,leg[1:]))
    assert all(math.dist(a[-1][-1],b[0][0])<=.05 for r in displayed for a,b in zip(r.leg_paths,r.leg_paths[1:]) if a and b)
    actual={r.id:r for r in snapshot.routes}
    reference=json.loads((ROOT/batch/'识别结果.json').read_text(encoding='utf-8'))
    results=[]
    for expected in reference['records']:
        route=actual[expected['line_id']]
        assert route.diagnostic is None,(route.id,route.diagnostic)
        assert len(route.stop_ids)==expected['stop_count']
        assert len(route.leg_paths)==len(route.stop_ids)-1
        assert route.depot_paths
        assert route.paths==tuple(p for leg in route.leg_paths for p in leg)
        if expected.get('name','').startswith('5P'):
            assert route.direction.kind=='one_way'
            assert route.direction.terminal_index is None
        else:
            kind='roundtrip' if expected['terminal_station'] else 'circular'
            assert route.direction.kind==kind,(route.id,route.direction)
            assert route.direction.terminal_index==(expected['terminal_station']-1 if expected['terminal_station'] else None),(route.id,route.direction)
        if route.id==823859:
            assert route.direction.terminal_index==13
            stops={s.id:s for s in snapshot.stops}
            assert stops[route.stop_ids[13]].name=='东北转车站E2'
        results.append(dict(id=route.id,kind=route.direction.kind,terminal=route.direction.terminal_index))
    # Normal operation reuses only this service's current in-memory snapshot.
    cached=service.load(save,use_disk_cache=False)
    assert cached is snapshot
    Path(f'jobs/map-implementation/regression-{batch}.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
