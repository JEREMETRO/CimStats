"""Capacity and interaction contract for the read-only departure panel."""
import copy
import importlib.util

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QEnterEvent, QHelpEvent
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QLabel, QToolTip


@pytest.fixture
def panel(qt_application, schedule_theme):
    if importlib.util.find_spec('line_schedule_view') is None:
        pytest.skip('SchedulePanel is not implemented')
    from line_schedule_view import SchedulePanel
    widget = SchedulePanel()
    widget.resize(904, 566)
    widget.show()
    qt_application.processEvents()
    yield widget
    widget.close()
    widget.deleteLater()


@pytest.fixture(scope='module')
def schedule_theme(qt_application):
    from stats_style import initialize_theme
    initialize_theme(qt_application)


def test_schedule_panel_is_available_to_line_page():
    assert importlib.util.find_spec('line_schedule_view'), 'SchedulePanel is not implemented'


def departures(count):
    return [dict(time=f'{6 + index // 60:02d}:{index % 60:02d}',
                 vehicle_type=('任意', '小型', '中型', '大型', '未知')[index % 5],
                 original_index=index) for index in range(count)]


def test_operating_time_shows_segments_and_only_special_annotations(panel):
    for times, expected, tip in (
        (['00:00','02:00','04:00','06:00','08:00','10:00','12:00','14:00','16:00','18:00','20:00','22:00'],
         '00:00-24:00', '24小时运营线路'),
        (['07:30','08:30','09:30','16:30','17:30','18:30'],
         '07:30-09:30    16:30-18:30', '分时段运营线路'),
        (['07:30','08:30','09:30'], '07:30-09:30', ''),
    ):
        panel.set_line({'班次': {'周一': [dict(time=t) for t in times]}})
        assert 'first' not in panel.summary_values and 'last' not in panel.summary_values
        assert panel.summary_labels['service'].text() == '运营时间'
        assert panel.summary_values['service'].text() == expected
        assert panel.summary_values['service'].toolTip() == tip
        assert panel.summary_labels['service'].toolTip() == tip


def test_narrow_operating_time_wraps_without_losing_segments(panel, qt_application):
    from PySide6.QtCore import QRect
    times = ['05:00','06:00','10:00','11:00','15:00','16:00','20:00','21:00']
    panel.set_line({'班次': {'周一': [dict(time=t) for t in times]}})
    panel.resize(400,700);qt_application.processEvents()
    value = panel.summary_values['service']
    assert all(segment in value.text() for segment in ('05:00-06:00','10:00-11:00','15:00-16:00','20:00-21:00'))
    bounds = value.fontMetrics().boundingRect(QRect(0,0,value.width(),10000), Qt.TextFlag.TextWordWrap, value.text())
    assert value.height() >= bounds.height()
    assert panel.summary_host.rect().contains(value.mapTo(panel.summary_host,value.rect().bottomRight()))


def test_period_tooltip_uses_actual_configured_ranges(panel):
    panel.period_rules = {'morning_peak': (('06:45','08:15'),),
                          'offpeak': (('08:15','12:00'),('14:00','18:00'))}
    panel.set_line({'班次': {'周一': [dict(time='07:00'),dict(time='07:10')]}})
    assert panel.summary_values['morning_peak'].toolTip() == '早高峰（06:45-08:15）平均间隔'
    assert panel.summary_labels['offpeak'].toolTip() == '平峰（08:15-12:00、14:00-18:00）平均间隔'
    assert '07:30' not in panel.summary_values['morning_peak'].toolTip()
    assert panel.summary_values['night'].toolTip() == '夜间（时段未确认）平均间隔'


@pytest.mark.parametrize('count', [0, 1, 50, 72, 100, 140, 200])
@pytest.mark.parametrize('width', [888, 904])
def test_all_departures_fit_without_scroll_and_final_time_is_visible(panel, qt_application, count, width):
    panel.set_expanded(count > 140)
    panel.resize(width, 818 if count > 140 else 458)
    panel.set_line({'班次': {'周五': departures(count)}})
    qt_application.processEvents()
    matrix, scroll = panel.matrix, panel.matrix_scroll
    assert len(matrix.entries) == count
    assert matrix.display_count == count
    assert panel.count_label.text() == f'{count} 班'
    assert panel.display_label.text() == f'显示 {count} / {count}'
    assert scroll.horizontalScrollBar().maximum() == 0
    assert scroll.verticalScrollBar().maximum() == 0
    assert matrix.height() >= (480 if count > 140 else 280)
    assert matrix.font().pixelSize() == 14
    assert matrix.font().weight() == 400
    assert matrix.focusPolicy() == Qt.FocusPolicy.NoFocus
    if count:
        rect = matrix.cell_rect(count - 1)
        point = matrix.mapTo(scroll.viewport(), rect.bottomRight())
        assert scroll.viewport().rect().contains(point), 'last departure is clipped'
        assert matrix.entry_at(rect.center()) == count - 1
        assert len(matrix.visible_indices()) == count
        assert matrix.columns == 10
        pixels = matrix.grab(rect).toImage()
        final_color = {1: '#242b32', 50: '#18314f', 72: '#206343',
                       100: '#18314f', 140: '#18314f', 200: '#18314f'}[count]
        assert sum(pixels.pixelColor(x, y).name() == final_color
                   for x in range(pixels.width()) for y in range(pixels.height())) >= 3, \
            'the last cell must contain real painted time text'
        # The cell holds the complete HH:mm width even in the tenth column.
        assert rect.width() >= matrix.fontMetrics().horizontalAdvance('23:59') + 12
    else:
        assert panel.summary['count'] == 0
        assert all(label.text() == '—' for key, label in panel.summary_values.items() if key != 'count')
        assert panel.summary_values['count'].text() == '0 班'


