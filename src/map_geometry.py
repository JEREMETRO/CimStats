"""Read-only map extraction, isolated runtime worker and atomic snapshot cache.

The public service has no CLR/Qt imports and can be called from any background
thread. Runtime assemblies are only loaded inside a separate process.
"""
from __future__ import annotations
from collections import Counter
from dataclasses import asdict
import gzip
import hashlib
import json
import math
import os
from pathlib import Path as FilePath
import re
import runpy
import shutil
import struct
import subprocess
import sys
import tempfile
import threading

from map_model import (GroupCount, GroupFunctionCount, MapBuilding, MapRoad, MapRoute, MapSnapshot,
                       MapStop, MapLane, MapJunction, MapJunctionConnection, RouteDirection, polygon_area)
from map_analysis import infer_direction
from display_rules import format_line_name

def runtime_root():
    """Source checkout root or the PyInstaller bundle root, never its parent."""
    if getattr(sys,'frozen',False):
        return FilePath(getattr(sys,'_MEIPASS',FilePath(sys.executable).resolve().parent))
    return FilePath(__file__).resolve().parents[1]


def probe_script():
    # SCRIPT_DATA retains this helper inside src even when Python modules are
    # collected at the top of the frozen bundle.
    return runtime_root()/'src'/'patch_singleton_probe.py'


PROJECT = runtime_root()
SCHEMA_VERSION = 9
SOCIAL_GROUPS = ('BlueCollar','WhiteCollar','Student','BusinessPeople','Pensioner','Tourist')


def native_distribution_tables(assembly_path):
    """Read the game's distribution initializers without running Unity code."""
    import dnfile
    pe=dnfile.dnPE(str(assembly_path))
    try:
        fields={str(row.Name):0x04000000|i for i,row in enumerate(pe.net.mdtables.Field,1)}
        tables={}
        for role,name in (('home','$$field-10'),('leisure','$$field-11')):
            token=fields[name]
            row=next(r for r in pe.net.mdtables.FieldRva if r.Field.row_index==(token&0xffffff))
            values=struct.unpack('<72i',pe.get_data(row.Rva,288))
            tables[role]=[list(values[i:i+6]) for i in range(0,72,6)]
        td=next(t for t in pe.net.mdtables.TypeDef if str(t.TypeName)=='CityManager')
        method=next(m.row for m in td.MethodList if str(m.row.Name)=='Awake')
        header=pe.get_data(method.Rva,12)
        size=header[0]>>2 if header[0]&3==2 else struct.unpack_from('<I',header,4)[0]
        header_size=1 if header[0]&3==2 else (struct.unpack_from('<H',header)[0]>>12)*4
        body=pe.get_data(method.Rva+header_size,size)
        start=body.index(b'\x7d'+struct.pack('<I',fields['m_homeDistribution']))+5
        end=body.index(b'\x7d'+struct.pack('<I',fields['m_workPlaceDistribution']),start)
        code=body[start:end]; i=0; literals=[]; work=[[0]*6 for _ in range(12)]; dimensions=False
        while i<len(code):
            op=code[i]; i+=1
            if op in (0x02,0x25): continue  # this, array duplicate
            if 0x16<=op<=0x1e: literals.append(op-0x16)
            elif op==0x1f: literals.append(struct.unpack_from('<b',code,i)[0]); i+=1
            elif op==0x20: literals.append(struct.unpack_from('<i',code,i)[0]); i+=4
            elif op in (0x73,0x28):
                token=struct.unpack_from('<I',code,i)[0]; i+=4
                member=pe.net.mdtables.MemberRef.rows[(token&0xffffff)-1] if token>>24==0x0a else None
                name=str(member.Name) if member else ''
                if op==0x73 and name=='.ctor' and literals==[12,6]: dimensions=True
                elif op==0x28 and name=='Set' and dimensions and len(literals)==3:
                    row,col,value=literals
                    if not (0<=row<12 and 0<=col<6 and 0<=value<=100): raise ValueError('Invalid native distribution')
                    work[row][col]=value
                else: raise ValueError('Unsupported native distribution initializer')
                literals=[]
            else: raise ValueError('Unsupported native distribution opcode')
        if not dimensions or literals: raise ValueError('Incomplete native distribution initializer')
        tables['work']=work
        return tables
    finally:
        pe.close()


def native_citizen_multiplier(items):
    """RulesetData.Apply uses 100 for an absent key and integer Q10 scale 512."""
    if items is None: return None
    percent=next((int(value) for category,key,value in items
                  if category=='general' and key=='citizen-amount'),100)
    return percent*512//100


def native_function_capacities(metadata,multiplier,tables):
    """Native Buildings dataview quantities, preserving unknown and true zero."""
    area=metadata.get('area_type') if metadata else None
    known_area=isinstance(area,int) and 0<=area<12
    result=[dict(group=group) for group in SOCIAL_GROUPS]
    for role,key in (('home','homes'),('work','work'),('leisure','recreation')):
        base=metadata.get(key) if metadata else None
        amount=None
        if base==0: amount=0
        elif isinstance(base,int) and base>=0:
            if role=='leisure': amount=base
            elif multiplier is not None: amount=(base*multiplier+1023)//1024
        distribution=tables.get(role) if tables else None
        for i,row in enumerate(result):
            row[role]=0 if amount==0 else ((amount*distribution[area][i]+99)//100
                if amount is not None and known_area and distribution is not None else None)
    return result


class MapCancelled(Exception):
    """A cancelled job never publishes a snapshot."""


def _check(cancelled):
    if cancelled and cancelled():
        raise MapCancelled('Map load cancelled')


def _digest(path, cancelled=None):
    h=hashlib.sha256()
    with FilePath(path).open('rb') as f:
        while chunk := f.read(1024*1024):
            _check(cancelled)
            h.update(chunk)
    return h.hexdigest()


def population_groups(residents, workers, groups=SOCIAL_GROUPS):
    """Count citizen identities once per building and once in the role union.

    Inputs are (citizen identity, social group index/name) pairs. Unknown group
    is a measured associated person, not a missing population observation.
    """
    def identities(values):
        out={}
        for identity, group in values:
            if isinstance(group,int) and 0<=group<len(groups):
                group=groups[group]
            if group not in groups:
                group='unknown'
            if identity in out and out[identity]!=group:
                out[identity]='unknown'
            else:
                out[identity]=group
        return out
    def counts(values):
        count=Counter(values.values())
        return tuple(GroupCount(g,count[g]) for g in (*groups,'unknown'))
    a,b=identities(residents),identities(workers)
    union=dict(a)
    for key,group in b.items():
        union[key]='unknown' if key in union and union[key]!=group else group
    return counts(a),counts(b),counts(union)


def sample_curve(controls):
    if len(controls)!=4 or any(p is None or len(p)!=3 or not all(math.isfinite(v) for v in p) for p in controls):
        raise ValueError('Invalid road control points')
    length=sum(math.dist(a,b) for a,b in zip(controls,controls[1:]))
    count=max(8,min(256,math.ceil(length/18)))
    return tuple(tuple(sum(w*p[i] for w,p in zip(((1-t)**3,3*(1-t)**2*t,3*(1-t)*t*t,t**3),controls))
                       for i in range(3)) for t in (j/count for j in range(count+1)))


