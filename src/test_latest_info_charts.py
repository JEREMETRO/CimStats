"""Old analysis interaction contracts. Run only in the assigned offscreen slot."""
from dataclasses import replace
from decimal import Decimal
from math import cos, sin, radians

import pytest

from test_latest_info_page import page, snapshot, session, child, inside, label_texts


def local_click(widget, point, application):
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    point = QPointF(point)
    event = QMouseEvent(QEvent.Type.MouseButtonPress, point, point,
                        Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
                        Qt.KeyboardModifier.NoModifier)
    application.sendEvent(widget, event)
    application.processEvents()


@pytest.mark.parametrize('panel_name', ['passengerRanking', 'departureStructure'])
def test_real_fluent_segments_remain_visible_selected_and_preserve_local_scope(page, qt_application, panel_name):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from stats_controls import FluentSegmentedControl
    page.set_session(session())
    page.set_snapshot(snapshot())
    panel = child(page, panel_name)
    other = page.departures if panel is page.passengers else page.passengers
    before = other.capture_state()
    assert isinstance(panel.view_selector, FluentSegmentedControl)
    assert not hasattr(panel, 'view_label')
    buttons = (panel.structure_button, panel.ranking_button, panel.share_button)
    for view, button in zip(('structure', 'ranking', 'line_share'), buttons):
        assert all(item.isVisible() for item in buttons)
        QTest.mouseClick(button, Qt.MouseButton.LeftButton)
        assert panel.view_selector.currentKey() == view and button.isChecked()
        assert sum(item.isChecked() for item in buttons) == 1
        assert panel.capture_state()['view'] == view and other.capture_state() == before
    panel.show_ranking('地铁')
    assert '地铁' in panel.mode_combo.text()
    QTest.mouseClick(panel.share_button, Qt.MouseButton.LeftButton)
    assert panel.capture_state() == {'view': 'line_share', 'mode': '地铁'}
    QTest.mouseClick(panel.structure_button, Qt.MouseButton.LeftButton)
    assert panel.capture_state() == {'view': 'structure', 'mode': None}
    assert not panel.mode_combo.isEnabled() and '全部制式' in panel.mode_combo.text()


@pytest.mark.parametrize('panel_name', ['passengerRanking', 'departureStructure'])
@pytest.mark.parametrize('key_name', ['Key_Return', 'Key_Enter', 'Key_Space'])
def test_segments_focus_arrow_and_activation_keys_use_actual_buttons(page, qt_application, panel_name, key_name):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    page.set_session(session())
    page.set_snapshot(snapshot())
    panel = child(page, panel_name)
    panel.structure_button.setFocus(Qt.FocusReason.TabFocusReason)
    qt_application.processEvents()
    assert panel.structure_button.hasFocus()
    QTest.keyClick(panel.structure_button, Qt.Key.Key_Right)
    assert panel.ranking_button.hasFocus() and panel.capture_state()['view'] == 'ranking'
    QTest.keyClick(panel.ranking_button, Qt.Key.Key_Right)
    assert panel.share_button.hasFocus() and panel.capture_state()['view'] == 'line_share'
    QTest.keyClick(panel.share_button, Qt.Key.Key_Left)
    assert panel.ranking_button.hasFocus() and panel.capture_state()['view'] == 'ranking'
    panel.structure_button.setFocus(Qt.FocusReason.TabFocusReason)
    QTest.keyClick(panel.structure_button, getattr(Qt.Key, key_name))
    assert panel.capture_state() == {'view': 'structure', 'mode': None}


