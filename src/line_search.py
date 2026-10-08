"""Shared searches over a route's visible identity, never its numeric facts."""
from unicodedata import normalize

from display_rules import display_mode


def _text(value):
    return normalize('NFKC', str(value)).strip().casefold() if value is not None else ''


def line_matches_search(query, record, *, aliases=()):
    """Accept session lines and map catalog rows without searching raw IDs.

    Numeric searches only inspect line names/codes and line numbers. Company
    digits used to disambiguate duplicate names must not produce false routes.
    """
    needle = _text(query)
    if not needle:
        return True
    name = record.get('search_name') or record.get('name') or record.get('线路名称')
    number = record.get('number', record.get('线路号'))
    values = [name, number, *aliases]
    if not needle.isdecimal():
        mode = record.get('mode', record.get('运输制式'))
        values.extend((record.get('display_label'), record.get('label'),
                       mode, display_mode(mode),
                       record.get('company_name', record.get('公司名称'))))
    return any(needle in _text(value) for value in values if value is not None)
