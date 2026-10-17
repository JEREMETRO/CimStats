"""Prepare bounded index ranges off the GUI thread; never alter geometry."""
from dataclasses import replace
import numpy as np


def cull_commands(scene,chunk_size=1536):
    """Preserve primitive order and measured-width coverage at every scale.

    A city-wide merged route otherwise runs every vertex at every zoom, even
    when almost the whole route is offscreen. Symbolic stroke coverage is
    included in the renderer's screen margin. Winding contours stay whole.
    """
    if chunk_size<3 or chunk_size%3:raise ValueError('Triangle chunk size must be a positive multiple of three')
    materials=scene.materials
    physical=np.where(materials[:,3]<5.5,np.maximum(materials[:,2],0.)*.5,0.)
    result=[];bounds_cache={}
    for c in scene.commands:
        if c.mode!='triangles' or c.connection_rank>=0 or c.count<=chunk_size:
            result.append(c);continue
        key=c.start,c.count
        chunks=bounds_cache.get(key)
        if chunks is None:
            ids=scene.indices[c.start:c.start+c.count]
            points=scene.vertices[ids,:2]
            local=np.arange(0,c.count,chunk_size)
            lower=np.minimum.reduceat(points,local,axis=0).astype(float)
            upper=np.maximum.reduceat(points,local,axis=0).astype(float)
            material_ids=scene.vertices[ids,8].astype(np.int64)
            radius=np.maximum.reduceat(physical[material_ids],local)
            lower-=radius[:,None];upper+=radius[:,None]
            chunks=tuple((int(start),(*lo,*hi)) for start,lo,hi in zip(local,lower,upper))
            bounds_cache[key]=chunks
        result.extend(replace(c,start=c.start+start,count=min(chunk_size,c.count-start),bounds=bounds)
                      for start,bounds in chunks)
    return tuple(result)