@pytest.mark.parametrize('panel_name', ['passengerRanking', 'departureStructure'])
def test_visible_range_menu_real_item_click_uses_data_key_and_checkmark(page, qt_application, panel_name):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    page.set_session(session())
    page.set_snapshot(snapshot())
    panel = child(page, panel_name)
    other = page.departures if panel is page.passengers else page.passengers
    before = other.capture_state()
    QTest.mouseClick(panel.ranking_button, Qt.MouseButton.LeftButton)
    QTest.mouseClick(panel.mode_combo, Qt.MouseButton.LeftButton)
    qt_application.processEvents()
    menu = panel.mode_combo.range_menu
    assert menu.isVisible()
    index = panel.mode_combo.findData('地铁')
    item = menu.view.item(index)
    QTest.mouseClick(menu.view.viewport(), Qt.MouseButton.LeftButton,
                     pos=menu.view.visualItemRect(item).center())
    qt_application.processEvents()
    assert panel.capture_state() == {'view': 'ranking', 'mode': '地铁'}
    assert '地铁' in panel.mode_combo.text() and panel.mode_combo.currentData() == '地铁'
    assert item.data(Qt.ItemDataRole.UserRole).isChecked()
    assert sum(menu.view.item(i).data(Qt.ItemDataRole.UserRole).isChecked()
               for i in range(menu.view.count())) == 1
    assert other.capture_state() == before and page.scope() == ('', '综合')


@pytest.mark.parametrize('key_name', ['Key_Return', 'Key_Enter', 'Key_Space'])
def test_range_menu_opens_from_actual_keyboard_focus(page, qt_application, key_name):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    page.set_session(session())
    page.set_snapshot(snapshot())
    panel = page.passengers
    panel.show_ranking()
    panel.mode_combo.setFocus(Qt.FocusReason.TabFocusReason)
    qt_application.processEvents()
    assert panel.mode_combo.hasFocus()
    QTest.keyClick(panel.mode_combo, getattr(Qt.Key, key_name))
    qt_application.processEvents()
    assert panel.mode_combo.range_menu.isVisible()


@pytest.mark.parametrize('key_name', ['Key_Return', 'Key_Enter', 'Key_Space'])
def test_range_menu_keyboard_selects_focused_real_item_once(page, qt_application, key_name):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    page.set_session(session())
    page.set_snapshot(snapshot())
    panel = page.passengers
    panel.show_ranking()
    panel.mode_combo.setFocus(Qt.FocusReason.TabFocusReason)
    QTest.keyClick(panel.mode_combo, Qt.Key.Key_Return)
    menu = panel.mode_combo.range_menu
    view = menu.view
    assert view.hasFocus()
    view.setCurrentRow(0)
    QTest.keyClick(view, Qt.Key.Key_Down)
    assert view.currentRow() == 1
    emissions = []
    panel.mode_combo.currentIndexChanged.connect(emissions.append)
    QTest.keyClick(view, getattr(Qt.Key, key_name))
    qt_application.processEvents()
    assert emissions == [1]
    assert panel.capture_state() == {'view': 'ranking', 'mode': snapshot().modes[0]}
    assert not menu.isVisible()


def test_analysis_card_grows_from_actual_content_size_hint_without_clipping_modes(page, qt_application):
    from latest_info_model import ModeCount
    data = snapshot()
    lines = tuple(replace(data.lines[0], key=f'extended-mode-{i}', mode=f'自定义制式{i}', passengers=1)
                  for i in range(13))
    data = replace(data, lines=lines, passenger_top10=lines[:10],
                   passenger_modes=tuple(ModeCount(line.mode, 1) for line in lines))
    page.set_session(session())
    page.set_snapshot(data)
    qt_application.processEvents()
    panel = page.passengers
    rows = panel.visible_mode_rows()
    assert len(rows) == 13 and all(inside(panel.structure, row) for row in rows)
    assert panel.height() > page.trend.height()


@pytest.mark.parametrize('panel_name', ['passengerRanking', 'departureStructure'])
def test_short_mode_names_remain_complete_and_selected_segment_uses_accent(page, qt_application, panel_name):
    from latest_info_model import ModeCount
    from PySide6.QtGui import QColor
    import stats_tokens as tokens
    data = snapshot()
    counts = (ModeCount('有轨电车', 100), ModeCount('无轨电车', 0))
    data = replace(data, passenger_modes=counts, departure_modes=counts, total_departures=100)
    page.set_session(session())
    page.set_snapshot(data)
    qt_application.processEvents()
    panel = child(page, panel_name)
    for row in panel.visible_mode_rows():
        assert row.name.text() == row.mode
        assert row.name.contentsRect().width() >= row.name.fontMetrics().horizontalAdvance(row.name.text()) + 2
        assert row.share.contentsRect().width() >= row.share.fontMetrics().horizontalAdvance(row.share.text())
        assert all(label.text() != '›' for label in row.findChildren(type(row.name)))
    button = panel.structure_button
    assert button.isChecked()
    # The fill belongs to the shared segmented surface and moves behind buttons.
    image = panel.view_selector.grab().toImage()
    scale = image.devicePixelRatio()
    assert image.pixelColor(round((button.x()+5)*scale), round((button.y()+8)*scale)).name() == QColor(tokens.ACCENT).name()