def actual_lane_attributes(lanes,sidewalk_left=None,sidewalk_right=None):
    """Measure the saved lane masks/offsets, excluding parking from capacity."""
    values=dict(lanes_a=0,lanes_b=0,bus_lanes_a=0,bus_lanes_b=0,parking_lanes_a=0,parking_lanes_b=0,width=None)
    vehicle_modes=0x1f000000
    sidewalk=[]
    for lane in lanes:
        mask=lane['type_mask']
        side='a' if mask&0x100 and not mask&0x200 else 'b' if mask&0x200 and not mask&0x100 else None
        if side and mask&vehicle_modes:
            if mask&4:
                values['parking_lanes_'+side]+=1
            elif mask&3 and not mask&8:
                values['lanes_'+side]+=1
                if mask&2: values['bus_lanes_'+side]+=1
        if mask&0x10000:
            sidewalk.append(lane['offset'])
    # The observed sidewalk centre and stored sidewalk width give the road's
    # outer edge. No assumed vehicle lane width enters this measurement.
    if sidewalk and sidewalk_left is not None and sidewalk_right is not None:
        left=min(sidewalk); right=max(sidewalk)
        if left<0<right:
            values['width']=right-left+(sidewalk_left+sidewalk_right)/2
    return values


def _road_paths(road, reverse=False):
    paths=tuple(sample_curve(c) for c in road.get('curves',()))
    return tuple(p[::-1] for p in paths[::-1]) if reverse else paths


def _project(point,path,prefer_last=False):
    best=None
    for i,(a,b) in enumerate(zip(path,path[1:])):
        delta=tuple(y-x for x,y in zip(a,b))
        length2=sum(v*v for v in delta)
        t=max(0.,min(1.,sum((x-y)*v for x,y,v in zip(point,a,delta))/max(length2,1e-12)))
        p=tuple(x+t*v for x,v in zip(a,delta))
        key=(math.dist(point,p),-i if prefer_last else i)
        if best is None or key<best[0]:
            best=(key,i,p)
    return best


def lane_paths(road,lane,reverse=False):
    """Saved centre cubics + saved signed lane offset, evaluated in 3D.

    Positive offset is the right normal (dz,0,-dx) of the forward road.
    Junction endpoints independently validate this against saved lane cubics.
    """
    result=[];offset=lane['offset']
    for controls in road.get('curves',()):
        centre=sample_curve(controls); count=len(centre)-1; path=[]
        for i,p in enumerate(centre):
            t=i/count
            tangent=tuple(3*((1-t)**2*(controls[1][k]-controls[0][k])+2*(1-t)*t*(controls[2][k]-controls[1][k])+t*t*(controls[3][k]-controls[2][k])) for k in range(3))
            length=math.hypot(tangent[0],tangent[2])
            if length<=1e-10:
                if offset: raise ValueError('Undefined saved lane tangent')
                path.append(p)
            else:
                path.append((p[0]+offset*tangent[2]/length,p[1],p[2]-offset*tangent[0]/length))
        result.append(tuple(path))
    paths=tuple(result)
    return tuple(p[::-1] for p in paths[::-1]) if reverse else paths


def select_lane_chain(references,roads,connections,mode=None):
    """Choose a complete allowed saved lane chain, without lane-change guesses."""
    mode_mask={'bus':1<<24,'tram':1<<25,'trolley':1<<27,'trolleybus':1<<27,
               'metro':1<<26,'monorail':1<<28}.get(mode,0x1f000000)
    states={}; chosen=[]
    for i,ref in enumerate(references):
        road=roads.get(ref['id']) or roads.get(str(ref['id']))
        if road is None: return None,None,(f"missing_road:{ref['id']}",)
        direction=0x200 if ref.get('reverse') else 0x100
        allowed={v['index']:v for v in road.get('lanes',())
                 if ref.get('min_lane',-1)<=v['index']<=ref.get('max_lane',-1)
                 and v['type_mask']&direction and v['type_mask']&mode_mask}
        # Parking-marked approach lanes can have saved turn destinations and
        # be explicitly allowed by the path range. Do not erase that topology.
        if not allowed: return None,None,(f"invalid_lane_range:{ref['id']}",)
        if i==0:
            states={key:(abs(v['offset']),(key,),()) for key,v in allowed.items()}
            continue
        previous=references[i-1]; next_states={}
        if ref.get('continuation') and previous['id']==ref['id'] and previous.get('reverse')==ref.get('reverse'):
            next_states={key:(state[0]+abs(allowed[key]['offset']),state[1]+(key,),state[2]+(None,))
                         for key,state in states.items() if key in allowed}
        for c in connections.get((previous['id'],ref['id']),()):
            if ref.get('continuation'): continue
            if c['source_lane'] not in states or c['target_lane'] not in allowed or not c['type_mask']&mode_mask: continue
            cost,lanes,chain=states[c['source_lane']]
            candidate=(cost+abs(allowed[c['target_lane']]['offset']),lanes+(c['target_lane'],),chain+(c,))
            key=c['target_lane']; old=next_states.get(key)
            rank=lambda s:(s[0],s[1],tuple(v['id'] if v else 0 for v in s[2]))
            if old is None or rank(candidate)<rank(old): next_states[key]=candidate
        if not next_states:
            return None,None,(f"missing_lane_connection:{previous['id']}:{ref['id']}",)
        states=next_states
    if not states: return (),(),()
    best=min(states.values(),key=lambda s:(s[0],s[1],tuple(v['id'] if v else 0 for v in s[2])))
    return best[1],best[2],()


