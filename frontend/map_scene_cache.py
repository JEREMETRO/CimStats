"""A byte/count bounded cache of CPU scene variants for the current source.

Accounting uses immutable owners, rather than retaining an object registry for
millions of saved coordinates. Shared scene/array owners are counted once.
Source geometry uses conservative coordinate/path size estimates; no snapshot,
annotation glyph cache, paint surface or GL resource is retained.
"""
from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
import sys

import numpy as np
from PySide6.QtGui import QColor, QPainterPath, QPolygonF


_POINT_BYTES=sys.getsizeof((0.,0.,0.))+3*max(sys.getsizeof(0.),sys.getsizeof(1<<64))


def option_value(value):
    """Make option values immutable without conflating types or identities."""
    if isinstance(value,QColor):return QColor,value.spec(),value.getRgbF()
    if isinstance(value,Mapping):
        return type(value),frozenset((option_value(k),option_value(v)) for k,v in value.items())
    if isinstance(value,(set,frozenset)):
        return frozenset,frozenset(option_value(v) for v in value)
    if isinstance(value,(tuple,list)):
        return type(value),tuple(option_value(v) for v in value)
    if is_dataclass(value) and not isinstance(value,type):
        return type(value),tuple((f.name,option_value(getattr(value,f.name))) for f in fields(value))
    return type(value),value


def _estimated_bytes(value,cancelled=None,*,skip_models=False):
    """Conservative payload size; temporary visited set is released immediately.

    Saved paths have homogeneous xyz point tuples. Counting their full owned
    point storage by length avoids visiting/retaining each Python coordinate.
    Model records in derived templates are charged to the source owners.
    """
    seen=set();pending=[value];total=0
    while pending:
        if cancelled is not None and cancelled():raise InterruptedError()
        item=pending.pop();identity=id(item)
        if identity in seen:continue
        seen.add(identity)
        if skip_models and type(item).__module__=='map_model':continue
        total+=sys.getsizeof(item)
        if isinstance(item,np.ndarray):
            if item.base is not None:pending.append(item.base)
        elif isinstance(item,memoryview):pending.append(item.obj)
        elif isinstance(item,QPainterPath):total+=128+item.capacity()*32
        elif isinstance(item,QPolygonF):total+=64+item.capacity()*16
        elif isinstance(item,Mapping):
            if not isinstance(item,dict):total+=128+len(item)*64
            pending.extend(item.keys());pending.extend(item.values())
        elif isinstance(item,(tuple,list)):
            if item and isinstance(item[0],tuple) and len(item[0])==3 and all(type(v) in (float,int) for v in item[0]):
                total+=len(item)*_POINT_BYTES
            elif item and all(type(v) in (float,int,bool,type(None)) for v in item):
                # Numeric tuples are homogeneous in the immutable contracts;
                # charge each slot independently even when values are shared.
                total+=len(item)*max(sys.getsizeof(v) for v in item)
            else:pending.extend(item)
        elif isinstance(item,(set,frozenset)):pending.extend(item)
        elif is_dataclass(item) and not isinstance(item,type):
            pending.extend(getattr(item,f.name) for f in fields(item))
            if hasattr(item,'__dict__'):total+=sys.getsizeof(item.__dict__)
    return total


def _paths_bytes(paths):
    return sys.getsizeof(paths)+sum(sys.getsizeof(path)+len(path)*_POINT_BYTES for path in paths)


def _source_bytes(source,cancelled):
    """Known immutable model owners: count coordinates/groups by their lengths."""
    total=sys.getsizeof(source)
    for index,item in enumerate(source):
        if index%256==0 and cancelled is not None and cancelled():raise InterruptedError()
        kind=type(item).__name__
        if kind=='MapRoad':
            total+=(1536+4*(len(item.name)+len(item.asset_id))+_paths_bytes(item.paths)
                    +256*len(item.lanes)+64*(len(item.bridge_masks)+len(item.tunnel_masks)))
        elif kind=='MapBuilding':
            total+=(1024+4*(len(item.name)+len(item.asset_id)+len(item.category))
                    +_POINT_BYTES+sys.getsizeof(item.polygon)+len(item.polygon)*_POINT_BYTES
                    +320*sum(len(getattr(item,name)) for name in ('residents','workers','combined_groups',
                                                               'function_capacities','function_population'))
                    +64*(len(item.service_lines.route_ids)+len(item.service_lines.unresolved_refs))
                    +4*len(item.service_lines.diagnostic or ''))
        elif kind=='MapStop':
            total+=512+4*len(item.name)
        elif kind=='MapJunction':
            total+=768+64*len(item.road_ids)+4*len(item.diagnostic or '')
            for connection in item.connections:
                total+=768+_paths_bytes(connection.paths)
        elif kind=='MapRoute':
            total+=(2048+4*sum(len(str(getattr(item,name) or '')) for name in
                             ('name','company_id','company_name','mode','diagnostic','passenger_date',
                              'passenger_diagnostic','depot_name'))
                    +_paths_bytes(item.paths)+_paths_bytes(item.depot_paths)
                    +sum(64+_paths_bytes(paths) for paths in (*item.leg_paths,*item.depot_leg_paths))
                    +128*len(item.direction.paired_stations)
                    +64*sum(len(getattr(item,name)) for name in ('stop_ids','leg_map_length_units',
                              'depot_map_length_units','stop_arrival_offsets_ticks','leg_duration_ticks')))
            for timetable in item.service.timetables or ():
                total+=256+64*len(timetable.departure_ticks or ())
        else:
            total+=_estimated_bytes(item,cancelled)
    return total


