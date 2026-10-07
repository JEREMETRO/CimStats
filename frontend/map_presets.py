"""Per-save preset state with one-way migration of the old network settings."""
from __future__ import annotations
from copy import deepcopy
import json
from math import isfinite

PRESETS = ('single', 'network', 'planning')


def _read(settings, key, default):
    try:
        value = json.loads(str(settings.value(key, 'null')))
        return value if isinstance(value, type(default)) else deepcopy(default)
    except (ValueError, TypeError):
        return deepcopy(default)


def _json(value):
    return json.dumps(value, ensure_ascii=False,
                      default=lambda item: sorted(item, key=str) if isinstance(item, set) else str(item))


def valid_view(view):
    """Malformed settings must never put NaNs or a negative zoom into the canvas."""
    if not isinstance(view, (tuple, list)) or len(view) != 3:
        return None
    try:
        x, z, zoom = (float(value) for value in view)
    except (ValueError, TypeError):
        return None
    return [x, z, zoom] if all(isfinite(v) for v in (x, z, zoom)) and .0001 <= zoom <= 100 else None


class PresetStore:
    def __init__(self, settings, network_defaults):
        self.settings = settings
        self.defaults = {
            'network': deepcopy(network_defaults),
            'single': {'route_id': None, 'direction': 'up', 'deadhead': False},
            'planning': {'selected_ids': [], 'building_view': 'combined',
                         'building_classes': None, 'building_emphasis': True},
        }
        selected = str(settings.value('map/preset', 'network'))
        self.current = selected if selected in PRESETS else 'network'
        self.save_key = ''
        self._states = {}
        self.load('')

    def load(self, save_key):
        self.save_key = str(save_key or '')
        saved = _read(self.settings, 'map/presets/' + self.save_key, {}) if self.save_key else {}
        legacy = _read(self.settings, 'map/query/' + self.save_key, {}) if self.save_key else {}
        self._states = {}
        for preset in PRESETS:
            record = saved.get(preset, {})
            if not isinstance(record, dict):
                record = {}
            query = deepcopy(self.defaults[preset])
            source = record.get('query', legacy if preset == 'network' else {})
            if isinstance(source, dict):
                query.update(source)
            layout = _read(self.settings, 'map/presets/layout/' + preset, {})
            if preset == 'network' and not self.settings.contains('map/presets/layout/network'):
                layout = _read(self.settings, 'map/layout', {})
            self._states[preset] = {'query': query, 'view': valid_view(record.get('view')), 'layout': layout}
        self._persist()

    def state(self, preset):
        return deepcopy(self._states[preset])

    def update(self, preset, *, query=None, view=None, layout=None):
        record = self._states[preset]
        if query is not None:
            record['query'].update(deepcopy(query))
        if view is not None:
            record['view'] = valid_view(view)
        if layout is not None:
            record['layout'] = deepcopy(layout)
            self.settings.setValue('map/presets/layout/' + preset, _json(layout))
        self._persist()

    def activate(self, preset):
        if preset not in PRESETS:
            raise ValueError('Unknown map preset: ' + str(preset))
        self.current = preset
        self.settings.setValue('map/preset', preset)

    def _persist(self):
        if self.save_key:
            self.settings.setValue('map/presets/' + self.save_key, _json({
                key: {field: value for field, value in record.items() if field != 'layout'}
                for key, record in self._states.items()}))