def route_leg(references, roads, start=None, end=None, *, connections=None, mode=None, lane_selection=None):
    """Keep every real curve; clip only endpoint roads, never bridge a gap."""
    paths=[]; issues=[]; previous=None; source_indices=[]
    lane_indices=selected_connections=None
    if lane_selection is not None:
        lane_indices,selected_connections=lane_selection
    elif connections is not None:
        lane_indices,selected_connections,di=select_lane_chain(references,roads,connections,mode)
        issues.extend(di)
    for index,ref in enumerate(references):
        rid=ref['id']; road=roads.get(rid) or roads.get(str(rid))
        if road is None:
            issues.append(f'missing_road:{rid}'); previous=None
            continue
        mask=ref.get('mask')
        if mask is not None and bool(mask&1)==bool(mask&2):
            issues.append(f'ambiguous_road_direction:{rid}')
        reverse=ref.get('reverse',False)
        first=road.get('end' if reverse else 'start'); last=road.get('start' if reverse else 'end')
        if previous is not None and first is not None and previous!=first:
            issues.append(f'junction_discontinuity:{rid}')
        previous=last
        try:
            if lane_indices is None:
                current=_road_paths(road,reverse)
            else:
                lane=next(v for v in road['lanes'] if v['index']==lane_indices[index])
                current=lane_paths(road,lane,reverse)
        except (ValueError,TypeError):
            issues.append(f'invalid_curve:{rid}'); continue
        if not current:
            issues.append(f'empty_road:{rid}')
        if selected_connections and index:
            c=selected_connections[index-1]; connector=_road_paths(c)
            if paths and current and connector:
                # Use the actual stored fixed-point endpoint, replacing only
                # sub-2cm floating normalization differences; never draw a
                # connector segment across an unobserved gap.
                if math.dist(paths[-1][-1],connector[0][0])<=.02:
                    paths[-1]=paths[-1][:-1]+(connector[0][0],)
                else: issues.append(f"lane_connection_start_gap:{c['id']}")
                if math.dist(current[0][0],connector[-1][-1])<=.02:
                    current=((connector[-1][-1],)+current[0][1:],)+current[1:]
                else: issues.append(f"lane_connection_end_gap:{c['id']}")
            paths.extend(connector); source_indices.extend([index-.5]*len(connector))
        paths.extend(current); source_indices.extend([index]*len(current))
    if not paths:
        return (),tuple(issues or ['empty_path'])
    # Endpoint projection is restricted to the actual first/last referenced
    # roads. Missing endpoint roads cannot be silently replaced by another.
    lo,hi=0,len(paths)-1
    start_projection=end_projection=None
    if start is not None and source_indices[0]==0:
        choices=[(_project(start,p),i) for i,p in enumerate(paths) if source_indices[i]==0 and len(p)>1]
        if choices:
            projection,lo=min(choices,key=lambda v:(v[0][0][0],v[1]))
            if projection[0][0]>250:
                issues.append('start_projection_distant')
            start_projection=projection
    if end is not None and source_indices[-1]==len(references)-1:
        choices=[(_project(end,p,True),i) for i,p in enumerate(paths) if source_indices[i]==len(references)-1 and len(p)>1]
        if choices:
            projection,hi=min(choices,key=lambda v:(v[0][0][0],-v[1]))
            if projection[0][0]>250:
                issues.append('end_projection_distant')
            end_projection=projection
    reversed_same=False
    if lo==hi and start_projection and end_projection:
        sj,sp=start_projection[1:]; ej,ep=end_projection[1:]
        reversed_same=sj>ej or (sj==ej and math.dist(paths[lo][sj],sp)>math.dist(paths[hi][ej],ep)+1e-6)
    if lo>hi or reversed_same:
        return tuple(paths),tuple(issues+['reversed_station_projection'])
    if lo==hi and start_projection and end_projection:
        sj,sp=start_projection[1:]; ej,ep=end_projection[1:]
        paths[lo]=(sp,)+paths[lo][sj+1:ej+1]+(ep,)
    else:
        if start_projection:
            _,j,p=start_projection; paths[lo]=(p,)+paths[lo][j+1:]
        if end_projection:
            _,j,p=end_projection; paths[hi]=paths[hi][:j+1]+(p,)
    return tuple(p for p in paths[lo:hi+1] if len(p)>1),tuple(issues)


def snapshot_from_data(data, source_hash='', asset_signature='', cancelled=None):
    roads=[]; diagnostics=list(data.get('diagnostics',()))
    raw_roads=data['roads']
    connection_lookup={}
    for junction in data.get('junctions',()):
        for c in junction.get('connections',()):
            connection_lookup.setdefault((c['source_road_id'],c['target_road_id']),[]).append(c)
    for r in raw_roads.values():
        _check(cancelled)
        try:
            paths=_road_paths(r)
        except (ValueError,TypeError):
            paths=(); diagnostics.append(f"invalid_road_curve:{r['id']}")
        roads.append(MapRoad(r['id'],r.get('asset_id',''),r.get('name',''),paths,
                             r.get('lanes_a'),r.get('lanes_b'),r.get('express'),r.get('track',False),
                             r.get('bridge',False),r.get('tunnel',False),r.get('width'),
                             **{k:r[k] for k in ('road_class','one_way','sidewalk_left','sidewalk_right','platform_width',
                                                'bus_lane','parking_lane','shoulder','pedestrian') if k in r},
                             bridge_masks=tuple(r.get('bridge_masks',())),tunnel_masks=tuple(r.get('tunnel_masks',())),
                             **{k:r[k] for k in ('declared_lanes_a','declared_lanes_b','bus_lanes_a','bus_lanes_b',
                                                'parking_lanes_a','parking_lanes_b') if k in r},
                             lanes=tuple(MapLane(**lane) for lane in r.get('lanes',()))))
    buildings=[]
    for b in data.get('buildings',()):
        _check(cancelled)
        population=population_groups(b.get('residents',()),b.get('workers',()))
        polygon=tuple(tuple(p) for p in b.get('polygon',()))
        buildings.append(MapBuilding(b['id'],b.get('asset_id',b.get('prefab','')),b.get('name',''),tuple(b['position']),
                                     polygon,b.get('category','unknown'),population[0],population[1],polygon_area(polygon),population[2],
                                     tuple(GroupFunctionCount(**r) for r in b.get('function_capacities',())),
                                     tuple(GroupFunctionCount(g.group,g.count,next((v.count for v in population[1] if v.group==g.group),None),None) for g in population[0]),
                                     b.get('game_area_type')))
    junctions=[]
    for j in data.get('junctions',()):
        _check(cancelled)
        connections=[]; issues=list(j.get('issues',()))
        for c in j.get('connections',()):
            try:
                paths=_road_paths(c)
            except (ValueError,TypeError):
                paths=(); issues.append(f"invalid_connection_curve:{c['id']}")
            connections.append(MapJunctionConnection(c['id'],c['source_road_id'],c['target_road_id'],
                                                     c['source_lane'],c['target_lane'],c['type_mask'],paths))
        junctions.append(MapJunction(j['id'],tuple(j['position']),tuple(j.get('road_ids',())),tuple(connections),
                                     j.get('bridge',False),j.get('tunnel',False),';'.join(issues) or None))
    stops={int(s['id']):MapStop(int(s['id']),s.get('name',''),tuple(s['position']))
           for s in data.get('stops',{}).values() if s.get('position') is not None}
    depots={b['id'] for b in data.get('buildings',()) if b.get('kind')=='DepotData'}
    routes=[]
    for line in data.get('lines',()):
        _check(cancelled)
        records=line.get('stops',())
        has_depot=bool(records and records[0]['id'] in depots)
        operational=records[1:] if has_depot else records
        for s in operational:
            if s.get('position') is not None:
                stops[s['id']]=MapStop(s['id'],s.get('name',''),tuple(s['position']))
        issues=[]; legs=[]; analysis_legs=[]; depot_paths=[]
        raw_legs=line.get('legs',())
        # Solve all operating legs together. The same saved road at a stop
        # must retain the same allowed lane; independent per-leg choices can
        # otherwise introduce 3m lateral seams at an identical stop.
        lane_selections={}
        if 'junctions' in data and has_depot:
            flat=[]; slices=[]
            for source_index,leg in enumerate(raw_legs[1:-1],1):
                refs=leg.get('roads',()); first=len(flat)
                for ri,ref in enumerate(refs):
                    value=dict(ref)
                    if ri==0 and flat and flat[-1]['id']==ref['id'] and flat[-1].get('reverse')==ref.get('reverse'):
                        value['continuation']=True
                    flat.append(value)
                slices.append((source_index,first,len(flat)))
            selected,chain,di=select_lane_chain(flat,raw_roads,connection_lookup,line.get('mode'))
            if not di:
                lane_selections={i:(selected[a:b],chain[a:max(a,b-1)]) for i,a,b in slices}
            else:
                issues.extend(f'operating_lane_chain:{d}' for d in di)
        # CIM2 serializes depot->first, operational adjacent pairs, last->depot.
        expected=len(records)
        if len(raw_legs)!=expected:
            issues.append('path_leg_count_mismatch')
        if has_depot:
            for i in (0,len(raw_legs)-1):
                if raw_legs:
                    p,di=route_leg(raw_legs[i].get('roads',()),raw_roads,connections=connection_lookup if 'junctions' in data else None,mode=line.get('mode'))
                    depot_paths.extend(p)
                    diagnostics.extend(f"route:{line['id']}:depot:{d}" for d in di)
        else:
            issues.append('missing_depot_identity')
        for i,(a,b) in enumerate(zip(operational,operational[1:])):
            index=i+1 if has_depot else i
            if index>=len(raw_legs):
                legs.append(()); analysis_legs.append(()); issues.append(f'missing_leg:{index}'); continue
            if a.get('position') is None or b.get('position') is None:
                legs.append(()); analysis_legs.append(()); issues.append(f'missing_stop_position:{i}'); continue
            leg=raw_legs[index]
            p,di=route_leg(leg.get('roads',()),raw_roads,a['position'],b['position'],
                           connections=connection_lookup if 'junctions' in data else None,mode=line.get('mode'),
                           lane_selection=lane_selections.get(index))
            legs.append(p)
            # Direction identifies the canonical saved road corridor, not an
            # arbitrary legal lane selected for map display. Lane offsets and
            # the selected turn arc must not move a business terminal index.
            canonical,_=route_leg(leg.get('roads',()),raw_roads,a['position'],b['position'])
            analysis_legs.append(canonical)
            issues.extend(f'leg:{index}:{d}' for d in di)
            if leg.get('dirty'):
                issues.append(f'dirty_path:{index}')
        points=tuple(tuple(s['position']) for s in operational if s.get('position') is not None)
        direction=RouteDirection() if issues or len(points)!=len(operational) else infer_direction(
            points,tuple(analysis_legs),[s.get('name','') for s in operational],lambda:_check(cancelled))
        routes.append(MapRoute(line['id'],format_line_name(line.get('number',0),line.get('name','')),line.get('number',0),line.get('company_id',''),
                               line.get('company',''),line.get('mode',''),tuple(s['id'] for s in operational),
                               tuple(p for leg in legs for p in leg),direction,tuple(legs),tuple(depot_paths),
                               ';'.join(dict.fromkeys(issues)) or None,line.get('company_index'),
                               line.get('previous_day_passengers'),line.get('passenger_date'),
                               line.get('passenger_diagnostic','no_serialized_previous_day_line_passengers')))
    allpoints=[p for r in roads for path in r.paths for p in path]
    allpoints.extend(b.position for b in buildings)
    allpoints.extend(j.position for j in junctions)
    bounds=(min(p[0] for p in allpoints),min(p[2] for p in allpoints),max(p[0] for p in allpoints),max(p[2] for p in allpoints)) if allpoints else (0.,0.,1.,1.)
    return MapSnapshot(tuple(roads),tuple(buildings),tuple(stops.values()),tuple(routes),source_hash,asset_signature,
                       tuple(dict.fromkeys(diagnostics)),bounds,SCHEMA_VERSION,tuple(junctions))