def _array_bytes(arrays):
    seen=set();total=0
    for array in arrays:
        while array is not None and id(array) not in seen:
            seen.add(id(array));total+=sys.getsizeof(array)
            if isinstance(array,np.ndarray):array=array.base
            elif isinstance(array,memoryview):array=array.obj
            else:break
    return total


def _scene_bytes(scene,cancelled):
    if not hasattr(scene,'vertices'):
        return _estimated_bytes(scene,cancelled)
    # A command has a fixed dataclass header, scalar fields, bounds and an
    # optional tile. Members hold (order, bounds, span, material). These upper
    # allowances deliberately overcount shared scalar/bounds Python objects.
    total=(sys.getsizeof(scene)+sys.getsizeof(scene.commands)
           +_array_bytes((scene.vertices,scene.materials,scene.indices)))
    for start in range(0,len(scene.commands),1024):
        if cancelled is not None and cancelled():raise InterruptedError()
        total+=sum(1024+384*len(command.connection_members) for command in scene.commands[start:start+1024])
    return total


def _prepared_bytes(prepared,cancelled):
    total=1024;arrays=[]
    for batches in (prepared.roads,prepared.buildings):
        total+=sys.getsizeof(batches)
        for index,batch in enumerate(batches):
            if index%256==0 and cancelled is not None and cancelled():raise InterruptedError()
            total+=1024+batch.path.capacity()*32
            total+=sum(384+path.capacity()*32 for _,path in batch.members)
    total+=sys.getsizeof(prepared.connections)
    for index,connection in enumerate(prepared.connections):
        if index%256==0 and cancelled is not None and cancelled():raise InterruptedError()
        total+=512
        for template in connection.templates:
            total+=1024+template.polygon.capacity()*16
            # NumPy views share the bulk owner's buffers. Only the root owner
            # is charged here; each view header is in the template allowance.
            arrays.extend(array.base if array.base is not None else array
                          for array in (template.screen_base,template.normals,template.fractions))
    total+=_array_bytes(arrays)
    for tiles in (prepared.road_tiles,prepared.building_tiles):
        total+=256*len(tiles)+64*sum(len(indices) for indices in tiles.values())
    total+=256*len(prepared.connection_tiles)
    total+=128*sum(len(indices) for _,indices in prepared.connection_tiles.values())
    return total


def retained_resources(value,cancelled=None,known=None):
    """Small owner table for a scene or (scene, prepared, source containers)."""
    known={} if known is None else known
    if hasattr(value,'base') and hasattr(value,'routes'):
        scene=value;prepared=None;sources=()
    else:
        scene,prepared,sources=value
    owners=[(scene.base,_scene_bytes),(scene.routes,_scene_bytes)]
    if prepared is not None:owners.append((prepared,_prepared_bytes))
    owners.extend((source,_source_bytes) for source in sources)
    result={}
    for owner,estimate in owners:
        identity=id(owner)
        if identity in result:continue
        previous=known.get(identity)
        size=(previous[1] if previous is not None and previous[0] is owner
              else estimate(owner,cancelled))
        result[identity]=(owner,size)
    return result


class SceneVariantCache:
    """LRU with conservative owner bytes plus key/bookkeeping allowance."""
    def __init__(self,byte_budget=1536*1024*1024,max_entries=6):
        self.byte_budget=max(0,int(byte_budget));self.max_entries=max(0,int(max_entries))
        self._entries=OrderedDict();self._resources={};self.retained_bytes=0

    def __len__(self):return len(self._entries)

    def resource_sizes(self):
        return {key:(owner,size) for key,(owner,size,count) in self._resources.items()}

    def get(self,key):
        record=self._entries.get(key)
        if record is None:return None
        self._entries.move_to_end(key)
        return record[0]

    def _remove(self,key):
        _,resources,overhead=self._entries.pop(key);self.retained_bytes-=overhead
        for identity in resources:
            owner,size,count=self._resources[identity]
            if count>1:self._resources[identity]=(owner,size,count-1)
            else:
                del self._resources[identity];self.retained_bytes-=size

    def put(self,key,value,resources=None):
        resources=retained_resources(value,known=self.resource_sizes()) if resources is None else resources
        # Includes keys, per-entry owner table, global owner records, LRU nodes,
        # wrapper tuples and dictionaries. Owner table cardinality is small.
        overhead=_estimated_bytes(key)+4096+len(resources)*512
        if key in self._entries:self._remove(key)
        if not self.max_entries or sum(size for _,size in resources.values())+overhead>self.byte_budget:return
        self._entries[key]=(value,resources,overhead);self.retained_bytes+=overhead
        for identity,(owner,size) in resources.items():
            count=self._resources.get(identity,(None,0,0))[2]
            self._resources[identity]=(owner,size,count+1)
            if not count:self.retained_bytes+=size
        while len(self._entries)>self.max_entries or self.retained_bytes>self.byte_budget:
            self._remove(next(iter(self._entries)))

    def clear(self):
        self._entries.clear();self._resources.clear();self.retained_bytes=0