@pytest.mark.parametrize('panel_name', ['passengerRanking', 'departureStructure'])
@pytest.mark.parametrize('view', ['ranking', 'line_share'])
@pytest.mark.parametrize('key_name', ['Key_Return', 'Key_Enter', 'Key_Space'])
def test_focused_return_button_keys_restore_structure_once(page, qt_application, panel_name, view, key_name):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    page.set_session(session())
    page.set_snapshot(snapshot())
    panel = child(page, panel_name)
    other = page.departures if panel is page.passengers else page.passengers
    other.show_line_share('公交')
    other_before = other.capture_state()
    getattr(panel, 'show_' + view)('公交')
    qt_application.processEvents()
    button = panel.return_button
    clicks = []
    button.clicked.connect(lambda checked=False: clicks.append(checked))
    button.setFocus(Qt.FocusReason.TabFocusReason)
    qt_application.processEvents()
    assert button.hasFocus()
    QTest.keyClick(button, getattr(Qt.Key, key_name))
    qt_application.processEvents()
    assert clicks == [False]
    assert panel.capture_state() == {'view': 'structure', 'mode': None}
    assert other.capture_state() == other_before


@pytest.mark.parametrize('key_name', ['Key_Return', 'Key_Enter', 'Key_Space'])
def test_disabled_return_button_keys_do_not_activate(page, qt_application, key_name):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    page.set_session(session())
    page.set_snapshot(snapshot())
    panel = page.passengers
    panel.show_ranking('公交')
    button = panel.return_button
    button.setFocus(Qt.FocusReason.TabFocusReason)
    qt_application.processEvents()
    assert button.hasFocus()
    clicks = []
    button.clicked.connect(lambda checked=False: clicks.append(checked))
    button.setEnabled(False)
    QTest.keyClick(button, getattr(Qt.Key, key_name))
    qt_application.processEvents()
    assert clicks == []
    assert panel.capture_state() == {'view': 'ranking', 'mode': '公交'}


@pytest.mark.parametrize('key_name', ['Key_Return', 'Key_Enter'])
def test_icon_button_enter_keys_ignore_auto_repeat_and_release(page, qt_application, key_name):
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtTest import QTest
    from qfluentwidgets import FluentIcon
    from latest_info_charts import icon_button
    button = icon_button(FluentIcon.RETURN, 'keyboardProbe', '返回制式分布', page)
    button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    button.show()
    button.setFocus(Qt.FocusReason.TabFocusReason)
    qt_application.processEvents()
    assert button.hasFocus()
    clicks = []
    button.clicked.connect(lambda checked=False: clicks.append(checked))
    key = getattr(Qt.Key, key_name)
    QTest.keyPress(button, key)
    assert clicks == [False]
    for kind in (QEvent.Type.KeyRelease, QEvent.Type.KeyPress):
        qt_application.sendEvent(button, QKeyEvent(kind, key, Qt.KeyboardModifier.NoModifier, '', True, 1))
    QTest.keyRelease(button, key)
    assert clicks == [False]
    QTest.keyClick(button, key)
    assert clicks == [False, False]


@pytest.mark.parametrize('attribute', ['passengers', 'departures'])
def test_share_denominator_is_full_range_and_other_is_real_remainder(attribute):
    from latest_info_charts import line_share_data
    data = snapshot()
    lines = tuple(replace(data.lines[0], key=f'share-{i}', name=f'{i}路',
                          **{attribute: Decimal(20 - i)}) for i in range(12))
    total = sum(getattr(line, attribute) for line in lines)
    entries, denominator = line_share_data(lines, attribute, total)
    assert len(entries) == 11 and denominator == total == 174
    assert [entry.line_key for entry in entries[:10]] == [f'share-{i}' for i in range(10)]
    assert entries[-1].name == '其他线路（2条）' and entries[-1].value == 19
    assert sum(entry.value for entry in entries) == denominator
    assert entries[0].value / denominator != entries[0].value / 155