def _decode_snapshot(d):
    def path(v): return tuple(tuple(p) for p in v)
    def paths(v): return tuple(path(p) for p in v)
    def counts(v): return tuple(GroupCount(**c) for c in v)
    roads=tuple(MapRoad(**(r|{'paths':paths(r['paths']),'bridge_masks':tuple(r.get('bridge_masks',())),
                              'tunnel_masks':tuple(r.get('tunnel_masks',())),
                              'lanes':tuple(MapLane(**lane) for lane in r.get('lanes',()))})) for r in d['roads'])
    buildings=tuple(MapBuilding(**(b|{'position':tuple(b['position']),'polygon':path(b['polygon']),
                       'residents':counts(b['residents']),'workers':counts(b['workers']),
                       'combined_groups':counts(b['combined_groups']),
                       'function_capacities':tuple(GroupFunctionCount(**r) for r in b.get('function_capacities',())),
                       'function_population':tuple(GroupFunctionCount(**r) for r in b.get('function_population',()))})) for b in d['buildings'])
    stops=tuple(MapStop(**(s|{'position':tuple(s['position'])})) for s in d['stops'])
    junctions=tuple(MapJunction(**(j|{'position':tuple(j['position']),'road_ids':tuple(j['road_ids']),
                          'connections':tuple(MapJunctionConnection(**(c|{'paths':paths(c['paths'])})) for c in j['connections'])}))
                    for j in d.get('junctions',()))
    routes=[]
    for r in d['routes']:
        direction=r['direction']; direction=RouteDirection(**(direction|{'paired_stations':tuple(tuple(v) for v in direction['paired_stations'])}))
        routes.append(MapRoute(**(r|{'stop_ids':tuple(r['stop_ids']),'paths':paths(r['paths']),
                                      'depot_paths':paths(r['depot_paths']),'leg_paths':tuple(paths(p) for p in r['leg_paths']),
                                      'direction':direction})))
    return MapSnapshot(**(d|{'roads':roads,'buildings':buildings,'stops':stops,'routes':tuple(routes),
                            'diagnostics':tuple(d['diagnostics']),'bounds':tuple(d['bounds']),'junctions':junctions}))


def _discover_bundles(runtime_data, managed):
    candidates=[runtime_data/'game_runtime'/'Bundles',runtime_data/'Bundles',managed.parent/'Bundles']
    if os.environ.get('CIM2_GAME_ROOT'):
        candidates.append(FilePath(os.environ['CIM2_GAME_ROOT'])/'CIM2_Data'/'Data'/'Bundles')
    if os.name=='nt':
        # Respect normal Steam installations and additional library folders.
        steam=[]
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\Valve\Steam') as key:
                steam.append(FilePath(winreg.QueryValueEx(key,'SteamPath')[0]))
        except OSError:
            pass
        steam.extend(FilePath(f'{drive}:/Program Files (x86)/Steam') for drive in 'CDEFGHIJKLMNOPQRSTUVWXYZ')
        libraries=[]
        for root in steam:
            if not root.is_dir(): continue
            libraries.append(root)
            vdf=root/'steamapps'/'libraryfolders.vdf'
            if vdf.is_file():
                libraries.extend(FilePath(v.replace('\\\\','\\')) for v in re.findall(r'"path"\s*"([^"]+)"',vdf.read_text(encoding='utf-8')))
        candidates.extend(p/'steamapps'/'common'/'Cities in Motion 2'/'CIM2_Data'/'Data'/'Bundles' for p in libraries)
    return next((p for p in candidates if p.is_dir() and any(p.rglob('*.bundle'))),None)


