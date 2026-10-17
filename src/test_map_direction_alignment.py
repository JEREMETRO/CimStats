from pathlib import Path
import numpy as np
import pytest
import map_analysis


def test_split_alignment_scores_match_independent_terminals():
    # Includes zeros, ambiguous ties and unequal sampled leg lengths.
    rng = np.random.default_rng(20261018)
    for count in (2, 7, 19):
        similarity = rng.integers(0, 7, (count, count)).astype(float)/3
        cuts = list(range(1, count))
        expected = {cut: map_analysis._align(similarity[:cut, cut:][:, ::-1])[0] for cut in cuts}
        assert map_analysis._split_alignment_scores(similarity, cuts) == expected


def test_split_alignment_checks_cancellation_while_advancing():
    class Cancelled(Exception):
        pass
    calls = []
    def cancel():
        calls.append(True)
        if len(calls) == 3:
            raise Cancelled()
    with pytest.raises(Cancelled):
        map_analysis._split_alignment_scores(np.ones((20, 20)), [5, 10, 15], cancel)
    assert len(calls) == 3


def test_proximity_matches_original_including_height_and_distance_boundaries():
    rng = np.random.default_rng(22)
    a = rng.normal(size=(40, 3))*300
    b = np.concatenate((a, a+[250., 0., 0.], a+[0., 6., 0.], a+[0., 6.001, 0.]))
    delta = a[:, None, :]-b[None, :, :]
    distance = np.linalg.norm(delta, axis=2)
    expected = np.where((distance <= 250)&(np.abs(delta[:, :, 1]) <= 6), np.exp(-(distance/120)**2), 0.)
    np.testing.assert_array_equal(map_analysis._proximity(a, b), expected)


def test_native_distribution_reuses_open_source_metadata(monkeypatch):
    import dnfile
    import map_geometry
    source = Path(map_geometry.__file__).resolve().parents[1]/'game_runtime/Managed/Assembly-CSharp.dll'
    expected = map_geometry.native_distribution_tables(source)
    metadata = dnfile.dnPE(str(source))
    try:
        def unexpected_parse(*args, **kwargs):
            raise AssertionError('Source metadata was already parsed for this extraction')
        monkeypatch.setattr(dnfile, 'dnPE', unexpected_parse)
        assert map_geometry.native_distribution_tables(source, source_metadata=metadata) == expected
        # The caller still owns the mapping for probe/other native readers.
        assert metadata.get_data(metadata.net.mdtables.MethodDef[0].Rva, 1)
    finally:
        metadata.close()


def test_route_geometry_memo_reuses_curves_and_lanes_without_changing_input(monkeypatch):
    from copy import deepcopy
    import map_geometry as g
    road = dict(id=1, start=2, end=3,
        curves=[[(0., 0., 0.), (30., 0., 0.), (70., 0., 0.), (100., 0., 0.)]],
        lanes=[dict(index=0, offset=2., type_mask=0x1000100)])
    before = deepcopy(road)
    refs = [dict(id=1, mask=1, reverse=False)]
    expected = g.route_leg(refs, {1: road})
    expected_lane = g.route_leg(refs, {1: road}, lane_selection=((0,), ()))
    calls = []
    sample = g.sample_curve
    def sampled(controls):
        calls.append(True)
        return sample(controls)
    monkeypatch.setattr(g, 'sample_curve', sampled)
    cache = {}
    for _ in range(5):
        assert g.route_leg(refs, {1: road}, geometry_cache=cache) == expected
        assert g.route_leg(refs, {1: road}, lane_selection=((0,), ()), geometry_cache=cache) == expected_lane
    assert len(calls) <= 2
    assert road == before
    # A new extraction does not reuse old input's geometry at the same ID.
    road['curves'][0][-1] = (110., 0., 0.)
    assert g.route_leg(refs, {1: road}, geometry_cache={}) != expected