@pytest.mark.parametrize('invalid', [None, Decimal('NaN'), float('inf'), -1])
def test_partial_share_keeps_known_values_without_fabricating_complete_percentages(invalid):
    from latest_info_charts import line_share_data
    data = snapshot()
    lines = (replace(data.lines[0], passengers=5), replace(data.lines[1], passengers=invalid),
             replace(data.lines[2], passengers=0))
    entries, denominator = line_share_data(lines, 'passengers', None)
    assert denominator is None
    assert [entry.value for entry in entries] == [Decimal(5), Decimal(0), None]
    assert [entry.line_key for entry in entries] == [lines[0].key, lines[2].key, None]
    assert entries[-1].name == '其他线路（1条）' and not entries[-1].complete


@pytest.mark.parametrize('panel_name', ['passengerRanking', 'departureStructure'])
def test_default_combined_structure_keeps_ring_all_modes_and_explicit_actions(page, qt_application, panel_name):
    page.set_session(session())
    page.set_snapshot(snapshot())
    qt_application.processEvents()
    panel = child(page, panel_name)
    assert panel.capture_state() == {'view': 'structure', 'mode': None}
    assert panel.ring.isVisible()
    assert panel.ring.width() >= 128 and panel.ring.height() >= 128
    assert len(panel.visible_mode_rows()) == 6
    assert all(row.isVisible() and inside(panel, row) for row in panel.visible_mode_rows())
    assert panel.ranking_button.text() == '线路排行'
    assert panel.share_button.text() == '线路占比'


@pytest.mark.parametrize('panel_name', ['passengerRanking', 'departureStructure'])
@pytest.mark.parametrize('entry', ['sector', 'list'])
def test_real_category_events_use_stable_key_and_do_not_also_expand_share(page, qt_application, panel_name, entry):
    from PySide6.QtCore import QPointF
    page.set_session(session())
    page.set_snapshot(snapshot())
    qt_application.processEvents()
    panel = child(page, panel_name)
    dispatches = []
    panel.ring.mode_requested.connect(lambda key: dispatches.append(('mode', key)))
    panel.ring.share_requested.connect(lambda: dispatches.append(('share', None)))
    if entry == 'sector':
        sector = panel.ring.sectors()[0]
        mode = sector[2]
        angle = radians((sector[0] + sector[1]) / 2 - 90)
        center, radius = panel.ring.geometry_for_hit()
        local_click(panel.ring, QPointF(center.x() + cos(angle) * radius * .85,
                                        center.y() + sin(angle) * radius * .85), qt_application)
    else:
        row = panel.visible_mode_rows()[0]
        mode = row.mode
        local_click(row, row.rect().center(), qt_application)
    assert panel.capture_state() == {'view': 'ranking', 'mode': mode}
    assert all(row.line.mode == mode for row in panel.visible_ranking_rows())
    if entry == 'sector':
        assert dispatches == [('mode', mode)]
    assert panel.return_button.toolTip() == '返回制式分布'
    panel.return_button.click()
    assert panel.capture_state() == {'view': 'structure', 'mode': None}


