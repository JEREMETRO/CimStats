"""Prepare bounded index ranges off the GUI thread; never alter geometry."""
from dataclasses import dataclass, replace
import numpy as np


def _checkpoint(cancelled):
    if cancelled is not None and (cancelled() if callable(cancelled) else cancelled.is_set()):
        raise InterruptedError()


@dataclass(frozen=True, slots=True, eq=False)
class BoundsTree:
    """CPU-only immutable tree, prepared before a scene reaches its renderer."""
    boxes: np.ndarray
    nodes: tuple
    all_indices: np.ndarray
    estimated_bytes: int

    @classmethod
    def build(cls, boxes, cancelled=None):
        _checkpoint(cancelled)
        # Own the bounds: legacy callers can keep mutable input arrays without
        # changing the shared scene metadata underneath another GL context.
        values=np.asarray(boxes,dtype=float).reshape(-1,4)
        boxes=np.empty(values.shape,dtype=float);boxes[:]=values
        boxes.setflags(write=False)
        all_indices=np.arange(len(boxes),dtype=np.int64)
        all_indices.setflags(write=False)
        nodes=[]

        def build(ids):
            _checkpoint(cancelled)
            selected=boxes[ids]
            bounds=(*np.min(selected[:,:2],axis=0),*np.max(selected[:,2:],axis=0))
            index=len(nodes);nodes.append(None)
            if len(ids)<=128:
                nodes[index]=(bounds,ids,None)
            else:
                centers=selected[:,:2]+(selected[:,2:]-selected[:,:2])*.5
                axis=int(np.argmax(np.ptp(centers,axis=0)))
                ids=ids[np.argsort(centers[:,axis],kind='stable')]
                ids.setflags(write=False)
                _checkpoint(cancelled)
                middle=len(ids)//2
                left=build(ids[:middle]);right=build(ids[middle:])
                nodes[index]=(bounds,left,right)
            return index

        if len(boxes):build(all_indices)
        _checkpoint(cancelled)
        # Leaf slices can keep their sorting parent's full owner alive. Twice
        # the leaf payload bounds that storage even for uneven subdivisions;
        # the node allowance includes tuples, scalar bounds and array headers.
        estimated=4096+boxes.nbytes+all_indices.nbytes*3+len(nodes)*1024
        return cls(boxes,tuple(nodes),all_indices,estimated)


@dataclass(frozen=True, slots=True, eq=False)
class SceneVisibility:
    command_tree: BoundsTree
    member_tree: BoundsTree

    @property
    def estimated_bytes(self):
        return 256+self.command_tree.estimated_bytes+self.member_tree.estimated_bytes

    @classmethod
    def build(cls, commands, cancelled=None):
        command_boxes=[];member_boxes=[]
        for index,command in enumerate(commands):
            if index%256==0:_checkpoint(cancelled)
            command_boxes.append(command.bounds)
            if command.connection_rank>=0:
                for offset,member in enumerate(command.connection_members):
                    if offset%256==0:_checkpoint(cancelled)
                    member_boxes.append(member[1])
        return cls(BoundsTree.build(command_boxes,cancelled),
                   BoundsTree.build(member_boxes,cancelled))


class BoundsCandidates:
    """Private view neighbourhood around a shareable immutable AABB tree.

    Only membership is cached: callers still apply exact bounds, LOD and draw
    order on every frame. Storage is linear in the source boxes; distant or
    city-wide views traverse existing nodes rather than empty spatial cells.
    """
    def __init__(self, boxes):
        self.tree=boxes if isinstance(boxes,BoundsTree) else BoundsTree.build(boxes)
        self.boxes=self.tree.boxes
        self.nodes=self.tree.nodes
        self._region=None
        self._candidates=np.empty(0,dtype=np.int64)
        self._all=self.tree.all_indices

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
