"""Direction from operational paths and reverse stop order, in game metres.

No UI, Unity callbacks, depot legs or asset guesses enter this analysis.
"""
from __future__ import annotations
import math
import numpy as np
from map_model import Path, RouteDirection

SPECIAL_TERMINAL_WORDS = ('转车站', '枢纽站', '路口站', '车厂站', '火车站', '地铁站')


def choose_turnaround_candidate(candidates, cumulative, midpoint, names=None):
    pool = candidates
    if len(pool) > 1 and names is not None:
        named = [c for c in pool if any(w in str(names[c['index']] or '') for w in SPECIAL_TERMINAL_WORDS)]
        if named:
            pool = named
    return min(pool, key=lambda c: (abs(cumulative[c['index']]-midpoint), -c['score'], c['index']))


def _align(sim, trace=False):
    a,b = sim.shape
    table = np.zeros((a+1,b+1))
    for i in range(a):
        table[i+1,1:] = np.maximum.accumulate(np.maximum(table[i,1:],table[i,:-1]+sim[i]))
    pairs=[]
    if trace:
        i,j=a,b
        while i and j:
            if sim[i-1,j-1] > .05 and abs(table[i,j]-table[i-1,j-1]-sim[i-1,j-1]) < 1e-7:
                pairs.append((i-1,j-1)); i-=1; j-=1
            elif table[i-1,j] >= table[i,j-1]:
                i-=1
            else:
                j-=1
        pairs.reverse()
    return float(table[-1,-1]),pairs


def _proximity(a,b):
    delta = a[:,None,:]-b[None,:,:]
    distance = np.linalg.norm(delta,axis=2)
    # Separate a surface road from an overpass/tunnel occupying the same x/z.
    return np.where((distance<=250)&(np.abs(delta[:,:,1])<=6),np.exp(-(distance/120)**2),0.)


def _sample(paths):
    result=[]
    for path in paths:
        for a,b in zip(path,path[1:]):
            a,b=np.asarray(a,float),np.asarray(b,float)
            delta=b-a; length=float(np.linalg.norm(delta))
            if length<.01:
                continue
            count=max(1,math.ceil(length/80))
            for j in range(count):
                result.append([*(a+delta*((j+.5)/count)),*(delta/length),length/count])
    return np.asarray(result,float).reshape((-1,7))


def _cached_geometry_similarity(samples, cancelled=None):
    """Compare each ordered operating sample pair once for all terminals.

    A terminal only changes where the same sequence is split into outbound
    and reversed inbound paths. The block size bounds temporary allocations;
    unusually long paths retain the original per-terminal computation.
    """
    all_samples=np.concatenate(samples)
    count=len(all_samples)
    if count>4000:
        return None
    similarity=np.empty((count,count),dtype=float)
    position=all_samples[:,:3]
    direction=all_samples[:,3:6]
    weight=all_samples[:,6]
    for first in range(0,count,256):
        if cancelled: cancelled()
        last=min(count,first+256)
        similarity[first:last]=_proximity(position[first:last],position)
        cosine=direction[first:last] @ (-direction.T)
        similarity[first:last]*=np.where(cosine>=.6,np.clip(cosine,0,1),0)
        similarity[first:last]*=np.minimum(weight[first:last,None],weight[None,:])
    return similarity


def infer_direction(points: Path, legs: tuple[tuple[Path,...],...], names=None, cancelled=None) -> RouteDirection:
    """Return zero-based stop pairs; unknown when any operational leg is absent.

    A name can only break a score plateau strictly between the last strong
    reverse pair. An open non-returning path is one_way, never circular.
    """
    n=len(points)
    if n<2 or len(legs)!=n-1 or any(not leg or not any(len(p)>1 for p in leg) for leg in legs):
        return RouteDirection()
    points=np.asarray(points,float)
    samples=[_sample(leg) for leg in legs]
    lengths=[float(s[:,-1].sum()) for s in samples]
    if any(length<=1e-8 for length in lengths):
        return RouteDirection()
    cumulative=np.r_[0,np.cumsum(lengths)]
    total=float(cumulative[-1])
    similarity=_cached_geometry_similarity(samples,cancelled) if n>2 else None
    cut=0
    candidates=[]
    for k in range(1,n-1):
        if cancelled:
            cancelled()
        cut+=len(samples[k-1])
        geometry=0.
        if similarity is not None:
            sim=similarity[:cut,cut:][:,::-1]
            geometry=2*_align(sim)[0]/max(total,1e-8)
        else:
            down=np.concatenate(samples[:k]); up=np.concatenate(samples[k:])[::-1].copy()
            up[:,3:6]*=-1
            if len(down) and len(up):
                sim=_proximity(down[:,:3],up[:,:3])
                cosine=down[:,3:6] @ up[:,3:6].T
                sim*=np.where(cosine>=.6,np.clip(cosine,0,1),0)
                sim*=np.minimum(down[:,None,6],up[None,:,6])
                geometry=2*_align(sim)[0]/max(total,1e-8)
        stations,pairs=_align(_proximity(points[:k],points[k+1:][::-1]),True)
        stations=2*stations/max(n-1,1)
        candidates.append(dict(index=k,score=.65*geometry+.35*stations,geometry=geometry,
                               stations=stations,pairs=[(i,n-1-j) for i,j in pairs]))
    start=legs[0][0][0]; end=legs[-1][-1][-1]
    closed=np.linalg.norm(np.asarray(start)-end)<=35 and abs(start[1]-end[1])<=6
    if not candidates:
        return RouteDirection(kind='circular' if closed else 'one_way')
    best=max(candidates,key=lambda c:c['score'])
    baseline=best; rule='geometry'
    strong=[(i,j) for i,j in best['pairs'] if np.linalg.norm(points[i]-points[j])<=120 and abs(points[i,1]-points[j,1])<=6]
    if strong:
        left,right=max(strong,key=lambda ij:ij[0])
        midpoint=(cumulative[left]+cumulative[right])/2
        plateau=[c for c in candidates if c['score']>=best['score']-.012 and left<c['index']<right]
        if plateau:
            baseline=choose_turnaround_candidate(plateau,cumulative,midpoint)
            best=choose_turnaround_candidate(plateau,cumulative,midpoint,names)
            if best['index']!=baseline['index']:
                rule='special_name_inside_ambiguous_turnaround'
    roundtrip=baseline['score']>=.55 and (baseline['geometry']>=.45 or baseline['stations']>=.75)
    if roundtrip:
        return RouteDirection('roundtrip',best['index'],tuple(best['pairs']),best['score'],best['geometry'],best['stations'],rule)
    # Closure refers to serialized operating paths, excluding depot travel.
    return RouteDirection('circular' if closed else 'one_way',score=baseline['score'],
                          geometry_score=baseline['geometry'],station_score=baseline['stations'])