def test_201_departures_have_explicit_overflow_and_final_item_can_be_reached(panel, qt_application):
    panel.set_expanded(True)
    panel.set_line({'班次': {'周五': departures(201)}})
    qt_application.processEvents()
    scroll = panel.matrix_scroll
    assert len(panel.matrix.entries) == 201
    assert panel.matrix.row_height == 24
    assert panel.matrix.minimumHeight() == 504
    assert scroll.height() < panel.matrix.height()
    assert scroll.horizontalScrollBar().maximum() == 0
    assert scroll.verticalScrollBar().maximum() > 0
    assert not panel.overflow_label.isHidden()
    assert '滚动' in panel.overflow_label.text()
    scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())
    qt_application.processEvents()
    assert 200 in panel.matrix.visible_indices()
    assert panel.display_label.text().endswith('/ 201')


def test_actual_day_groups_keep_insertion_order_and_switch_without_stale_state(panel, qt_application):
    source = {'班次': {'周一': departures(1), '周二': departures(50),
                      '周三': [], '周四': departures(72)}}
    original = copy.deepcopy(source)
    panel.set_line(source)
    assert panel.day_groups == ('周一', '周二', '周三', '周四')
    assert panel.current_group == '周一'
    QTest.mouseClick(panel.group_buttons['周二'], Qt.MouseButton.LeftButton)
    qt_application.processEvents()
    assert panel.current_group == '周二'
    assert panel.summary['count'] == 50
    assert len(panel.matrix.entries) == 50
    assert panel.count_label.text() == '50 班'
    QTest.mouseClick(panel.group_buttons['周三'], Qt.MouseButton.LeftButton)
    assert panel.summary['count'] == 0
    assert panel.matrix.entries == []
    panel.set_line({'班次': {'周日': departures(1)}})
    assert panel.day_groups == ('周日',)
    assert panel.current_group == '周日'
    assert source == original
    assert not any('站点客流' in label.text() for label in panel.findChildren(QLabel))


def test_duplicates_midnight_tooltip_metadata_and_vehicle_accessibility(panel, qt_application):
    panel.set_line({'班次': {'周六': [
        {'time': '23:50', 'vehicle_type': '小型', '备注': '末段原始信息'},
        {'time': '00:10', 'vehicle_type': '大型', 'next_day': True, '备注': '夜间原始信息'},
        {'time': '23:50', 'vehicle_type': '未知'},
    ]}})
    qt_application.processEvents()
    entries = panel.matrix.entries
    assert [item['time'] for item in entries] == ['23:50', '23:50', '00:10']
    assert entries[-1]['next_day'] is True
    assert '次日' in panel.summary_values['service'].text()
    tooltip = panel.matrix.tooltip_for(2)
    assert tooltip.splitlines() == ['发班序号：第3班', '完整时刻：次日00:10', '车型：大型']
    assert entries[-1]['备注'] == '夜间原始信息'
    assert '大型' in panel.matrix.accessibleName()
    assert '车型：—' in panel.matrix.accessibleName()
    assert '未知' not in panel.matrix.accessibleName()
    rect = panel.matrix.cell_rect(2)
    help_event = QHelpEvent(QEvent.Type.ToolTip, rect.center(),
                           panel.matrix.mapToGlobal(rect.center()))
    qt_application.sendEvent(panel.matrix, help_event)
    from qfluentwidgets import ToolTip
    from PySide6.QtGui import QPalette
    tip = panel.matrix._tooltip
    assert isinstance(tip, ToolTip) and tip.isVisible() and tip.text() == tooltip
    assert tip.container.palette().color(QPalette.ColorRole.Window).lightness() > 230
    assert tip.shadowEffect.blurRadius() > 0
    assert tip.rect().contains(tip.label.mapTo(tip, tip.label.rect().bottomRight()))
    panel.matrix.set_entries(entries)
    assert not tip.isVisible(), 'changing timetable must hide stale details'
    assert panel.matrix.vehicle_color(entries[1]) != panel.matrix.vehicle_color({'vehicle_type': '任意'})
    assert panel.matrix.vehicle_color({'vehicle_type': '新车型'}) == panel.matrix.vehicle_color({'vehicle_type': '未知'})
    assert not panel.matrix.findChildren(QLabel), 'time cells should be painted text'