@pytest.mark.parametrize('panel_name', ['passengerRanking', 'departureStructure'])
@pytest.mark.parametrize('entry', ['button', 'center', 'blank'])
def test_share_opens_in_same_card_and_aggregate_returns_directly_to_structure(page, qt_application, panel_name, entry):
    from PySide6.QtCore import QPointF
    data = snapshot()
    lines = tuple(replace(data.lines[0], key=f'expanded-{i}', name=f'{i}路',
                          passengers=20 - i, departures=20 - i) for i in range(12))
    from latest_info_model import ModeCount
    total = sum(line.passengers for line in lines)
    data = replace(data, lines=lines, passenger_top10=lines[:10],
                   passenger_modes=(ModeCount('公交', total),),
                   departure_modes=(ModeCount('公交', total),), total_departures=total)
    page.set_session(session())
    page.set_snapshot(data)
    qt_application.processEvents()
    panel = child(page, panel_name)
    other = page.departures if panel is page.passengers else page.passengers
    other_before = other.capture_state()
    if entry == 'button':
        panel.share_button.click()
    elif entry == 'center':
        local_click(panel.ring, panel.ring.rect().center(), qt_application)
    else:
        local_click(panel.ring, QPointF(1, 1), qt_application)
    assert panel.capture_state() == {'view': 'line_share', 'mode': None}
    assert panel.stack.currentWidget() is panel.line_share
    assert len(panel.visible_share_rows()) == 11
    assert all(inside(panel, row) for row in panel.visible_share_rows())
    assert '其他线路（2条）' in label_texts(panel.visible_share_rows()[-1])
    assert panel.visible_share_rows()[-1].number.text().startswith('19 ')
    assert panel.return_button.toolTip() == '返回制式分布'
    panel.return_button.click()
    assert panel.capture_state() == {'view': 'structure', 'mode': None}
    assert other.capture_state() == other_before


def test_independent_states_refresh_restore_scope_invalidation_and_new_session_reset(page, qt_application):
    data = snapshot()
    page.set_session(session())
    page.set_snapshot(data)
    page.passengers.show_ranking('地铁')
    page.departures.show_line_share()
    saved = page.capture_chart_state()
    page.set_snapshot(data)
    assert page.capture_chart_state() == saved
    page.set_session(session())
    page.set_snapshot(data)
    assert page.restore_chart_state(saved)
    assert page.capture_chart_state() == saved
    page.set_snapshot(replace(data, lines=tuple(line for line in data.lines if line.mode != '地铁'),
                              passenger_modes=tuple(count for count in data.passenger_modes if count.mode != '地铁')))
    assert page.passengers.capture_state() == {'view': 'structure', 'mode': None}
    assert page.departures.capture_state() == {'view': 'line_share', 'mode': None}
    page.set_session(session('new-save'))
    page.set_snapshot(replace(data, session_key='new-save'))
    assert not page.restore_chart_state(saved)
    assert page.passengers.capture_state() == page.departures.capture_state() == {'view': 'structure', 'mode': None}


def test_scope_signal_capture_preserves_source_scope_and_independent_intent_through_repeated_changes(page):
    page.set_session(session())
    page.set_snapshot(snapshot())
    page.passengers.show_ranking('地铁')
    page.departures.show_line_share()
    before = page.capture_chart_state()
    captures = []
    page.scope_changed.connect(lambda *_: captures.append(page.capture_chart_state()))
    page.company_combo.setCurrentIndex(page.company_combo.findData('company-b'))
    assert captures[-1] == before
    captures[-1]['passengers']['mode'] = '公交'
    assert page.capture_chart_state() == before  # detached copies, no shared mutable intent
    page.mode_combo.setCurrentIndex(page.mode_combo.findData('地铁'))
    assert captures[-1] == before
    page.clear_session()
    assert page.capture_chart_state()['passengers']['view'] == 'structure'


@pytest.mark.parametrize('panel_name', ['passengerRanking', 'departureStructure'])
def test_combined_structure_ring_shows_values_as_the_only_compact_exception(page, qt_application, panel_name):
    page.set_session(session())
    page.set_snapshot(snapshot())
    qt_application.processEvents()
    panel = child(page, panel_name)
    assert panel.ring.center_total.text() == ('955' if panel_name == 'passengerRanking' else '155')
    assert not hasattr(panel, 'stacked')
    assert all(row.number.text() != '—' and row.share.text().endswith('%') for row in panel.visible_mode_rows())
    assert panel.ring.center_total.isVisible() and panel.total_label.isHidden()
    assert all(row.number.isVisible() and row.share.isVisible() for row in panel.visible_mode_rows())


