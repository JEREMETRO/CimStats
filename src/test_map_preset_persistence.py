"""Navigation saves the final camera without serializing on every input event."""
import json
import pytest
from PySide6.QtCore import QSettings
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication


class Settings:
    def __init__(self):
        self.values = {}
        self.writes = []

    def value(self, key, default=None):
        return self.values.get(key, default)

    def contains(self, key):
        return key in self.values

    def setValue(self, key, value):
        self.values[key] = value
        self.writes.append(key)


def test_deferred_camera_is_current_and_flushes_only_once():
    from map_presets import PresetStore
    settings = Settings()
    store = PresetStore(settings, {})
    store.load('A')
    settings.writes.clear()
    for x in range(120):
        store.update('network', view=[x, 2, .5], persist=False)
    assert store.state('network')['view'] == [119, 2, .5]
    assert settings.writes == []
    store.flush()
    store.flush()
    assert settings.writes == ['map/presets/A']
    assert json.loads(settings.values['map/presets/A'])['network']['view'] == [119, 2, .5]


def test_save_switch_flushes_old_identity_and_query_stays_immediate():
    from map_presets import PresetStore
    settings = Settings()
    store = PresetStore(settings, {})
    store.load('A')
    store.update('network', view=[1, 2, .5], persist=False)
    store.load('B')
    store.update('single', view=[3, 4, .8], persist=False)
    store.update('single', query={'route_id': 38})
    assert json.loads(settings.values['map/presets/A'])['network']['view'] == [1, 2, .5]
    saved = json.loads(settings.values['map/presets/B'])
    assert saved['network']['view'] is None
    assert saved['single']['view'] == [3, 4, .8]
    assert saved['single']['query']['route_id'] == 38


@pytest.fixture
def page(tmp_path):
    from map_page import MapPage
    app = QApplication.instance() or QApplication([])
    settings = QSettings(str(tmp_path/'view.ini'), QSettings.Format.IniFormat)
    widget = MapPage(settings)
    widget.set_session({'save_key': 'A'})
    # The camera persistence contract does not require starting a geometry worker.
    widget.query = object()
    yield widget, settings, app
    widget.query = None
    widget.close()


def test_navigation_is_debounced_and_timer_writes_latest_view(page):
    widget, settings, app = page
    for x in range(80):
        widget._save_view(x, 2, .5)
    assert widget.presets.state('network')['view'] == [79, 2, .5]
    assert json.loads(settings.value('map/presets/A'))['network']['view'] is None
    QTest.qWait(400)
    assert json.loads(settings.value('map/presets/A'))['network']['view'] == [79, 2, .5]
    assert not widget._view_save_timer.isActive()


@pytest.mark.parametrize('boundary', ['close', 'workers', 'save'])
def test_pending_camera_flushed_at_lifecycle_boundary(page, boundary):
    widget, settings, app = page
    widget._save_view(12, 34, .7)
    if boundary == 'close':
        widget.close()
    elif boundary == 'workers':
        widget.stop_workers()
    else:
        widget.set_session({'save_key': 'B'})
    assert json.loads(settings.value('map/presets/A'))['network']['view'] == [12, 34, .7]
    assert not widget._view_save_timer.isActive()
    if boundary == 'save':
        QTest.qWait(350)
        assert json.loads(settings.value('map/presets/B'))['network']['view'] is None


def test_hidden_prepared_signal_cannot_clear_revealed_loading(page, monkeypatch):
    widget, settings, app = page
    monkeypatch.setattr(widget, 'isVisible', lambda: True)
    monkeypatch.setattr(widget.canvas, 'can_export', lambda: False)
    monkeypatch.setattr(widget.canvas, 'is_prepared', lambda: True, raising=False)
    widget._awaiting_frame = True
    widget._frame_ready()
    assert widget._awaiting_frame
    monkeypatch.setattr(widget.canvas, 'can_export', lambda: True)
    widget._frame_ready()
    assert not widget._awaiting_frame