def test_clear_resets_summary_selection_counts_and_overflow(panel):
    panel.set_line({'班次': {'周日': departures(201)}})
    panel.clear()
    assert panel.day_groups == ()
    assert panel.current_group is None
    assert panel.matrix.entries == []
    assert panel.summary['count'] == 0
    assert panel.count_label.text() == '0 班'
    assert panel.display_label.text() == '显示 0 / 0'
    assert panel.overflow_label.isHidden()


def test_panel_minimum_fits_parent_budget_and_small_width_never_clips_time(panel, qt_application):
    panel.set_line({'班次': {'周一至周四': departures(140), '周五': [], '周六': [], '周日': []}})
    assert panel.minimumSizeHint().width() <= 400
    assert panel.minimumHeight() <= 458
    panel.resize(400, 544)
    qt_application.processEvents()
    assert panel.matrix_scroll.horizontalScrollBar().maximum() == 0
    # Narrow content overflows locally rather than growing the whole panel.
    assert panel.height() == 544
    assert panel.matrix_scroll.verticalScrollBar().maximum() > 0
    panel.matrix_scroll.verticalScrollBar().setValue(panel.matrix_scroll.verticalScrollBar().maximum())
    qt_application.processEvents()
    assert 139 in panel.matrix.visible_indices()
    assert panel.matrix.cell_rect(139).width() >= panel.matrix.fontMetrics().horizontalAdvance('08:19') + 12
    assert panel.width() <= 400


def test_data_loaded_before_show_does_not_force_a_tall_window(qt_application):
    from line_schedule_view import SchedulePanel
    widget = SchedulePanel()
    widget.resize(904, 566)
    widget.set_line({'班次': {'周五': departures(140)}})
    widget.show()
    qt_application.processEvents()
    try:
        assert widget.height() <= 566, 'pre-show layout used an uninitialized one-column viewport'
        assert widget.matrix.columns == 10
        assert widget.matrix.display_count == 140
    finally:
        widget.close()
        widget.deleteLater()


def test_model_day_groups_exclude_legacy_empty_placeholder(panel):
    panel.set_line({'日组': ['周一', '周二', '周三', '周四', '周五', '周六', '周日'],
                    '班次': {'周一至周四': [], '周五': [], '周六': [], '周日': [],
                             '周一': departures(1), '周二': departures(50),
                             '周三': [], '周四': departures(72)}})
    assert panel.day_groups == ('周一', '周二', '周三', '周四', '周五', '周六', '周日')
    assert panel.current_group == '周一'
    assert panel.summary['count'] == 1
    assert '周一至周四' not in panel.group_buttons


def test_schedule_uses_statistics_typography_and_shared_day_selector(panel, qt_application):
    from stats_controls import FluentSegmentedControl
    import stats_tokens as tokens
    panel.set_line({'班次': {'周一': departures(1), '周二': departures(1)}})
    qt_application.processEvents()
    assert isinstance(panel.group_control, FluentSegmentedControl)
    assert panel.matrix.font().family() == tokens.FONT_FAMILY
    metrics = panel.matrix.fontMetrics()
    assert len({metrics.horizontalAdvance(str(digit)) for digit in range(10)}) == 1
    assert panel.title_label.font().families()[0].startswith('Segoe UI')
    assert panel.title_label.font().pixelSize() == tokens.FONT_SIZE_CHART_TITLE
    assert panel.title_label.palette().color(panel.title_label.foregroundRole()).name() == tokens.TEXT_PRIMARY.lower()
    assert all(value.font().weight() == 600 for value in panel.summary_values.values())
    assert all(value.height() >= value.fontMetrics().height() for value in panel.summary_values.values())
    assert panel.title_icon.size().width() == 18


def test_tooltip_numbers_merged_operating_day_not_source_timetable(panel):
    panel.set_line({'班次': {'周日': [
        {'time': '23:50', '发班序号': '99', '时刻表序号': '8', 'vehicle_type': '小型'},
        {'time': '00:10', '发班序号': '1', '时刻表序号': '9', 'vehicle_type': '大型'},
        {'time': '23:50', '发班序号': '5', '时刻表序号': '7', 'vehicle_type': '任意'},
    ]}})
    assert [panel.matrix.tooltip_for(i).splitlines() for i in range(3)] == [
        ['发班序号：第1班', '完整时刻：23:50', '车型：小型'],
        ['发班序号：第2班', '完整时刻：23:50', '车型：任意'],
        ['发班序号：第3班', '完整时刻：次日00:10', '车型：大型'],
    ]
    assert panel.matrix.entries[0]['发班序号'] == '99'


def test_tooltip_keeps_real_seconds_while_matrix_displays_only_hours_minutes(panel):
    panel.set_line({'班次': {'周日': [
        {'time': '06:00', '发班_tick': '216300000000', 'vehicle_type': '中型'},
    ]}})
    assert panel.matrix.entries[0]['time'] == '06:00'
    assert panel.matrix.tooltip_for(0).splitlines() == [
        '发班序号：第1班', '完整时刻：06:00:30', '车型：中型']