@pytest.mark.parametrize('panel_name', ['passengerRanking', 'departureStructure'])
def test_ranking_has_ten_real_tracks_visible_mode_identity_exact_value_and_key(page, qt_application, panel_name):
    page.set_session(session())
    page.set_snapshot(snapshot())
    panel = child(page, panel_name)
    panel.ranking_button.click()
    qt_application.processEvents()
    rows = panel.visible_ranking_rows()
    assert len(rows) == 10 and all(inside(panel, row) for row in rows)
    assert all(row.track.width() >= 80 for row in rows)
    assert all(row.line.mode in row.name.text() for row in rows)
    assert all(row.number.isHidden() and row.number.text() in row.accessibleName() for row in rows)
    assert all(row.track.toolTip() == '' for row in rows)  # Final approved cancellation stays in force.
    emitted = []
    page.line_requested.connect(emitted.append)
    rows[0].action.click()
    assert emitted == [rows[0].line.key]


@pytest.mark.parametrize('panel_name', ['passengerRanking', 'departureStructure'])
def test_missing_mode_total_never_draws_a_complete_100_percent_distribution(page, qt_application, panel_name):
    data = snapshot()
    counts = tuple(replace(count, value=None if i == 0 else count.value)
                   for i, count in enumerate(data.passenger_modes if panel_name == 'passengerRanking' else data.departure_modes))
    data = replace(data, passenger_modes=counts) if panel_name == 'passengerRanking' else replace(data, departure_modes=counts, total_departures=None)
    page.set_session(session())
    page.set_snapshot(data)
    qt_application.processEvents()
    panel = child(page, panel_name)
    assert panel.ring.sectors() == []
    assert '总量不完整' in panel.status.text()
    assert all(row.share.text() == '—' for row in panel.visible_mode_rows())


def test_shared_mode_colors_use_keys_and_unknown_modes_are_not_one_fixed_slot():
    from latest_info_charts import mode_color, short_line_name
    from stats_charts import ChartPanel
    import stats_tokens as tokens
    statistics_panel = ChartPanel('颜色基准', allowed_modes=('line',))
    statistics_panel.set_category_palette(tokens.DATA_CATEGORY_COLORS)
    for chinese, key in [('公交', 'bus'), ('有轨电车', 'tram'), ('无轨电车', 'trolley'),
                         ('地铁', 'metro'), ('水上巴士', 'waterbus')]:
        assert mode_color(chinese) == mode_color(key) == statistics_panel._category_color(key)
    assert len({mode_color(f'未知制式{i}').name() for i in range(20)}) > 1
    statistics_panel.close()
    statistics_panel.deleteLater()


@pytest.mark.parametrize('panel_name', ['passengerRanking', 'departureStructure'])
def test_line_share_uses_visible_matching_legend_colors_and_human_slice_labels(page, qt_application, panel_name):
    from latest_info_charts import mode_color, short_line_name
    page.set_session(session())
    page.set_snapshot(snapshot())
    panel = child(page, panel_name)
    panel.share_button.click()
    qt_application.processEvents()
    assert panel.share_ring.caption == '线路占比'
    for row in panel.visible_share_rows():
        expected = mode_color(row.entry.mode)
        assert panel.share_ring.colors[row.entry.key] == expected
        assert row.dot.property('legendColor') == expected.name()
        assert row.dot.isVisible()
        assert panel.share_ring.display_labels[row.entry.key] == f'{row.entry.mode} {row.entry.name}'
        assert row.entry.key not in panel.share_ring.display_labels[row.entry.key]


@pytest.mark.parametrize('panel_name', ['passengerRanking', 'departureStructure'])
def test_tiny_sector_exact_key_and_zero_categories_remain_available(page, qt_application, panel_name):
    from PySide6.QtCore import QPointF
    from latest_info_model import ModeCount
    data = snapshot()
    counts = (ModeCount('公交', 99999), ModeCount('地铁', 1), ModeCount('水上巴士', 0))
    data = replace(data, passenger_modes=counts) if panel_name == 'passengerRanking' else replace(data, departure_modes=counts, total_departures=100000)
    page.set_session(session())
    page.set_snapshot(data)
    qt_application.processEvents()
    panel = child(page, panel_name)
    assert len(panel.visible_mode_rows()) == 2
    assert panel._counts[-1].value == 0
    assert panel.mode_combo.findData('水上巴士') >= 0
    sector = panel.ring.sectors()[-1]
    angle = radians((sector[0] + sector[1]) / 2 - 90)
    center, radius = panel.ring.geometry_for_hit()
    dispatches = []
    panel.ring.mode_requested.connect(lambda key: dispatches.append(('mode', key)))
    panel.ring.share_requested.connect(lambda: dispatches.append(('share', None)))
    local_click(panel.ring, QPointF(center.x() + cos(angle) * radius * .85,
                                    center.y() + sin(angle) * radius * .85), qt_application)
    assert dispatches == [('mode', '地铁')]
    assert panel.capture_state() == {'view': 'ranking', 'mode': '地铁'}