class MapGeometryService:
    def __init__(self,cache_dir=None,managed_root=None,runtime_data=None,bundles=None):
        project=runtime_root()
        default_cache=(FilePath(os.environ.get('LOCALAPPDATA',str(FilePath.home()/'AppData'/'Local')))/'CimStats'/'map-cache'
                       if getattr(sys,'frozen',False) else project/'jobs'/'map-cache')
        self.cache_dir=FilePath(cache_dir) if cache_dir else default_cache
        self.managed=FilePath(managed_root or os.environ.get('CIM2_MANAGED_ROOT') or project/'game_runtime'/'Managed')
        self.runtime_data=FilePath(runtime_data or os.environ.get('CIM2_RUNTIME_DATA_DIR') or project/'data')
        self.asset_catalog=self.runtime_data/'map_assets.json'
        configured=bundles or os.environ.get('CIM2_BUNDLES_DIR')
        self.bundles=(FilePath(configured) if configured else None if self.asset_catalog.is_file()
                      else _discover_bundles(self.runtime_data,self.managed))
        self._memory={}; self._lock=threading.Lock()
        self._asset_state=None; self._asset_hash=None

    def _asset_signature(self,cancelled=None):
        files=sorted(self.managed.glob('*.dll'))
        files.extend(self.runtime_data/p for p in ('Assembly-CSharp.probe.dll','UnityEngine.dll'))
        if self.bundles:
            files.extend(sorted(self.bundles.rglob('*.bundle')))
        elif self.asset_catalog.is_file():
            files.append(self.asset_catalog)
        state=tuple((str(p.resolve()),p.stat().st_size,p.stat().st_mtime_ns) for p in files)
        _check(cancelled)
        if state==self._asset_state:
            return self._asset_hash
        h=hashlib.sha256()
        for p in files:
            h.update(p.name.encode()); h.update(_digest(p,cancelled).encode())
        signature=h.hexdigest()
        self._asset_state,self._asset_hash=state,signature
        return signature

    def load(self,save_path,cancelled=None):
        _check(cancelled)
        save=FilePath(save_path).resolve()
        source_hash=_digest(save,cancelled); asset_signature=self._asset_signature(cancelled)
        key=f'{source_hash}-{asset_signature}-v{SCHEMA_VERSION}'
        with self._lock:
            snapshot=self._memory.get(key)
        if snapshot is not None:
            _check(cancelled); return snapshot
        target=self.cache_dir/f'{key}.json.gz'
        if target.is_file():
            try:
                with gzip.open(target,'rt',encoding='utf-8') as f: snapshot=_decode_snapshot(json.load(f))
                if (snapshot.source_hash,snapshot.asset_signature,snapshot.schema_version)!=(source_hash,asset_signature,SCHEMA_VERSION):
                    raise ValueError('Cache identity mismatch')
                _check(cancelled)
                with self._lock: self._memory[key]=snapshot
                return snapshot
            except (OSError,EOFError,ValueError,TypeError,KeyError):
                pass  # Corrupt cache is rebuilt from the real input.
        self.cache_dir.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='map-job-',dir=self.cache_dir) as job:
            job=FilePath(job)
            config=dict(save=str(save),managed=str(self.managed),runtime_data=str(self.runtime_data),
                        bundles=str(self.bundles) if self.bundles else None,job=str(job),
                        asset_catalog=str(self.asset_catalog) if self.asset_catalog.is_file() else None,
                        catalog_cache=str(self.cache_dir/f'assets-v{SCHEMA_VERSION}-{asset_signature}.json'))
            config_path=job/'config.json'; config_path.write_text(json.dumps(config),encoding='utf-8')
            flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
            with (job/'worker.log').open('w',encoding='utf-8') as log:
                command=([sys.executable,'--map-geometry-worker',str(config_path)] if getattr(sys,'frozen',False)
                         else [sys.executable,str(FilePath(__file__).resolve()),'--worker',str(config_path)])
                process=subprocess.Popen(command,
                                         stdout=log,stderr=log,creationflags=flags)
                try:
                    while True:
                        _check(cancelled)
                        try:
                            code=process.wait(timeout=.1); break
                        except subprocess.TimeoutExpired:
                            pass
                finally:
                    if process.poll() is None:
                        process.terminate(); process.wait(timeout=10)
            if code:
                raise RuntimeError('Map runtime extraction failed: '+(job/'worker.log').read_text(encoding='utf-8')[-5000:])
            _check(cancelled)
            data=json.loads((job/'geometry.json').read_text(encoding='utf-8'))
            snapshot=snapshot_from_data(data,source_hash,asset_signature,cancelled)
            if _digest(save,cancelled)!=source_hash:
                raise RuntimeError('Save changed during map extraction')
            if self._asset_signature(cancelled)!=asset_signature:
                raise RuntimeError('Map assets changed during extraction')
            _check(cancelled)
            staging=job/'snapshot.json.gz'
            with gzip.open(staging,'wt',encoding='utf-8',compresslevel=3) as f:
                json.dump(asdict(snapshot),f,ensure_ascii=False,separators=(',',':'))
            _check(cancelled)
            os.replace(staging,target)
        with self._lock: self._memory[key]=snapshot
        return snapshot


def _read_catalog(bundles):
    import UnityPy
    files=sorted(FilePath(bundles).rglob('*.bundle'))
    if not files:
        raise ValueError(f'No game asset bundles found in {bundles}')
    env=UnityPy.load(*(str(p) for p in files))
    catalog={}
    for obj in env.objects:
        if obj.type.name!='MonoBehaviour': continue
        values=vars(obj.read()); identity=values.get('m_id'); script=values.get('m_Script')
        for info in values.get('m_roadTypeInfo',[]):
            info=vars(info) if not isinstance(info,dict) else info
            typ=info['m_type']; typ=vars(typ) if not isinstance(typ,dict) else typ
            record=dict(id=info['m_name'],class_name='RoadTypeInfo',type={k:v for k,v in typ.items() if k.startswith('m_')},transport_links=[])
            key='roadtype:'+record['id']
            if key in catalog and catalog[key]!=record:
                raise ValueError(f'Conflicting road type: {key}')
            catalog[key]=record
        if not isinstance(identity,str) or not identity or script is None: continue
        class_name=str(script.read().m_ClassName)
        if class_name not in ('BuildingObject','DepotObject','LandmarkObject','StopObject','PropObject','TreeObject','RoadObject'): continue
        record=dict(id=identity,class_name=class_name,homes=int(values.get('m_homeCount',0)),
                    work=int(values.get('m_workPlaceCount',0)),recreation=int(values.get('m_recreationValue',0)),outline=[],transport_links=[])
        area=values.get('m_areaType')
        record['area_type']=int(area) if area is not None else None
        generated=values.get('m_generatedInfo')
        if generated is not None and generated.path_id:
            record['outline']=list(vars(generated.read()).get('m_collisionArea') or [])
        if class_name=='StopObject':
            public=any(vars(p.read()).get('m_publicTransport') for p in values.get('m_types',[]) if p.path_id)
            if public:
                pointers=[values.get('m_entrancePrefab')]
                pointers.extend((child if isinstance(child,dict) else vars(child)).get('m_object') for child in values.get('m_children',[]))
                record['transport_links']=[str(vars(p.read()).get('m_id') or '') for p in pointers if p is not None and p.path_id]
        if identity in catalog and catalog[identity]!=record:
            raise ValueError(f'Conflicting asset identity: {identity}')
        catalog[identity]=record
    transport={identity for r in catalog.values() for identity in r['transport_links']}
    for identity,r in catalog.items(): r['transport']=identity in transport
    return catalog