def test_compact_height_preserves_140_times_and_only_four_vehicle_legend(panel, qt_application):
    panel.set_line({'班次': {'周一': departures(140)}})
    panel.resize(888, 458)
    qt_application.processEvents()
    assert panel.height() <= 458
    assert panel.minimumHeight() <= 458
    assert panel.matrix_scroll.viewport().height() >= 280
    assert panel.matrix.display_count == 140
    assert panel.matrix.columns == 10
    assert panel.matrix_scroll.verticalScrollBar().maximum() == 0
    assert '未知' not in panel.legend_label.text()
    assert all(name in panel.legend_label.text() for name in ('任意', '小型', '中型', '大型'))
    assert not any(label.isVisible() and '灰底' in label.text() for label in panel.findChildren(QLabel))


def test_day_departure_count_is_in_six_item_summary_and_changes_with_selection(panel):
    panel.set_line({'班次': {'周一': departures(200), '周二': departures(1)}})
    assert tuple(panel.summary_values) == ('service', 'count', 'morning_peak', 'evening_peak', 'offpeak', 'night')
    assert panel.summary_labels['count'].text() == '日发班'
    assert panel.summary_values['count'].text() == '200 班'
    assert panel.count_label is panel.summary_values['count']
    panel.set_current_group('周二')
    assert panel.summary_values['count'].text() == '1 班'


@pytest.mark.parametrize('vehicle_fields', [
    {}, {'vehicle_type': '未知'}, {'vehicle_type': '未识别的新车型'},
])
def test_missing_vehicle_is_unavailable_with_neutral_text_and_retained_metadata(panel, vehicle_fields):
    import stats_tokens as tokens
    source = {'time': '06:00', '原始备注': '保留原记录', **vehicle_fields}
    original = copy.deepcopy(source)
    panel.set_line({'班次': {'周一': [source]}})
    assert panel.matrix.tooltip_for(0).splitlines() == [
        '发班序号：第1班', '完整时刻：06:00', '车型：—']
    assert panel.matrix.vehicle_color(panel.matrix.entries[0]).name() == tokens.TEXT_PRIMARY.lower()
    assert panel.matrix.vehicle_color(panel.matrix.entries[0]) != panel.matrix.vehicle_color({'vehicle_type': '任意'})
    assert '未知' not in panel.legend_label.text()
    assert '车型：—' in panel.matrix.accessibleName()
    assert source == original
    assert all(panel.matrix.entries[0][key] == value for key, value in source.items())


def test_panel_hover_uses_shared_elevation_without_changing_layout(panel, qt_application):
    from stats_elevation import CardElevation
    controller = panel.findChild(CardElevation)
    assert controller is not None, 'panel must use the shared Fluent elevation'
    geometry = panel.geometry()
    qt_application.sendEvent(panel, QEnterEvent(QPointF(), QPointF(),
                                               QPointF(panel.mapToGlobal(QPoint()))))
    QTest.qWait(180)
    assert controller.hovered and controller.level > 0
    assert panel.geometry() == geometry
    assert panel.matrix.graphicsEffect() is None
    finished = QSignalSpy(controller.animation.finished)
    qt_application.sendEvent(panel, QEvent(QEvent.Type.Leave))
    if controller.level != 0:
        assert finished.wait(1000), 'shared elevation must finish fading out'
    assert not controller.hovered and controller.level == 0


def test_shared_fluent_scroll_reaches_last_overflow_by_keyboard(panel, qt_application):
    from stats_controls import StatisticsScrollArea
    assert isinstance(panel.matrix_scroll, StatisticsScrollArea)
    panel.set_line({'班次': {'周一': departures(201)}})
    qt_application.processEvents()
    panel.matrix_scroll.setFocus()
    QTest.keyClick(panel.matrix_scroll, Qt.Key.Key_End)
    qt_application.processEvents()
    assert panel.matrix_scroll.verticalScrollBar().value() == panel.matrix_scroll.verticalScrollBar().maximum()
    assert 200 in panel.matrix.visible_indices()


def test_morning_and_evening_summary_values_are_independent(panel):
    panel.set_line({'班次': {'周一': [
        {'time': '07:30'}, {'time': '07:40'}, {'time': '17:00'}, {'time': '17:20'},
    ]}})
    assert panel.summary_values['morning_peak'].text() == '10m0s'
    assert panel.summary_values['evening_peak'].text() == '20m0s'
    assert panel.summary_labels['morning_peak'].text() == '早高峰平均间隔'
    assert panel.summary_labels['evening_peak'].text() == '晚高峰平均间隔'


