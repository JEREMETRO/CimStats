"""Prepare bounded index ranges off the GUI thread; never alter geometry."""
from dataclasses import replace
import numpy as np


class BoundsCandidates:
    """Immutable AABB tree and one bounded, conservative view neighbourhood.

    Only membership is cached: callers still apply exact bounds, LOD and draw
    order on every frame. Storage is linear in the source boxes; distant or
    city-wide views traverse existing nodes rather than empty spatial cells.
    """
    def __init__(self, boxes):
        self.boxes=np.asarray(boxes,dtype=float).reshape(-1,4)
        self.nodes=[]
        self._region=None
        self._candidates=np.empty(0,dtype=np.int64)
        self._all=np.arange(len(self.boxes),dtype=np.int64)
        if len(self.boxes):self._build(self._all)

    def _build(self, ids):
        boxes=self.boxes[ids]
        bounds=(*np.min(boxes[:,:2],axis=0),*np.max(boxes[:,2:],axis=0))
        index=len(self.nodes);self.nodes.append(None)
        if len(ids)<=128:
            self.nodes[index]=(bounds,ids,None)
        else:
            centers=boxes[:,:2]+(boxes[:,2:]-boxes[:,:2])*.5
            axis=int(np.argmax(np.ptp(centers,axis=0)))
            ids=ids[np.argsort(centers[:,axis],kind='stable')]
            middle=len(ids)//2
            left=self._build(ids[:middle]);right=self._build(ids[middle:])
            self.nodes[index]=(bounds,left,right)
        return index

    def query(self, bounds):
        x0,y0,x1,y1=bounds
        width=max(x1-x0,1e-9);height=max(y1-y0,1e-9)
        region=self._region
        if (region is not None and region[0]<=x0 and region[1]<=y0 and
                region[2]>=x1 and region[3]>=y1 and
                region[2]-region[0]<=width*4 and region[3]-region[1]<=height*4):
            return self._candidates
        region=(x0-width*.25,y0-height*.25,x1+width*.25,y1+height*.25)
        if self.nodes:
            box=self.nodes[0][0]
            # Broad views are cheaper as contiguous array scans. A superset
            # remains conservative, including elongated road/route bounds.
            overlap_width=max(0.,min(box[2],region[2])-max(box[0],region[0]))
            overlap_height=max(0.,min(box[3],region[3])-max(box[1],region[1]))
            area=(box[2]-box[0])*(box[3]-box[1])
            if area>0 and overlap_width*overlap_height>=area*.35:
                self._region=region;self._candidates=self._all
                return self._candidates
        found=[];pending=[0] if self.nodes else []
        while pending:
            box,left,right=self.nodes[pending.pop()]
            if box[0]>region[2] or box[2]<region[0] or box[1]>region[3] or box[3]<region[1]:
                continue
            if right is None:found.append(left)
            else:pending.extend((left,right))
        ids=np.concatenate(found) if found else np.empty(0,dtype=np.int64)
        boxes=self.boxes[ids]
        keep=(boxes[:,0]<=region[2])&(boxes[:,2]>=region[0])
        keep&=(boxes[:,1]<=region[3])&(boxes[:,3]>=region[1])
        self._candidates=ids[keep]
        self._region=region
        return self._candidates


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