def _restore_lookup(probe,source):
    """Restore metadata lookup only in the freshly generated private probe."""
    import dnfile
    original=FilePath(source).read_bytes(); out=bytearray(FilePath(probe).read_bytes())
    pe=dnfile.dnPE(str(source)); patched=dnfile.dnPE(str(probe))
    try:
        a=[(str(m.Name),m.Rva) for m in pe.net.mdtables.MethodDef]
        b=[(str(m.Name),m.Rva) for m in patched.net.mdtables.MethodDef]
        if len(out)!=len(original) or a!=b: raise ValueError('Probe metadata mismatch')
        for td in pe.net.mdtables.TypeDef:
            for entry in td.MethodList:
                method=entry.row
                if not method.Rva: continue
                offset=pe.get_offset_from_rva(method.Rva); first=original[offset]
                header=1 if first&3==2 else (int.from_bytes(original[offset:offset+2],'little')>>12)*4
                size=first>>2 if header==1 else int.from_bytes(original[offset+4:offset+8],'little')
                if str(td.TypeName)=='DataStoreManager' and str(method.Name) in ('GetPlaceablePrefab','GetRoadTypeInfo'):
                    out[offset:offset+header+size]=original[offset:offset+header+size]
                elif str(td.TypeName).startswith('SingletonGameObject') and str(method.Name)=='get_instance':
                    body=original[offset+header:offset+header+size]
                    if len(body)<6 or body[0]!=0x7e: raise ValueError('Unsupported singleton method')
                    replacement=body[:5]+b'\x2a'
                    if header==1: out[offset]=(6<<2)|2
                    else: out[offset+4:offset+8]=(6).to_bytes(4,'little')
                    out[offset+header:offset+header+6]=replacement
    finally:
        pe.close(); patched.close()
    FilePath(probe).write_bytes(out)


def _install_catalog(e,catalog):
    flags=e.FLAGS|e.System.Reflection.BindingFlags.Static
    new=e.System.Runtime.Serialization.FormatterServices.GetUninitializedObject
    typ=e.ASM.GetType('DataStoreManager'); store=new(typ)
    dictionary_field=typ.GetField('m_placeableObjects',flags)
    dictionary=e.System.Activator.CreateInstance(dictionary_field.FieldType)
    road_field=typ.GetField('m_roadTypes',flags)
    road_dictionary=e.System.Activator.CreateInstance(road_field.FieldType)
    road_info_type=road_dictionary.GetType().GetGenericArguments()[1]
    base=e.ASM.GetType('PlaceableObject'); generated_type=e.ASM.GetType('GeneratedBuildingInfo')
    for r in catalog.values():
        if r['class_name']=='RoadTypeInfo':
            info=new(road_info_type); road_info_type.GetField('m_name',flags).SetValue(info,r['id'])
            type_field=road_info_type.GetField('m_type',flags)
            road_type=e.System.Activator.CreateInstance(type_field.FieldType)
            for name,value in r['type'].items():
                field=road_type.GetType().GetField(name,flags)
                if field.FieldType.IsEnum: value=e.System.Enum.ToObject(field.FieldType,e.System.Int32(value))
                elif str(field.FieldType)=='System.Boolean': value=e.System.Boolean(bool(value))
                else: value=e.System.Int32(value)
                field.SetValue(road_type,value)
            type_field.SetValue(info,road_type); road_dictionary.Add(r['id'],info)
            continue
        typ=e.ASM.GetType(r['class_name'])
        if typ is None or not typ.IsSubclassOf(base): continue
        prefab=new(typ); typ.GetField('m_id',flags).SetValue(prefab,r['id'])
        for name,key in (('m_homeCount','homes'),('m_workPlaceCount','work'),('m_recreationValue','recreation'),('m_areaType','area_type')):
            value=r.get(key); metadata=typ.GetField(name,flags)
            if metadata is not None and value is not None:
                value=e.System.Enum.ToObject(metadata.FieldType,e.System.Int32(value)) if metadata.FieldType.IsEnum else e.System.Int32(value)
                metadata.SetValue(prefab,value)
        field=typ.GetField('m_generatedInfo',flags)
        if field is not None and field.FieldType==generated_type:
            generated=new(generated_type)
            generated_type.GetField('m_collisionArea',flags).SetValue(generated,e.System.Array[e.System.Int32](r['outline']))
            field.SetValue(prefab,generated)
        dictionary.Add(r['id'],prefab)
    dictionary_field.SetValue(store,dictionary)
    road_field.SetValue(store,road_dictionary)
    store.GetType().BaseType.GetField('s_instance',flags).SetValue(None,store)


def _category(meta,kind):
    if kind=='DepotData': return 'transport'
    if kind=='LandmarkData': return 'special'
    if meta is None: return 'unknown'
    if meta.get('transport'): return 'transport'
    roles=sum(meta[k]>0 for k in ('homes','work','recreation'))
    if roles>1: return 'mixed'
    if meta['homes']>0: return 'residential'
    if meta['work']>0: return 'work'
    if meta['recreation']>0: return 'commercial'
    return 'unknown'


def _worker(config):
    job=FilePath(config['job']); runtime=job/'runtime'; runtime.mkdir()
    managed=FilePath(config['managed']); source=managed/'Assembly-CSharp.dll'
    shutil.copy2(FilePath(config['runtime_data'])/'UnityEngine.dll',runtime/'UnityEngine.dll')
    os.environ.update(CIM2_ASSEMBLY_SOURCE=str(source),CIM2_PROBE_OUTPUT=str(runtime/'Assembly-CSharp.probe.dll'))
    # Keep probe preparation in this killable worker, with no orphan subprocess.
    runpy.run_path(str(probe_script()),run_name='__map_probe__')
    _restore_lookup(runtime/'Assembly-CSharp.probe.dll',source)
    os.utime(runtime/'Assembly-CSharp.probe.dll',None)
    os.environ.update(CIM2_RUNTIME_DATA_DIR=str(runtime),CIM2_MANAGED_ROOT=str(managed),CIM2_PAYLOAD_DIR=str(job/'payload'))
    sys.argv=['map_geometry',config['save']]
    import extract_runtime_data as e
    catalog={}; asset_cache=FilePath(config['catalog_cache'])
    if config['bundles']:
        try:
            catalog=json.loads(asset_cache.read_text(encoding='utf-8'))
        except (OSError,ValueError):
            catalog=_read_catalog(config['bundles'])
            staging=job/'assets.json'; staging.write_text(json.dumps(catalog,ensure_ascii=False),encoding='utf-8')
            os.replace(staging,asset_cache)
    elif config.get('asset_catalog'):
        catalog=json.loads(FilePath(config['asset_catalog']).read_text(encoding='utf-8'))
    _install_catalog(e,catalog)
    print(f'assets:{len(catalog)}',flush=True)
    root,_=e.load_root(True); print('deserialized',flush=True)
    data=_extract_objects(e,root,catalog)
    (job/'geometry.json').write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')),encoding='utf-8')