def test_scope_restore_is_strict_by_default_and_never_relaxes_save_identity(page):
    page.set_session(session())
    page.set_snapshot(snapshot())
    page.passengers.ranking_button.click()
    saved = page.capture_chart_state()
    page.company_combo.setCurrentIndex(page.company_combo.findData('company-b'))
    assert not page.restore_chart_state(saved, allow_scope_change=True)  # no accepted snapshot yet
    page.set_snapshot(replace(snapshot(), company_id='company-b'))
    assert not page.restore_chart_state(saved)
    assert page.restore_chart_state(saved, allow_scope_change=True)
    assert page.passengers.capture_state() == {'view': 'ranking', 'mode': None}
    assert not page.restore_chart_state({**saved, 'session_key': 'different'}, allow_scope_change=True)


@pytest.mark.parametrize('panel_name', ['passengerRanking', 'departureStructure'])
def test_list_keyboard_drill_and_same_name_line_key_actions_are_real(page, qt_application, panel_name):
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent
    data = snapshot()
    first = replace(data.lines[0], key='company-a:one', name='101路', mode='公交', passengers=8, departures=8)
    second = replace(first, key='company-b:one', company_id='company-b', passengers=4, departures=4)
    from latest_info_model import ModeCount
    data = replace(data, lines=(first, second), passenger_top10=(first, second),
                   passenger_modes=(ModeCount('公交', 12),), departure_modes=(ModeCount('公交', 12),), total_departures=12)
    page.set_session(session())
    page.set_snapshot(data)
    qt_application.processEvents()
    panel = child(page, panel_name)
    event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
    qt_application.sendEvent(panel.visible_mode_rows()[0], event)
    qt_application.processEvents()
    assert panel.capture_state() == {'view': 'ranking', 'mode': '公交'}
    identities = []
    page.line_requested.connect(identities.append)
    for row in panel.visible_ranking_rows():
        row.action.click()
    assert identities == ['company-a:one', 'company-b:one']


@pytest.mark.parametrize('panel_name,title', [('passengerRanking', '当日客流结构'), ('departureStructure', '班次结构')])
def test_guided_view_names_icon_return_and_cross_view_local_scope(page, qt_application, panel_name, title):
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent
    page.set_session(session())
    page.set_snapshot(snapshot())
    qt_application.processEvents()
    panel = child(page, panel_name)
    assert panel.title.text() == title
    assert panel.ranking_button.text() == '线路排行'
    assert not panel.return_button.isVisible()
    default_return_geometry = panel.return_slot.geometry()
    row = next(row for row in panel.visible_mode_rows() if row.mode == '公交')
    local_click(row, row.rect().center(), qt_application)
    assert panel.title.text() == title and panel.view_selector.currentKey() == 'ranking'
    assert panel.return_button.toolTip() == panel.return_button.accessibleName() == '返回制式分布'
    assert panel.return_button.width() >= 28 and panel.return_button.height() >= 28
    panel.share_button.click()
    assert panel.capture_state() == {'view': 'line_share', 'mode': '公交'}
    assert all(row.entry.mode == '公交' for row in panel.visible_share_rows() if row.entry.line_key)
    panel.ranking_button.click()
    assert panel.capture_state() == {'view': 'ranking', 'mode': '公交'}
    assert panel.return_slot.geometry() == default_return_geometry
    event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Space, Qt.KeyboardModifier.NoModifier)
    panel.return_button.setFocus()
    qt_application.sendEvent(panel.return_button, event)
    release = QKeyEvent(QEvent.Type.KeyRelease, Qt.Key.Key_Space, Qt.KeyboardModifier.NoModifier)
    qt_application.sendEvent(panel.return_button, release)
    qt_application.processEvents()
    assert panel.capture_state() == {'view': 'structure', 'mode': None}


