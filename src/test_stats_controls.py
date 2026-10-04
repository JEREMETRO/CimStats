"""Shared Fluent segmented control for page, chart, and summary switches."""
import os
import sys
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'frontend'))

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication, QButtonGroup
from qfluentwidgets import FluentIcon, TogglePushButton

from stats_controls import FluentSegmentedControl
import stats_tokens as tokens


def app():
    return QApplication.instance() or QApplication([])


def test_segmented_control_uses_exclusive_fluent_buttons_and_emits_once(monkeypatch):
    monkeypatch.setattr('stats_motion.animations_enabled', lambda: True)
    app()
    control = FluentSegmentedControl()
    spy = QSignalSpy(control.currentKeyChanged)
    control.addItem('default', '默认模式', FluentIcon.PIE_SINGLE)
    control.addItem('companies', '多公司对比', FluentIcon.PEOPLE)
    control.addItem('period', '同期对比', FluentIcon.CALENDAR)
    buttons = control.findChildren(TogglePushButton)
    assert len(buttons) == 3
    assert isinstance(control.findChild(QButtonGroup), QButtonGroup)
    assert control.currentKey() == 'default' and buttons[0].isChecked()
    assert control.width() < 500  # The group does not stretch into three oversized pills.
    assert all(button.width() >= button.minimumWidth() for button in buttons)
    assert spy.count() == 0
    control.show()
    app().processEvents()
    buttons[1].click()
    assert control.currentKey() == 'companies'
    assert [button.isChecked() for button in buttons] == [False, True, False]
    assert spy.count() == 1 and spy.at(0)[0] == 'companies'
    assert control._animation.duration() == 167
    control.setCurrentKey('companies')
    assert spy.count() == 1
    control.setCurrentKey('period')
    assert spy.count() == 2 and spy.at(1)[0] == 'period'
    control.deleteLater()


def test_disabled_segment_cannot_be_clicked_and_programmatic_selection_respects_signals():
    app()
    control = FluentSegmentedControl()
    control.addItem('overall', '总体')
    control.addItem('companies', '多公司')
    buttons = control.findChildren(TogglePushButton)
    spy = QSignalSpy(control.currentKeyChanged)
    control.setItemEnabled('companies', False)
    buttons[1].click()
    assert control.currentKey() == 'overall' and spy.count() == 0
    with pytest.raises(ValueError):
        control.setCurrentKey('companies')
    control.setItemEnabled('companies', True)
    control.blockSignals(True)
    control.setCurrentKey('companies')
    control.blockSignals(False)
    assert control.currentKey() == 'companies' and spy.count() == 0
    control.setItemEnabled('companies', False)
    assert control.currentKey() == 'overall' and spy.count() == 1
    control.deleteLater()


def test_compact_and_regular_sizes_use_shared_tokens_and_group_border():
    app()
    for compact, height, font_size in ((False, tokens.CONTROL_HEIGHT, tokens.FONT_SIZE_BODY),
                                       (True, 28, tokens.FONT_SIZE_CAPTION)):
        control = FluentSegmentedControl(compact=compact)
        control.addItem('line', '折线', FluentIcon.PIE_SINGLE)
        control.addItem('area', '面积', FluentIcon.MARKET)
        assert control.height() == height
        assert all(button.height() <= height for button in control.findChildren(TogglePushButton))
        assert all(button.font().pixelSize() == font_size
                   for button in control.findChildren(TogglePushButton))
        assert tokens.BORDER in control.styleSheet()
        assert all('padding-left' in button.styleSheet() for button in control.findChildren(TogglePushButton))
        assert all(tokens.ACCENT in button.styleSheet()
                   for button in control.findChildren(TogglePushButton))
        assert control._subtle is compact
        selected_background = tokens.SEGMENT_QUIET_BG if compact else tokens.ACCENT
        control.show();app().processEvents()
        from PySide6.QtGui import QColor
        selected = control._buttons[control.currentKey()]
        image = control.grab().toImage()
        scale = image.devicePixelRatio()
        allowed = (selected_background, tokens.SEGMENT_QUIET_HOVER if compact else tokens.ACCENT_HOVER)
        assert image.pixelColor(round((selected.x()+5)*scale), round((selected.y()+8)*scale)).name() in {QColor(c).name() for c in allowed}
        control.deleteLater()


def test_dense_compact_segments_fit_three_character_label_without_clipping():
    app()
    control = FluentSegmentedControl(compact=True, dense=True)
    control.addItem('passenger', '客流')
    control.addItem('trips', '出行量')
    assert control.width() <= 120
    for button in control._buttons.values():
        assert button.fontMetrics().horizontalAdvance(button.text()) + 20 <= button.width()
    control.deleteLater()


def test_chinese_font_is_loaded_for_segment_labels():
    app()
    control = FluentSegmentedControl()
    control.addItem('companies', '多公司对比', FluentIcon.PEOPLE)
    from stats_controls import _FONT_ID
    assert _FONT_ID >= 0
    assert control.findChildren(TogglePushButton)[0].font().family() == tokens.FONT_FAMILY
    control.deleteLater()


def test_duplicate_or_unknown_key_is_rejected():
    app()
    control = FluentSegmentedControl()
    control.addItem('line', '折线')
    with pytest.raises(ValueError):
        control.addItem('line', '重复')
    with pytest.raises(KeyError):
        control.setCurrentKey('missing')
    with pytest.raises(KeyError):
        control.setItemEnabled('missing', False)
    control.deleteLater()


def test_selection_animation_settles_and_tab_focus_gets_visible_ring():
    app()
    control = FluentSegmentedControl()
    control.addItem('line', '折线', FluentIcon.MARKET)
    control.addItem('area', '面积', FluentIcon.PIE_SINGLE)
    control.show()
    app().processEvents()
    buttons = control.findChildren(TogglePushButton)
    buttons[1].setFocus()
    app().processEvents()
    buttons[0].setFocus(Qt.FocusReason.TabFocusReason)
    app().processEvents()
    assert buttons[0].property('keyboardFocus') is True
    control.setCurrentKey('area')
    QTest.qWait(190)
    assert buttons[1].graphicsEffect() is None
    control.close()


def test_rapid_switch_resize_and_reenable_leave_no_stale_effect():
    app()
    control = FluentSegmentedControl()
    control.addItem('default', '默认模式', FluentIcon.PIE_SINGLE)
    control.addItem('companies', '多公司对比', FluentIcon.PEOPLE)
    control.addItem('period', '同期对比', FluentIcon.CALENDAR)
    control.show()
    app().processEvents()
    control.setCurrentKey('period')
    control.setCurrentKey('default')
    control.resize(control.width(), control.height())
    control.setItemEnabled('period', False)
    control.setItemEnabled('period', True)
    QTest.qWait(190)
    assert control.currentKey() == 'default'
    assert [button.isChecked() for button in control._buttons.values()] == [True, False, False]
    assert all(button.graphicsEffect() is None for button in control._buttons.values())
    control.close()