def _extract_objects(e,root,catalog):
    # pythonnet reflection metadata lookup is expensive for hundreds of
    # thousands of associations. Cache by managed wrapper type and field name;
    # GetValue still reads the actual object, never a cached observation.
    field_cache={}
    def field(obj,name):
        if obj is None: return None
        key=(type(obj),name)
        if key not in field_cache:
            field_cache[key]=obj.GetType().GetField(name,e.FLAGS)
        metadata=field_cache[key]
        return metadata.GetValue(obj) if metadata is not None else None
    array=e.array_values
    rules=field(field(root,'m_rulesetManagerData'),'m_ruleset')
    items=field(rules,'m_items')
    rule_values=None if items is None else [(str(field(entry.Key,'m_category') or ''),str(field(entry.Key,'m_id') or ''),int(entry.Value)) for entry in items]
    multiplier=native_citizen_multiplier(rule_values)
    try:
        tables=native_distribution_tables(e.SOURCE_ASSEMBLY)
    except (OSError,ValueError,KeyError,StopIteration,AttributeError,struct.error) as error:
        print(f'native_distribution_unavailable:{type(error).__name__}:{error}',flush=True)
        tables=None
    print(f'native_home_work_multiplier:{multiplier}',flush=True)
    refs={}; next_ref=-1
    def identity(obj):
        nonlocal next_ref
        if obj is None: return 0
        oid=field(obj,'m_objectID')
        if oid is None: oid=field(obj,'m_citizenID')
        if oid is not None and int(oid)!=0: return int(oid)
        h=int(e.System.Runtime.CompilerServices.RuntimeHelpers.GetHashCode(obj))
        bucket=refs.setdefault(h,[])
        for other,key in bucket:
            if e.System.Object.ReferenceEquals(obj,other): return key
        key=next_ref; next_ref-=1; bucket.append((obj,key)); return key
    def vector(obj):
        return tuple(int(field(obj,axis))/1024 for axis in ('x','y','z')) if obj is not None else None
    def citizens(values):
        result=[]
        for c in array(values):
            if c is not None:
                group=field(c,'m_socialGroup')
                result.append((identity(c),str(group) if group is not None else None))
        return result
    unique={}; divisions=field(field(root,'m_objectManagerData'),'m_divisions')
    for ix in range(divisions.GetLength(0)):
        for iz in range(divisions.GetLength(1)):
            cell=divisions.GetValue(ix,iz)
            for collection in ('m_largeObjects','m_smallObjects'):
                for obj in array(field(cell,collection)):
                    if obj is not None: unique.setdefault((str(obj.GetType().Name),identity(obj)),obj)
    roads={}; buildings=[]; stops={}; diagnostics=[]; junctions={}; road_objects={}
    def junction_record(obj):
        if obj is None: return
        oid=identity(obj)
        if oid in junctions: return
        position=vector(field(obj,'m_position'))
        if position is None:
            diagnostics.append(f'missing_junction_position:{oid}'); return
        linked=[identity(field(r,'m_road')) for r in array(field(obj,'m_roads')) if field(r,'m_road') is not None]
        junctions[oid]=dict(id=oid,position=position,road_ids=linked,bridge=bool(field(obj,'m_bridge')),
                            tunnel=bool(field(obj,'m_tunnel')),connections=[],issues=[])
    refresh=e.ASM.GetType('BuildingData').GetMethod('RefreshCollisionArea',e.FLAGS)
    for (kind,oid),obj in unique.items():
        if kind=='RoadData':
            road_objects[oid]=obj
            junction_record(field(obj,'m_startJunction')); junction_record(field(obj,'m_endJunction'))
            segments=array(field(obj,'m_segments')); typ=field(obj,'m_type'); info=field(obj,'m_typeInfo')
            asset=field(info,'m_roadPrefab')
            lanes_a=field(typ,'m_laneCountA'); lanes_b=field(typ,'m_laneCountB')
            track=str(field(typ,'m_type')) in ('Track','Tram','Monorail')
            # Track is serialized in road segment type masks even when the
            # metadata-only runtime omits a RoadTypeInfo prefab dictionary.
            saved_lanes=array(field(obj,'m_lanes'))
            lane_records=[dict(index=i,type_mask=int(field(lane,'m_typeMask') or 0),
                               turn_directions=int(field(lane,'m_directions') or 0),
                               offset=int(field(lane,'m_offset') or 0)/1024) for i,lane in enumerate(saved_lanes)]
            road_name=str(field(info,'m_name') or '')
            road_kind=str(field(typ,'m_type'))
            express=bool(field(typ,'m_expressWay')) if typ is not None else None
            pedestrian=bool(field(typ,'m_pedestrianStreet')) if typ is not None else None
            road_class={'Track':'rail','Tram':'tram_track','Monorail':'monorail_track'}.get(road_kind)
            if road_class is None:
                road_class='expressway' if express else 'pedestrian' if pedestrian else 'avenue' if road_name=='avenue' else 'ordinary' if road_kind in ('Road','Trolley') else 'unknown'
            extras=dict(road_class=road_class,one_way=(int(lanes_a)==0)!=(int(lanes_b)==0) if lanes_a is not None and lanes_b is not None else None,
                        pedestrian=pedestrian)
            for out_name,in_name in (('sidewalk_left','m_sidewalkWidthL'),('sidewalk_right','m_sidewalkWidthR'),('platform_width','m_platformWidth')):
                value=field(typ,in_name); extras[out_name]=int(value)/1024 if value is not None else None
            for out_name,in_name in (('bus_lane','m_busLane'),('parking_lane','m_parkingLane'),('shoulder','m_shoulder')):
                value=field(typ,in_name); extras[out_name]=bool(value) if value is not None else None
            actual=actual_lane_attributes(lane_records,extras['sidewalk_left'],extras['sidewalk_right'])
            if saved_lanes:
                extras['one_way']=(actual['lanes_a']==0)!=(actual['lanes_b']==0)
            else:
                actual.update(lanes_a=None,lanes_b=None,bus_lanes_a=None,bus_lanes_b=None,parking_lanes_a=None,parking_lanes_b=None)
                extras['one_way']=None
            roads[str(oid)]=dict(id=oid,asset_id=road_name or str(field(asset,'m_id') or ''),name=road_name or road_kind,
                curves=[[vector(field(s,k)) for k in ('m_v1','m_v2','m_v3','m_v4')] for s in segments],
                start=identity(field(obj,'m_startJunction')),end=identity(field(obj,'m_endJunction')),
                declared_lanes_a=int(lanes_a) if lanes_a is not None else None,declared_lanes_b=int(lanes_b) if lanes_b is not None else None,
                lanes=lane_records,**actual,
                express=express,track=track,**extras,
                bridge=any(int(field(s,'m_bridgeMask') or 0) for s in segments),tunnel=any(int(field(s,'m_tunnelMask') or 0) for s in segments),
                bridge_masks=[int(field(s,'m_bridgeMask') or 0) for s in segments],tunnel_masks=[int(field(s,'m_tunnelMask') or 0) for s in segments])
        elif kind in ('BuildingData','DepotData','LandmarkData'):
            position=vector(field(obj,'m_position'))
            if position is None:
                diagnostics.append(f'missing_building_position:{oid}'); continue
            prefab=field(obj,'m_prefabObject'); asset_id=str(field(prefab,'m_id') or '')
            metadata=catalog.get(asset_id); polygon=[]
            if metadata and len(metadata['outline'])>=6 and len(metadata['outline'])%2==0:
                refresh.Invoke(obj,None)
                # Collision areas are FixedVector2 (x,z), not FixedVector3.
                polygon=[(int(field(p,'x'))/1024,position[1],int(field(p,'z'))/1024)
                         for p in array(field(obj,'m_collisionArea'))]
            buildings.append(dict(id=oid,kind=kind,asset_id=asset_id,name=str(field(obj,'m_name') or ''),position=position,
                                  polygon=polygon,category=_category(metadata,kind),residents=citizens(field(obj,'m_residents')),
                                  workers=citizens(field(obj,'m_employees')),game_area_type=metadata.get('area_type') if metadata else None,
                                  function_capacities=native_function_capacities(metadata,multiplier,tables)))
        elif kind=='StopData':
            stops[str(oid)]=dict(id=oid,name=str(field(obj,'m_name') or ''),position=vector(field(obj,'m_position')))
        elif kind=='JunctionData':
            junction_record(obj)
    # JunctionData has no serialized footprint. Its actual turning geometry
    # lives in each saved lane's RoadLaneDestination linked list.
    for source_id,obj in road_objects.items():
        source=roads[str(source_id)]
        for source_lane,lane in enumerate(array(field(obj,'m_lanes'))):
            destination=field(lane,'m_destinations'); seen_destinations=set()
            while destination is not None:
                cid=identity(destination)
                if cid in seen_destinations:
                    diagnostics.append(f'lane_destination_cycle:{source_id}:{source_lane}'); break
                seen_destinations.add(cid)
                target_id=identity(field(destination,'m_road'))
                target=roads.get(str(target_id))
                controls=[vector(field(destination,key)) for key in ('m_v1','m_v2','m_v3','m_v4')]
                if target is None or any(p is None for p in controls):
                    diagnostics.append(f'invalid_lane_destination:{source_id}:{source_lane}:{target_id}')
                else:
                    common={source['start'],source['end']}&{target['start'],target['end']}
                    common={key for key in common if key in junctions}
                    if common:
                        # U-turns share both ends of one road; use saved curve
                        # endpoints to associate the connection, not to invent it.
                        center=tuple((a+b)/2 for a,b in zip(controls[0],controls[-1]))
                        jid=min(common,key=lambda key:(math.dist(center,junctions[key]['position']),key))
                        junctions[jid]['connections'].append(dict(id=cid,source_road_id=source_id,target_road_id=target_id,
                            source_lane=source_lane,target_lane=int(field(destination,'m_lane') or 0),
                            type_mask=int(field(destination,'m_types') or 0),curves=[controls]))
                    else:
                        diagnostics.append(f'lane_destination_without_shared_junction:{source_id}:{target_id}')
                destination=field(destination,'m_next')
    print(f'junctions:{len(junctions)},connections:{sum(len(j["connections"]) for j in junctions.values())}',flush=True)
    print(f'roads:{len(roads)},buildings:{len(buildings)}',flush=True)
    players=array(field(root,'m_players')); transport=field(root,'m_transportManagerData')
    line=field(transport,'m_firstLine'); lines=[]; seen=set()
    histories=array(field(field(root,'m_dataManagerData'),'m_historyData'))
    print('history_names:'+json.dumps(sorted({str(field(h,'m_name')) for h in histories}),ensure_ascii=True),flush=True)
    if line is not None:
        print('line_fields:'+','.join(str(f.Name) for f in line.GetType().GetFields(e.FLAGS)),flush=True)
    while line is not None:
        oid=identity(line)
        if oid in seen: raise ValueError('Line linked list cycle')
        seen.add(oid)
        owner=field(field(line,'m_depot'),'m_owner')
        owner_index=next((i for i,p in enumerate(players) if owner is not None and e.System.Object.ReferenceEquals(owner,field(p,'m_companyData'))),None)
        company_id=str(field(players[owner_index],'m_id') or '') if owner_index is not None else ''
        legs=[]; line_stops=[]
        for i,stop in enumerate(array(field(line,'m_stops'))):
            actual=field(stop,'m_stop')
            line_stops.append(dict(id=identity(actual),name=str(field(actual,'m_name') or ''),position=vector(field(actual,'m_position'))))
            references=[]
            for segment in array(field(stop,'m_path')):
                road=field(segment,'m_road')
                if road is None: continue  # Station connector, not a road.
                mask=int(field(segment,'m_typeMask') or 0)
                references.append(dict(id=identity(road),mask=mask,reverse=bool(mask&2) and not bool(mask&1),
                                       min_lane=int(field(segment,'m_minLane') or 0),max_lane=int(field(segment,'m_maxLane') or 0)))
            legs.append(dict(index=i,dirty=bool(field(stop,'m_pathDirty')),roads=references))
        lines.append(dict(id=oid,name=str(field(line,'m_name') or ''),number=int(field(line,'m_number') or 0),
                          mode=str(field(field(line,'m_type'),'m_id') or ''),company=str(field(owner,'m_name') or ''),
                          company_id=company_id,company_index=owner_index,stops=line_stops,legs=legs,
                          previous_day_passengers=None,passenger_date=None,
                          passenger_diagnostic='no_serialized_previous_day_line_passengers'))
        line=field(line,'m_nextLine')
    if len(lines)!=int(field(transport,'m_lineCount')): raise ValueError('Line manager count mismatch')
    if not catalog: diagnostics.append('building_asset_catalog_unavailable')
    diagnostics.append('previous_day_line_passengers_unavailable')
    return dict(roads=roads,buildings=buildings,stops=stops,lines=lines,diagnostics=diagnostics,junctions=list(junctions.values()))


def worker_main(config_path):
    """Frozen app entrypoint must dispatch --map-geometry-worker before Qt."""
    _worker(json.loads(FilePath(config_path).read_text(encoding='utf-8')))


if __name__=='__main__':
    if len(sys.argv)==3 and sys.argv[1]=='--worker':
        worker_main(sys.argv[2])
    else:
        raise SystemExit('map_geometry is a library; use MapGeometryService.load')

