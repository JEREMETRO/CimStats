"""Direction reuse preserves the original terminal and confidence semantics."""
import pytest
import map_analysis


@pytest.mark.parametrize('height', [0., 12.])
def test_cached_direction_scores_match_per_terminal_computation(monkeypatch, height):
    points=((0.,0.,0.),(100.,0.,0.),(200.,0.,0.),(300.,0.,0.),
            (200.,height,2.),(100.,height,2.),(0.,height,2.))
    legs=tuple(((a,((a[0]+b[0])/2,(a[1]+b[1])/2,(a[2]+b[2])/2),b),)
               for a,b in zip(points,points[1:]))
    names=('', '', '', '东北转车站E2', '', '', '')
    cached=map_analysis.infer_direction(points,legs,names)
    monkeypatch.setattr(map_analysis,'_cached_geometry_similarity',lambda *args: None)
    original=map_analysis.infer_direction(points,legs,names)
    assert cached==original


def test_cached_direction_checks_cancellation_during_similarity():
    points=tuple((float(i*100),0.,0.) for i in range(4))
    legs=tuple(((a,b),) for a,b in zip(points,points[1:]))
    class Cancelled(Exception):
        pass
    calls=0
    def cancel():
        nonlocal calls
        calls+=1
        if calls==1:
            raise Cancelled()
    with pytest.raises(Cancelled):
        map_analysis.infer_direction(points,legs,cancelled=cancel)