def test_other_line_count_is_real_and_zero_remainder_has_no_sector():
    from latest_info_charts import line_share_data
    data = snapshot()
    lines = tuple(replace(data.lines[0], key=f'zero-other-{i}', passengers=20-i if i < 10 else 0) for i in range(13))
    entries, total = line_share_data(lines, 'passengers', sum(line.passengers for line in lines))
    assert entries[-1].name == '其他线路（3条）' and entries[-1].value == 0
    assert entries[-1].count == 3 and total == 155


@pytest.mark.parametrize('panel_name', ['passengerRanking', 'departureStructure'])
def test_six_digit_total_stays_in_data_without_line_share_ring_label(page, qt_application, panel_name):
    from latest_info_model import ModeCount
    data = snapshot()
    lines = tuple(replace(line, passengers=82572 if i == 0 else 82568,
                          departures=line.departures*1000) for i, line in enumerate(data.lines))
    data = replace(data, lines=lines,
                   passenger_modes=tuple(ModeCount(mode, sum(line.passengers for line in lines if line.mode == mode))
                                         for mode in data.modes),
                   departure_modes=tuple(replace(item, value=item.value*1000) for item in data.departure_modes),
                   total_departures=155000)
    page.set_session(session())
    page.set_snapshot(data)
    panel = child(page, panel_name)
    panel.share_button.click()
    qt_application.processEvents()
    assert panel.share_ring.center_total.isHidden()
    value = panel.share_ring.center_total
    assert value.text() == ('825,684' if panel_name == 'passengerRanking' else '155,000')
    assert panel.total_label.isHidden()


def test_million_total_and_actual_other_count_fit_in_line_share(page, qt_application):
    from latest_info_model import ModeCount
    data = snapshot()
    lines = tuple(replace(data.lines[0], key=f'million-{i}', name=f'{101+i}路',
                          passengers=84193 if i == 0 else 37500 if i < 10 else 15188 if i == 10 else 15154)
                  for i in range(73))
    data = replace(data, lines=lines, passenger_modes=(ModeCount('公交', 1376429),))
    page.set_session(session())
    page.set_snapshot(data)
    page.passengers.share_button.click()
    qt_application.processEvents()
    panel = page.passengers
    assert panel.share_ring.center_total.isHidden()
    assert panel.share_ring.center_total.text() == '1,376,429'
    other = panel.visible_share_rows()[-1]
    assert other.entry.name == '其他线路（63条）' and other.entry.value == 954736
    assert inside(panel, other) and other.number.isHidden() and other.share.isHidden()
    assert other.name.text() == other.entry.name and other.name.isVisible()
    assert other.name.contentsRect().width() >= other.name.fontMetrics().horizontalAdvance('其他线路')
    assert other.toolTip() == '' and other.number.text() in other.accessibleName()


@pytest.mark.parametrize('value', [Decimal('123456789012'), Decimal('123456789012345678901234567')])
def test_long_finite_totals_are_visible_only_in_structure_without_duplicate_total(page, qt_application, value):
    from latest_info_model import ModeCount
    from latest_info_charts import shown
    data = snapshot()
    line = replace(data.lines[0], passengers=value)
    data = replace(data, lines=(line,), passenger_top10=(line,), passenger_modes=(ModeCount('公交', value),))
    page.set_session(session())
    page.set_snapshot(data)
    for view in ('structure', 'line_share', 'ranking', 'structure', 'line_share'):
        panel = page.passengers
        getattr(panel, 'show_' + view)()
        qt_application.processEvents()
        if view == 'ranking':
            continue
        ring = panel.ring if view == 'structure' else panel.share_ring
        assert ring.total == value and ring.center_total.text() == shown(value)
        if view == 'structure':
            assert ring.center_total.isVisible() != panel.total_label.isVisible()
            assert all(row.number.isVisible() and row.share.isVisible() for row in panel.visible_mode_rows())
        else:
            assert ring.center_total.isHidden() and panel.total_label.isHidden()
            assert all(row.number.isHidden() and row.share.isHidden() for row in panel.visible_share_rows())
