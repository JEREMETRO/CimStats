"""Depot identity and serialized leg ordering survive geometry preparation."""
from dataclasses import asdict
import pytest


def geometry_data():
    return {'roads':{1:{'id':1,'curves':[[[0,0,0],[30,0,0],[70,0,0],[100,0,0]]]}},
        'buildings':[{'id':90,'kind':'DepotData','name':'真实库','position':[20,0,-50]}],
        'lines':[{'id':42,'number':1,'name':'','stops':[
            {'id':90,'position':[20,0,-50],'name':'真实库'},
            {'id':1,'position':[0,0,0],'name':'首站'},
            {'id':2,'position':[100,0,0],'name':'末站'}],
            'legs':[{'roads':[{'id':1,'reverse':False,'mask':1}]},
                    {'roads':[{'id':1,'reverse':False,'mask':1}]},
                    {'roads':[{'id':1,'reverse':True,'mask':1}]}]}]}


def test_depot_position_is_saved_object_position_and_legs_keep_outbound_inbound():
    from map_geometry import snapshot_from_data,_decode_snapshot
    snapshot=snapshot_from_data(geometry_data());route=snapshot.routes[0]
    assert route.depot_id==90 and route.depot_name=='真实库'
    assert route.depot_position==(20,0,-50)
    assert len(route.depot_leg_paths)==2
    assert route.depot_leg_paths[0][0][0]==(0.,0.,0.)
    assert route.depot_leg_paths[1][0][0]==(100.,0.,0.)
    assert tuple(p for leg in route.depot_leg_paths for p in leg)==route.depot_paths
    assert _decode_snapshot(asdict(snapshot))==snapshot


def test_legacy_snapshot_leaves_unrecorded_depot_identity_unknown():
    from map_geometry import snapshot_from_data,_decode_snapshot
    saved=asdict(snapshot_from_data(geometry_data()))
    for key in ('depot_leg_paths','depot_id','depot_name','depot_position'):saved['routes'][0].pop(key,None)
    route=_decode_snapshot(saved).routes[0]
    assert route.depot_id is None and route.depot_position is None and route.depot_leg_paths==()
