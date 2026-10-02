from stats_identity import save_fingerprint


def test_fingerprint_follows_content_not_filename(tmp_path):
    first, second = tmp_path / 'first.save', tmp_path / '另一个.save'
    first.write_bytes(b'save one')
    second.write_bytes(b'save one')
    assert save_fingerprint(first) == save_fingerprint(second)
    second.write_bytes(b'save two')
    assert save_fingerprint(first) != save_fingerprint(second)


def test_fingerprint_is_repeatable_for_large_file(tmp_path):
    path = tmp_path / 'long.save'
    path.write_bytes(b'x' * (2 * 1024 * 1024 + 13))
    assert len(save_fingerprint(path)) == 64
    assert save_fingerprint(path) == save_fingerprint(path)