def test_shared_content_track_left_aligns_time_and_leaves_information_gaps(panel, qt_application):
    panel.set_line({'班次': {'周一': departures(140)}})
    panel.resize(888, 458)
    qt_application.processEvents()
    track = panel.title_icon.mapTo(panel, QPoint()).x()
    assert panel.group_host.mapTo(panel, QPoint()).x() >= panel.title_label.geometry().right()
    assert abs(panel.group_host.mapTo(panel,panel.group_host.rect().center()).y()-
               panel.title_label.mapTo(panel,panel.title_label.rect().center()).y())<=2
    assert panel.summary_labels['service'].mapTo(panel, QPoint()).x() == track
    assert panel.matrix.mapTo(panel, QPoint()).x() == track
    summary_bottom = panel.summary_host.mapTo(panel, QPoint()).y() + panel.summary_host.height()
    assert panel.matrix.mapTo(panel, QPoint()).y() - summary_bottom >= 8
    group_bottom = panel.group_host.mapTo(panel, QPoint()).y() + panel.group_host.height()
    assert panel.summary_host.mapTo(panel, QPoint()).y() - group_bottom >= 8
    assert panel.matrix.cell_rect(0).height() == panel.matrix.row_height
    assert panel.matrix.row_height >= 22
    for index in (0, 9, 139):
        pixels = panel.matrix.grab(panel.matrix.cell_rect(index)).toImage()
        color = panel.matrix.vehicle_color(panel.matrix.entries[index]).name()
        ink_x = [x for x in range(pixels.width()) for y in range(pixels.height())
                 if pixels.pixelColor(x, y).name() == color]
        assert ink_x and min(ink_x) <= 4, 'time is centered instead of aligned to its column start'


