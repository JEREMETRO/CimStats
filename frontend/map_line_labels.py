"""Visible map line names resolved against the complete save's catalog."""
from collections.abc import Mapping
from display_rules import display_mode, format_line_name
from report_model import display_company


def _field(record, name, default=None):
    return record.get(name, default) if isinstance(record, Mapping) else getattr(record, name, default)


def resolve_line_labels(routes):
    """Return stable-ID labels; callers retain this full-save mapping when filtering.

    Prefix the company only for equal mode/name combinations across owners.
    Existing mode-qualified names keep one mode prefix. IDs are never visible.
    """
    normalized = []
    owners = {}
    for route in routes or ():
        identity = _field(route, 'id')
        if identity is None:
            continue
        mode = display_mode(_field(route, 'mode', ''))
        name = str(_field(route, 'name', '') or '').strip()
        number = _field(route, 'number')
        if number is not None and not (mode and name.startswith(mode)):
            name = format_line_name(number, name)
        base = name if mode and name.startswith(mode) else mode + name
        company = display_company(_field(route, 'company_name', '') or '')
        owner = _field(route, 'company_id')
        owner = ('id', str(owner)) if owner is not None else ('name', company)
        owners.setdefault(base, set()).add(owner)
        normalized.append((identity, base, company))
    return {identity: company + base if len(owners[base]) > 1 else base
            for identity, base, company in normalized}