def test_period_background_uses_model_tags_and_next_day_has_priority(panel, qt_application):
    panel.set_line({'班次': {'周一': []}})
    rows = [
        {'time': '12:00', 'period': 'morning_peak', 'vehicle_type': '小型'},
        {'time': '12:05', 'period': 'evening_peak', 'vehicle_type': '小型'},
        {'time': '12:10', 'period': 'offpeak', 'vehicle_type': '小型'},
        {'time': '01:00', 'period': 'morning_peak', 'next_day': True, 'vehicle_type': '小型'},
        {'time': '01:10', 'period': 'evening_peak', 'next_day': True, 'vehicle_type': '小型'},
    ]
    panel.matrix.set_entries(rows)
    qt_application.processEvents()
    colors = []
    for index in range(5):
        cell = panel.matrix.grab(panel.matrix.cell_rect(index)).toImage()
        colors.append(cell.pixelColor(cell.width() - 2, cell.height() // 2))
    assert colors[0] != colors[1]
    assert colors[0] != colors[2] and colors[1] != colors[2]
    assert colors[3] == colors[4] and colors[3] != colors[0] and colors[3] != colors[1]
    assert all(min(color.red(), color.green(), color.blue()) >= 220 for color in colors)


def test_all_day_model_result_starts_at_midnight_without_next_day_shading(panel):
    panel.set_line({'班次': {'周一': [{'time': f'{hour:02}:00'} for hour in range(24)]}})
    assert panel.summary['all_day'] is True
    assert panel.matrix.entries[0]['time'] == '00:00'
    assert panel.matrix.entries[-1]['time'] == '23:00'
    assert all(entry['next_day'] is False for entry in panel.matrix.entries)


def test_period_legend_matches_distinct_visible_backgrounds(panel):
    from line_schedule_view import PERIOD_COLORS
    assert set(panel.period_swatches)=={'morning_peak','evening_peak','night','next_day'}
    colors=[]
    for key,color in PERIOD_COLORS.items():
        entry={'period':key,'next_day':key=='next_day'}
        assert panel.matrix.background_color(entry).name()==color.lower()
        assert color in panel.period_swatches[key].styleSheet()
        colors.append(color)
    assert len(set(colors))==4
    evening=panel.matrix.background_color({'period':'evening_peak'})
    assert evening.blue()-evening.red()>=18


def test_expansion_requests_parent_action_and_expanded_200_fit_without_scroll(panel, qt_application):
    panel.set_line({'班次': {'周一': departures(200)}})
    panel.resize(888, 458)
    qt_application.processEvents()
    assert panel.expanded is False
    assert len(panel.matrix.entries) == 200
    assert 0 < panel.matrix.display_count < 200
    assert panel.matrix_scroll.verticalScrollBar().maximum() > 0
    assert panel.overflow_label.isVisible()
    assert '滚动' in panel.overflow_label.text()
    received = QSignalSpy(panel.expansionRequested)
    QTest.mouseClick(panel.expansion_button, Qt.MouseButton.LeftButton)
    assert received.count() == 1 and received.at(0) == [True]
    assert panel.expanded is False, 'parent owns the data-card collapse'
    panel.set_expanded(True)
    panel.resize(888, 818)
    qt_application.processEvents()
    assert panel.matrix.row_height == min(30, max(24, panel.matrix.height() // 20))
    assert panel.matrix.minimum_row_height == 24
    assert panel.matrix.cell_rect(0).height() == panel.matrix.row_height
    assert panel.matrix.display_count == 200
    assert panel.matrix_scroll.verticalScrollBar().maximum() == 0
    assert panel.overflow_label.isHidden()
    assert panel.expansion_button.accessibleName() == '显示线路数据'
    QTest.mouseClick(panel.expansion_button, Qt.MouseButton.LeftButton)
    assert received.count() == 2 and received.at(1) == [False]
    panel.set_expanded(False)
    panel.resize(888, 458)
    qt_application.processEvents()
    assert panel.matrix.cell_rect(0).height() >= panel.matrix.fontMetrics().height() + 4
    assert 0 < panel.matrix.display_count < 200


@pytest.mark.parametrize('width', [888, 904])
def test_expanded_stride_fills_available_height_and_can_shrink_back(panel, qt_application, width):
    panel.set_expanded(True)
    panel.set_line({'班次': {'周一': departures(200)}})
    for height in (818, 958):
        panel.resize(width, height)
        qt_application.processEvents()
        matrix = panel.matrix
        assert matrix.columns == 10
        assert matrix.minimumHeight() == 480
        assert matrix.row_height == min(30, max(24, matrix.height() // 20))
        assert matrix.minimum_row_height == 24
        assert 28 <= matrix.row_height <= 30
        assert matrix.row_offset == 0
        assert matrix.cell_rect(0).top() == 0
        assert matrix.display_count == 200
        assert panel.matrix_scroll.verticalScrollBar().maximum() == 0
        for index in (0, 10, 100, 199):
            cell = matrix.cell_rect(index)
            assert cell.y() == matrix.row_offset + index // 10 * matrix.row_height
            assert cell.height() == matrix.row_height
            assert matrix.entry_at(cell.center()) == index
            assert matrix.entry_at(cell.bottomRight()) == index
        assert matrix.tooltip_for(matrix.entry_at(matrix.cell_rect(199).center())).startswith('发班序号：第200班\n')
    panel.resize(width, panel.minimumHeight())
    qt_application.processEvents()
    assert panel.height() == panel.minimumHeight()
    assert panel.matrix.minimumHeight() == 480
    assert panel.matrix.row_height == 24
    assert panel.matrix.display_count < 200
    panel.matrix_scroll.verticalScrollBar().setValue(panel.matrix_scroll.verticalScrollBar().maximum())
    qt_application.processEvents()
    assert 199 in panel.matrix.visible_indices()
    panel.set_expanded(False)
    panel.resize(width, 818)
    qt_application.processEvents()
    assert panel.matrix.minimumHeight() <= panel.matrix_scroll.viewport().height()
    assert panel.matrix.minimum_row_height >= panel.matrix.fontMetrics().height() + 4
    assert panel.matrix.row_height == 30
    assert panel.matrix.display_count == 200


@pytest.mark.parametrize('width', [888, 904])
@pytest.mark.parametrize('expanded', [False, True])
def test_summary_values_share_matrix_ten_column_tracks_without_clipping(panel, qt_application, width, expanded):
    panel.set_expanded(expanded)
    panel.set_line({'班次': {'周一': departures(200 if expanded else 140)}})
    panel.resize(width, 818 if expanded else 458)
    qt_application.processEvents()
    for index, (key, column) in enumerate({'service': 0, 'count': 2, 'morning_peak': 3,
                                          'evening_peak': 5, 'offpeak': 7, 'night': 9}.items()):
        matrix_x = (panel.summary_host.x() + (0 if index == 0 else index + 1) * panel.summary_host.width() // 7 if expanded
                    else panel.matrix.mapTo(panel, panel.matrix.cell_rect(column).topLeft()).x())
        summary_x = panel.summary_values[key].mapTo(panel, QPoint()).x()
        assert abs(summary_x - matrix_x) <= 1, f'{key} is off the time column track'
        label = panel.summary_labels[key]
        assert label.width() >= label.fontMetrics().horizontalAdvance(label.text()), f'{key} caption is clipped'
    assert panel._summary_layout.horizontalSpacing() == 0


def test_expanded_summary_has_readable_values_and_complete_next_day_time(panel, qt_application):
    rows = [dict(time=f'{(300 + i * 6) // 60 % 24:02d}:{(300 + i * 6) % 60:02d}',
                 vehicle_type='任意') for i in range(200)]
    panel.set_expanded(True)
    panel.set_line({'班次': {'周一': rows}})
    panel.resize(888, 812)
    qt_application.processEvents()
    assert panel.summary_values['service'].text() == '05:00-次日00:54'
    for key, value in panel.summary_values.items():
        label = panel.summary_labels[key]
        assert value.font().pixelSize() == 21
        assert label.font().pixelSize() == 12
        assert value.height() >= value.fontMetrics().height()
        assert value.width() >= value.fontMetrics().horizontalAdvance(value.text())
        assert label.width() >= label.fontMetrics().horizontalAdvance(label.text())
        assert value.y() == panel.summary_values['service'].y()
    assert panel.summary_host.height() == 64
    assert panel.matrix.display_count == 200
    assert 28 <= panel.matrix.row_height <= 30
    assert panel.matrix_scroll.verticalScrollBar().maximum() == 0
    panel.set_expanded(False)
    panel.set_line({'班次': {'周一': departures(140)}})
    panel.resize(888, 818)
    qt_application.processEvents()
    assert panel.matrix.row_height == 30
    assert panel.matrix.minimumHeight() <= panel.matrix_scroll.viewport().height()
    assert panel.matrix.display_count == 140


@pytest.mark.parametrize('height', [842, 848])
def test_expanded_week_row_and_matrix_follow_summary_without_artificial_gap(panel, qt_application, height):
    panel.set_line({'班次': {'周一': departures(200), '周二': departures(140)}})
    panel.set_expanded(True)
    panel.resize(888, height)
    qt_application.processEvents()
    assert panel.title_label.font().pixelSize() == 18
    assert panel.title_label.height() == 36
    assert panel.group_host.height() == 36
    assert panel.group_control.height() == 28
    assert panel.group_control.y() == 4
    title_bottom = panel.title_label.mapTo(panel, QPoint()).y() + panel.title_label.height()
    assert panel.group_host.y() - title_bottom == 12
    summary_bottom = panel.summary_host.y() + panel.summary_host.height()
    first = panel.matrix.cell_rect(0)
    first_top = panel.matrix.mapTo(panel, first.topLeft()).y()
    assert first_top - summary_bottom == 12
    assert panel.matrix.row_offset == 0
    assert 29 <= panel.matrix.row_height <= 30
    assert 0 <= panel.matrix.height() - 20 * panel.matrix.row_height < 30
    assert panel.matrix.display_count == 200
    assert panel.matrix_scroll.verticalScrollBar().maximum() == 0
    last = panel.matrix.cell_rect(199)
    assert panel.matrix_scroll.viewport().rect().contains(panel.matrix.mapTo(panel.matrix_scroll.viewport(), last.bottomRight()))
    assert panel.matrix.entry_at(first.center()) == 0
    assert panel.matrix.entry_at(last.center()) == 199
    panel.set_expanded(False)
    panel.set_current_group('周二')
    panel.resize(888, 482)
    qt_application.processEvents()
    assert panel.title_label.font().pixelSize() == 14
    assert panel.group_host.height() == 28
    assert abs(panel.group_host.geometry().center().y() - panel.title_label.geometry().center().y()) <= 2
    assert panel.summary_host.height() == 40
    assert panel._layout.contentsMargins().left() == 16
    assert panel._layout.spacing() == 8
    assert panel.matrix.display_count == 140
    assert panel.matrix_scroll.verticalScrollBar().maximum() == 0
    panel.set_expanded(True)
    panel.set_current_group('周一')
    panel.resize(888, height)
    qt_application.processEvents()
    assert panel.matrix.mapTo(panel, panel.matrix.cell_rect(0).topLeft()).y() - (panel.summary_host.y() + panel.summary_host.height()) == 12
    assert panel.matrix.display_count == 200


def test_period_bands_round_only_ends_of_contiguous_runs(panel, qt_application):
    from line_schedule_view import PERIOD_COLORS
    import stats_tokens as tokens
    panel.resize(888, 458)
    panel.matrix.set_entries([
        dict(time='06:00', period='morning_peak', vehicle_type='任意'),
        dict(time='06:10', period='morning_peak', vehicle_type='任意'),
        dict(time='17:00', period='evening_peak', vehicle_type='任意'),
        *[dict(time='12:00', period='offpeak', vehicle_type='任意') for _ in range(6)],
        dict(time='23:50', period='night', vehicle_type='任意'),
        dict(time='00:10', period='night', vehicle_type='任意'),
    ])
    qt_application.processEvents()
    matrix = panel.matrix
    pixels = matrix.grab().toImage()
    dpr = pixels.devicePixelRatio()
    def pixel_color(x, y):
        # QRects use logical pixels; grab() stores physical pixels at this DPR.
        return pixels.pixelColor(int((x + 0.5) * dpr), int((y + 0.5) * dpr))
    first, second = matrix.cell_rect(0), matrix.cell_rect(1)
    top = first.top() + 2
    assert pixel_color(first.left(), top).name() == tokens.CARD_BG.lower()
    assert pixel_color(first.left() + 8, top + 1).name() == PERIOD_COLORS['morning_peak'].lower()
    assert pixel_color(first.right(), top + 1).name() == PERIOD_COLORS['morning_peak'].lower()
    assert pixel_color(second.left(), top + 1).name() == PERIOD_COLORS['morning_peak'].lower()
    assert pixel_color(second.right(), top).name() == tokens.CARD_BG.lower()
    for index in (0, 1, 9, 10):
        assert matrix.entry_at(matrix.cell_rect(index).center()) == index
    assert not matrix.findChildren(QLabel)


@pytest.mark.parametrize('expanded', [False, True])
def test_summary_emphasis_shapes_variable_numbers_with_chinese_fallback(panel, qt_application, expanded):
    from PySide6.QtGui import QFont, QFontDatabase, QTextLayout
    import stats_tokens as tokens
    panel.set_expanded(expanded)
    panel.resize(904, 818 if expanded else 458)
    count = 200 if expanded else 140
    panel.set_line({'班次': {'周五': [
        {'time': f'{(300 + 6 * index) % 1440 // 60:02d}:{(300 + 6 * index) % 60:02d}',
         'vehicle_type': '任意'} for index in range(count)]}})
    qt_application.processEvents()
    assert panel.matrix.display_count == count
    assert panel.matrix_scroll.verticalScrollBar().maximum() == 0
    assert panel.matrix.font().family() == tokens.FONT_FAMILY
    assert panel.matrix.font().weight() == 400
    variable_available = any('Segoe UI Variable' in family for family in QFontDatabase.families())
    for value in panel.summary_values.values():
        font = value.font()
        assert font.pixelSize() == (21 if expanded else 14)
        if variable_available:
            assert font.variableAxisValue(QFont.Tag('opsz')) == (36. if expanded else 20.)
        else:
            assert not font.isVariableAxisSet(QFont.Tag('opsz'))
        assert value.width() >= value.fontMetrics().horizontalAdvance(value.text())
        assert value.height() >= value.fontMetrics().height()
        layout = QTextLayout('200 00:54 6m0s 次日班', font)
        layout.beginLayout()
        line = layout.createLine()
        line.setLineWidth(1000)
        layout.endLayout()
        runs = layout.glyphRuns()
        assert runs
        latin = [run.rawFont() for run in runs if run.rawFont().familyName().startswith('Segoe UI')]
        chinese = [run.rawFont() for run in runs if run.rawFont().familyName() == tokens.FONT_FAMILY]
        assert latin and chinese, [(run.rawFont().familyName(), run.glyphIndexes()) for run in runs]
        assert all(font.weight() == 600 for font in latin + chinese)
        if variable_available:
            assert all(font.familyName().startswith('Segoe UI Variable') and len(font.fontTable('fvar')) > 0
                       for font in latin)


def test_panel_hides_inactive_group_and_preserves_enabled_zero_midnight(panel):
    source = {'班次': {'周一': [{'time': '00:00', '运行日掩码': 2}],
                       '周二': [], '未启用': [{'time': '12:00', '运行日掩码': 0}]}}
    before = copy.deepcopy(source)
    panel.set_line(source)
    assert panel.day_groups == ('周一', '周二')
    assert panel.matrix.entries[0]['time'] == '00:00'
    panel.set_current_group('周二')
    assert panel.summary['count'] == 0
    assert panel.summary_host.isVisible()
    assert source == before


def test_panel_filters_explicit_disabled_rows_without_using_cached_summary(panel):
    from line_schedule import prepare_schedule
    rows = [{'time': '00:00', '运行日掩码': 130},
            {'time': '12:00', '运行日掩码': 128},
            {'time': '13:00', '运行日状态': '未启用'},
            {'time': '14:00', '运行日掩码': None}]
    panel.set_line({'班次': {'周一': rows}, '时刻表': {'周一': prepare_schedule(rows)}})
    assert [row['time'] for row in panel.matrix.entries] == ['14:00', '00:00']
    assert panel.summary['count'] == 2


def test_panel_switch_to_inactive_clears_selection_summary_scroll_and_back(panel, qt_application):
    active = {'班次': {'周一': departures(1), '周五': departures(201)}}
    panel.set_line(active)
    panel.set_current_group('周五')
    qt_application.processEvents()
    scroll = panel.matrix_scroll.verticalScrollBar()
    assert scroll.maximum() > 0
    scroll.setValue(scroll.maximum())
    point = panel.matrix.cell_rect(200).center()
    qt_application.sendEvent(panel.matrix, QHelpEvent(
        QEvent.Type.ToolTip, point, panel.matrix.mapToGlobal(point)))
    assert panel.matrix._tooltip.isVisible()
    panel.set_line({'显示日组': [], '日组': ['周一', '未启用'],
                    '班次': {'周一': [], '未启用': [{'time': '12:00', '运行日掩码': 0}]}})
    qt_application.processEvents()
    assert panel.day_groups == ()
    assert panel.current_group is None
    assert panel.group_combo.count() == 0
    assert panel.group_control is None
    assert panel.matrix.entries == []
    assert panel.matrix._hover is None
    assert panel.matrix._tooltip.isHidden()
    assert panel.summary['count'] == 0
    assert panel.matrix_scroll.verticalScrollBar().value() == 0
    assert panel.summary_host.isHidden()
    assert panel.footer_host.isHidden()
    assert panel.expansion_button.isHidden()
    assert panel.empty_label.isVisible()
    assert panel.empty_label.text() == '暂无已启用时刻表'
    assert all(label.toolTip() == '' for label in panel.summary_values.values())
    panel.set_line(active)
    assert panel.current_group == '周一'
    assert len(panel.matrix.entries) == 1
    assert panel.summary_host.isVisible()
    assert panel.footer_host.isVisible()
    assert panel.expansion_button.isVisible()
    assert panel.empty_label.isHidden()


def test_panel_all_explicit_inactive_rows_do_not_create_day_tabs(panel):
    panel.set_line({'班次': {'周一': [{'time': '00:00', '运行日掩码': 0}],
                            '未启用': [{'time': '06:00'}]}})
    assert panel.day_groups == ()
    assert panel.current_group is None
    assert panel.matrix.entries == []
