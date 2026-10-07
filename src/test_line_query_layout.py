"""Regression checks for the existing line query at whole-window size."""
import copy
import os
import time
from pathlib import Path
import pytest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QScrollArea, QToolButton
import desktop_app
from report_model import load_session

@pytest.fixture
def lines_window(qt_application, monkeypatch, tmp_path):
    monkeypatch.setattr(desktop_app, 'QSettings', lambda *a: QSettings(str(tmp_path/'line.ini'), QSettings.Format.IniFormat))
    monkeypatch.setattr(desktop_app.MainWindow, 'check_install', lambda self: None)
    window=desktop_app.MainWindow()
    data=load_session(Path(os.environ.get('CIM2_LINE_TEST_SESSION_DIR', Path(__file__).resolve().parents[1]/'exports')),
                      os.environ.get('CIM2_LINE_TEST_SESSION_TAG', '望春市_test_运行时'))
    if not data['lines']:
        pytest.skip('Local exported-save fixture is unavailable')
    data.update(history=[], save_path='TEST DATA.save', save_key='layout-test')
    window.on_completed(data)
    window.resize(1424, 921)  # reserve native frame/title within 1440 x 960
    window.show(); window.navigate(1); window.line_clicked(0,0)
    for _ in range(8): qt_application.processEvents()
    yield window
    window.close()


def test_line_page_has_independent_list_and_complete_compact_cards(lines_window):
    w=lines_window
    assert not isinstance(w.pages.widget(1), QScrollArea)
    assert len(w.fact_cards)==9
    assert all(c.height()==86 and c.isVisible() for c in w.fact_cards)
    assert not any(c.findChildren(QToolButton) for c in w.fact_cards)
    assert all(c.icon.width() == c.icon.height() == 18 for c in w.fact_cards)
    from stats_tokens import FONT_FAMILY, TEXT_PRIMARY, BORDER
    assert all(c.value.font().families()[0].startswith('Segoe UI') for c in w.fact_cards)
    assert all(TEXT_PRIMARY in c.value.styleSheet() and BORDER in c.styleSheet() for c in w.fact_cards)
    assert [c.label.text() for c in w.fact_cards][:3]==['线路车库','开线日期','地图里程']
    assert [c.note_label.text() for c in w.fact_cards][3:6]==['核定速度','平均间隔','平均车辆需求数']
    assert w.lines_page.right_scroll.verticalScrollBar().maximum()==0
    assert w.lines_page.right_scroll.horizontalScrollBar().maximum()==0
    assert w.lines_page.left.width()==436
    # The shared shell can keep its sidebar expanded; verify the actual
    # allocation still contains every card instead of assuming a hidden sidebar.
    from PySide6.QtCore import QPoint, QRect
    viewport = w.lines_page.right_scroll.viewport()
    assert viewport.width() >= w.lines_page.right_host.minimumWidth()
    assert all(viewport.rect().contains(QRect(c.mapTo(viewport, QPoint()), c.size()))
               for c in w.fact_cards)


@pytest.mark.parametrize('collapsed', [False, True])
def test_real_schedule_summary_fits_both_sidebar_modes(lines_window, qt_application, collapsed):
    from PySide6.QtCore import QPoint, QRect
    w = lines_window
    w.set_sidebar_collapsed(collapsed)
    for _ in range(8): qt_application.processEvents()
    page = w.lines_page
    schedule = page.schedule_panel
    assert schedule.summary_host.height() == 40
    assert page.right_scroll.verticalScrollBar().maximum() == 0
    assert page.right_scroll.horizontalScrollBar().maximum() == 0
    viewport = page.right_scroll.viewport()
    assert viewport.rect().contains(QRect(schedule.mapTo(viewport, QPoint()), schedule.size()))
    for label in (*schedule.summary_labels.values(), *schedule.summary_values.values()):
        assert label.fontMetrics().horizontalAdvance(label.text()) <= label.width()


def test_list_expands_above_details_without_reflow_and_reverses(lines_window,qt_application):
    from PySide6.QtTest import QTest
    w=lines_window; page=w.lines_page
    right=page.right_scroll.geometry()
    page.set_expanded(True, animated=False)
    assert page.left.width()>right.width()
    assert page.right_scroll.geometry()==right
    assert [i for i in range(14) if not w.line_table.isColumnHidden(i)] == [i for i in range(14) if i != 4]
    assert all(action.text() != '折算 km' for action in page.line_columns_menu.actions())
    assert w.line_table.columnCount() == 14 and w.line_table.item(0, 4) is not None
    assert '折算里程' in w.data['lines'][0]
    page.set_expanded(False, animated=False)
    assert page.left.width()==436 and page.right_scroll.geometry()==right
    assert [i for i in range(14) if not w.line_table.isColumnHidden(i)]==[2,7,8,9,10]
    page.set_expanded(True); QTest.qWait(50); page.set_expanded(False); QTest.qWait(300)
    assert page.left.width()==436
    assert page.expand_button.accessibleName()=='展开线路列表'


def test_sorted_selection_survives_search_refresh(lines_window):
    w=lines_window
    w.line_table.sortItems(7, Qt.SortOrder.DescendingOrder)
    w.line_clicked(0,0); key=w.selected_key
    w.refresh_lines()
    row=w.line_table.currentRow()
    assert w.line_table.item(row,0).data(Qt.ItemDataRole.UserRole)==key
    assert w._selected_line['key']==key
    assert w.line_table.item(row,2).text()==w._selected_line['线路名称']


def test_filtered_selection_clears_footer(lines_window):
    w=lines_window
    w.query.setText('不存在的线路___')
    assert not w.selected_key and w._selected_line is None
    assert w.lines_page.list_footer.text()=='从列表选择线路'


def test_reimport_clears_previous_selection_footer(lines_window):
    w=lines_window
    w.on_completed(copy.deepcopy(w.data))
    assert not w.selected_key and w._selected_line is None
    assert w.lines_page.list_footer.text()=='从列表选择线路'


def test_fact_units_match_statistics_caption_and_text_uses_readable_detail_size(lines_window):
    from stats_tokens import FONT_SIZE_KPI, FONT_SIZE_CAPTION
    w=lines_window
    assert w.fact_cards[0].value.font().pixelSize()==18
    assert w.fact_cards[1].value.font().pixelSize()==18
    assert w.lines_page.detail_title.font().pixelSize()==18
    metric=w.fact_cards[2].value
    assert metric.font().pixelSize()==FONT_SIZE_KPI
    assert metric.unit_font().pixelSize()==FONT_SIZE_CAPTION
    assert metric.text()==metric.accessibleName() and 'km' in metric.text()


def test_garage_and_date_first_lines_share_font_and_baseline(lines_window, qt_application):
    from PySide6.QtCore import QPoint
    from stats_tokens import TEXT_PRIMARY
    garage, date = lines_window.fact_cards[:2]
    garage.value.setText('888888\n888888')
    date.value.setText('888888')
    qt_application.processEvents()
    assert garage.value.font().pixelSize() == date.value.font().pixelSize() == 18
    assert date.value.alignment() & Qt.AlignmentFlag.AlignTop
    assert garage.value.alignment() & Qt.AlignmentFlag.AlignTop
    assert garage.value.height() >= 2 * garage.value.fontMetrics().lineSpacing()
    first_ink = []
    for card in (garage, date):
        pixels = card.value.grab().toImage()
        ink_y = [y for y in range(pixels.height()) for x in range(pixels.width())
                 if pixels.pixelColor(x, y).name() == TEXT_PRIMARY.lower()]
        assert ink_y
        first_ink.append(card.value.mapTo(lines_window.lines_page.detail, QPoint()).y() + min(ink_y))
    assert abs(first_ink[0] - first_ink[1]) <= 1


def test_navigation_interrupts_surface_motion_without_reflow(lines_window, qt_application):
    from PySide6.QtTest import QTest
    w = lines_window
    page = w.lines_page
    before = page.right_scroll.geometry()
    w.navigate(0)
    QTest.qWait(35)
    w.navigate(1)
    QTest.qWait(35)
    w.navigate(2)
    assert not page.motion.running
    assert page.graphicsEffect() is None
    QTest.qWait(35)
    w.navigate(1)
    # Check natural completion with a bounded condition: a fixed 320 ms can
    # expire between paint and animation ticks when the real-save UI is busy.
    deadline = time.monotonic() + 2
    while page.motion.running and time.monotonic() < deadline:
        QTest.qWait(10)
    assert page.right_scroll.geometry() == before
    assert page.graphicsEffect() is None
    assert not page.motion.running
    assert page.right_scroll.verticalScrollBar().maximum() == 0
    w.navigate(1)
    assert not page.motion.running


def test_unknown_running_day_does_not_display_confirmed_count_as_total(lines_window):
    w = lines_window
    line = copy.deepcopy(w._selected_line)
    line['班次数据完整'] = False
    line['当日发班数'] = 0
    line['当日发班数Tooltip'] = '有班次运行日缺失；已确认0班，无法确认当日总数。'
    w.show_line(line)
    assert w.fact_cards[4].value.text() == '—'
    assert w.fact_cards[4].value.toolTip() == ''  # Daily departure count explicitly has no tooltip.
    assert line['当日发班数'] == 0


def test_unknown_source_values_keep_real_zero_distinct(lines_window):
    from line_query_page import line_display_value
    w = lines_window
    line = copy.deepcopy(w._selected_line)
    line['地图里程'] = line['站点数'] = 0
    line['字段可用性'] = {'地图里程': False, '站点数': False}
    w.show_line(line)
    assert w.fact_cards[2].value.text() == '—'
    assert w.fact_cards[2].note_value.text() == '—'
    assert w.fact_cards[3].note_value.text() == '—'
    line['字段可用性'] = {'地图里程': True, '站点数': True}
    assert line_display_value(line, '地图里程') == 0
    assert line_display_value(line, '站点数') == 0
    line['班次数据完整'] = False
    assert line_display_value(line, '今日平均单班人次') is None
    assert line_display_value(line, '今日平均车公里人次') is None


def test_theme_initialization_does_not_rewrap_fluent_styles(qt_application):
    from qfluentwidgets import TableWidget
    from qfluentwidgets.common.style_sheet import styleSheetManager
    from stats_style import initialize_theme
    initialize_theme(qt_application)
    table = TableWidget()
    source = styleSheetManager.source(table)
    for _ in range(8):
        initialize_theme(qt_application)
    assert styleSheetManager.source(table) is source
    table.deleteLater()
    qt_application.processEvents()


def test_fact_collapse_gives_timetable_full_right_and_restores_fields(lines_window):
    w = lines_window
    page = w.lines_page
    right = page.right_scroll.geometry()
    count = len(w.fact_cards)
    page.set_schedule_expanded(True, animated=False)
    assert not page.detail.isVisible()
    assert page.schedule_panel.expanded
    assert page.schedule_panel.matrix.minimum_row_height == 24
    assert page.right_scroll.geometry() == right
    page.set_schedule_expanded(False, animated=False)
    assert page.detail.isVisible()
    assert len(w.fact_cards) == count == 9
    assert all(c.isVisible() for c in w.fact_cards)
    assert not page.schedule_panel.expanded
    desktop_app.QApplication.processEvents()
    assert page.right_scroll.verticalScrollBar().maximum() == 0

def test_fact_collapse_animation_reverses_from_current_height(lines_window, monkeypatch):
    from PySide6.QtTest import QTest
    from PySide6.QtCore import QAbstractAnimation
    monkeypatch.setattr('stats_motion.animations_enabled', lambda: True)
    page = lines_window.lines_page

    def sample_current(ms):
        animation = page.detail_motion.animation
        assert animation is not None
        animation.pause()
        animation.setCurrentTime(ms)
        desktop_app.QApplication.processEvents()

    def wait_completed():
        animation = page.detail_motion.animation
        if animation is not None:
            animation.resume()
        deadline = time.monotonic() + 3
        while page.detail_motion.animation is not None and time.monotonic() < deadline:
            QTest.qWait(10)
        assert page.detail_motion.animation is None

    page.motion.finish()
    original = page.detail.height()
    right = page.right_scroll.geometry()
    page.set_schedule_expanded(True)
    sample_current(90)
    assert page.detail_motion.animation is not None
    middle = page.detail.height()
    assert 0 < middle < original
    assert page.schedule_panel.height() > 458
    page.set_schedule_expanded(False)
    assert abs(page.detail.maximumHeight() - middle) <= 1
    wait_completed()
    assert not page.schedule_expanded and page.detail.isVisible()
    assert page.detail.height() == original
    assert page.right_scroll.geometry() == right
    assert all(card.isVisible() for card in lines_window.fact_cards)
    for state in (True, False, True):
        page.set_schedule_expanded(state)
        sample_current(35)
    wait_completed()
    assert page.schedule_expanded and not page.detail.isVisible()
    assert page.schedule_panel.expanded
    assert page.schedule_panel.matrix.minimum_row_height == 24
    page.set_schedule_expanded(False)
    sample_current(35)
    interrupted = page.detail_motion.animation
    lines_window.navigate(0)
    assert interrupted.state() == QAbstractAnimation.State.Stopped
    lines_window.navigate(1)
    QTest.qWait(350)
    assert not page.schedule_expanded and page.detail.isVisible()
    assert page.detail.height() == original, (page.detail.maximumHeight(),page.detail.sizeHint(),page.detail.minimumSizeHint(),page.schedule_panel.height(),page.schedule_panel.minimumHeight(),page.schedule_panel.matrix.columns,page.schedule_panel.summary_host.height(),page.right_host.size(),[(c.isVisible(),c.isHidden(),c.geometry()) for c in lines_window.fact_cards])
    assert page.detail_motion.animation is None
    assert page.schedule_panel.graphicsEffect() is None


def test_fluent_delegate_draws_core_counts_at_shared_body_size(lines_window):
    from PySide6.QtGui import QFontInfo, QFontMetrics
    from PySide6.QtWidgets import QStyleOptionViewItem
    from stats_tokens import FONT_FAMILY, FONT_SIZE_BODY
    table = lines_window.line_table
    for column in (2,8,9,7,10):
        index = table.model().index(0,column)
        option = QStyleOptionViewItem()
        option.initFrom(table)
        option.rect = table.visualRect(index)
        option.widget = table
        table.delegate.initStyleOption(option,index)
        assert option.font.pixelSize() == FONT_SIZE_BODY
        assert QFontInfo(option.font).family() == FONT_FAMILY
        if column == 8:
            assert option.rect.width() >= QFontMetrics(option.font).horizontalAdvance('200') + 12
    from qfluentwidgets import TableItemDelegate
    assert isinstance(table.delegate, TableItemDelegate)


def test_main_pages_do_not_show_bottom_status_area(lines_window, qt_application):
    # Returning to the line page must keep the shared content area available.
    window = lines_window
    for page_index in (0, 1, 2, 1, 0):
        window.navigate(page_index)
        qt_application.processEvents()
        from PySide6.QtWidgets import QStatusBar
        # QMainWindow.statusBar() creates a visible bar when none exists.
        assert not any(bar.isVisible() for bar in window.findChildren(QStatusBar))
        page = window.pages.currentWidget()
        from PySide6.QtCore import QPoint
        assert page.mapTo(window.content_host, QPoint(0, page.height())).y() == window.content_host.height(), \
            f'page {page_index} lost content height to a bottom status area'
    window.navigate(1)
    qt_application.processEvents()
    assert len(window.fact_cards) == 9
    assert window.lines_page.right_scroll.verticalScrollBar().maximum() == 0


def test_filter_and_field_controls_fit_text_and_reflow_without_losing_selection(lines_window, qt_application):
    from PySide6.QtTest import QTest
    w = lines_window
    p = w.lines_page
    key = w.selected_key
    assert p.fact_menu_button.width() >= p.fact_menu_button.sizeHint().width()
    assert p.line_columns_button.width() >= p.line_columns_button.sizeHint().width()
    assert p.line_mode.width() >= p.line_mode.sizeHint().width()
    assert p.line_company.width() > p.line_mode.width()
    assert p.line_company.y() == p.line_mode.y()
    controls = (p.line_company, p.line_mode, p.line_columns_button)
    assert all(not a.geometry().intersects(b.geometry()) for i, a in enumerate(controls) for b in controls[i+1:])
    w.resize(920, 680)
    QTest.qWait(100)
    assert p.line_company.y() < p.line_mode.y()
    assert p.line_mode.y() == p.line_columns_button.y()
    assert p.line_company.width() >= p.line_company.sizeHint().width()
    assert p.line_mode.width() >= p.line_mode.sizeHint().width()
    p.set_expanded(True, animated=False)
    QTest.qWait(100)
    assert p.line_company.y() == p.line_mode.y()
    p.set_expanded(False, animated=False)
    w.resize(1436, 906)
    QTest.qWait(100)
    assert p.line_company.y() == p.line_mode.y()
    assert p.fact_menu_button.width() >= p.fact_menu_button.sizeHint().width()
    assert w.selected_key == key and all(c.isVisible() for c in w.fact_cards)


@pytest.mark.parametrize('primary,size', [
    (('开线日期', '2013-04-01 08:10'), 18),
    (('线路车库', '八连交通集团有轨电车车库1'), 18),
    (('地图里程', '123.45 km'), 21),
])
def test_fact_emphasis_shapes_segoe_latin_and_existing_chinese(qt_application, primary, size):
    from PySide6.QtGui import QFont, QFontDatabase, QTextLayout
    from line_query_page import CompactFactCard
    from stats_style import initialize_theme
    from stats_tokens import FONT_FAMILY
    initialize_theme(qt_application)
    card = CompactFactCard(primary)
    card.resize(286, 86)
    card.show()
    qt_application.processEvents()
    try:
        font = card.value.font()
        assert font.pixelSize() == size and font.weight() == 600
        variable_available = any('Segoe UI Variable' in family for family in QFontDatabase.families())
        if variable_available:
            assert font.variableAxisValue(QFont.Tag('opsz')) == (36. if size >= 20 else 20.)
        else:
            assert not font.isVariableAxisSet(QFont.Tag('opsz'))
        for text, latin in [('0123456789E:/.,-km', True), ('线路车库次日班辆人次', False)]:
            layout = QTextLayout(text, font)
            layout.beginLayout()
            line = layout.createLine()
            line.setLineWidth(1000)
            layout.endLayout()
            runs = layout.glyphRuns()
            assert runs and all(run.glyphIndexes() for run in runs)
            for run in runs:
                actual = run.rawFont()
                assert actual.familyName().startswith('Segoe UI') if latin else actual.familyName() == FONT_FAMILY
                assert actual.weight() == 600
                if latin and variable_available:
                    assert actual.familyName().startswith('Segoe UI Variable')
                    assert len(actual.fontTable('fvar')) > 0, 'Latin silently used a static fallback'
        assert card.value.height() >= card.value.fontMetrics().height()
    finally:
        card.close()
        card.deleteLater()
        qt_application.processEvents()


def test_metric_unit_paint_has_shared_baseline_and_small_variable_font(qt_application):
    from PySide6.QtGui import QFont, QFontMetrics, QTextLayout
    from line_query_page import CompactFactCard
    from stats_style import initialize_theme
    from stats_tokens import TEXT_PRIMARY, TEXT_SECONDARY
    initialize_theme(qt_application)
    card = CompactFactCard(('地图里程', '888888 km'))
    card.resize(286, 86)
    card.show()
    qt_application.processEvents()
    try:
        value = card.value
        unit_font = value.unit_font()
        assert value.font().pixelSize() == 21 and unit_font.pixelSize() == 12
        assert unit_font.weight() == 600
        if unit_font.families()[0].startswith('Segoe UI Variable'):
            assert unit_font.variableAxisValue(QFont.Tag('opsz')) == 8.
        else:
            assert not unit_font.isVariableAxisSet(QFont.Tag('opsz'))
        layout = QTextLayout('km', unit_font)
        layout.beginLayout()
        line = layout.createLine()
        line.setLineWidth(200)
        layout.endLayout()
        assert all(run.rawFont().familyName().startswith('Segoe UI') for run in layout.glyphRuns())
        image = value.grab().toImage()
        scale = image.devicePixelRatio()
        number_width = QFontMetrics(value.font()).horizontalAdvance('888888')
        unit_left = number_width + 6
        bounds = []
        for left, right, color in [(0, number_width, TEXT_PRIMARY),
                                   (unit_left, value.width(), TEXT_SECONDARY)]:
            from PySide6.QtGui import QColor
            target = QColor(color)
            ink = [(x, y) for y in range(image.height())
                   for x in range(round(left * scale), min(image.width(), round(right * scale)))
                   if image.pixelColor(x, y).alpha() > 200
                   and max(abs(image.pixelColor(x, y).red() - target.red()),
                           abs(image.pixelColor(x, y).green() - target.green()),
                           abs(image.pixelColor(x, y).blue() - target.blue())) < 32]
            assert ink, 'metric or unit was not actually painted'
            bounds.append((min(y for _, y in ink), max(y for _, y in ink)))
        assert abs(bounds[0][1] - bounds[1][1]) <= max(1, round(scale)), bounds
        assert min(y for y, _ in bounds) > 0
        assert max(y for _, y in bounds) < image.height() - 1
    finally:
        card.close()
        card.deleteLater()
        qt_application.processEvents()


def test_fact_emphasis_records_static_segoe_fallback_when_variable_unavailable(qt_application, monkeypatch, caplog):
    import logging
    from PySide6.QtGui import QFont, QFontDatabase, QTextLayout
    import stats_typography as typography
    from line_query_page import CompactFactCard
    from stats_style import initialize_theme
    from stats_tokens import FONT_FAMILY
    initialize_theme(qt_application)
    available = [family for family in QFontDatabase.families() if 'Segoe UI Variable' not in family]
    original_load = typography._load_system_font
    saved = {key: qt_application.property(key) for key in
             ('statsVariableFontPrepared', 'statsVariableFontFallbackLogged')}
    monkeypatch.setattr(typography.QFontDatabase, 'families', lambda: available)
    monkeypatch.setattr(typography, '_load_system_font',
                        lambda filename: -1 if filename == 'SegUIVar.ttf' else original_load(filename))
    qt_application.setProperty('statsVariableFontPrepared', False)
    qt_application.setProperty('statsVariableFontFallbackLogged', False)
    card = None
    try:
        with caplog.at_level(logging.INFO, logger='stats_typography'):
            card = CompactFactCard(('地图里程', '123.45 km'))
            card.resize(286, 86)
            card.show()
            qt_application.processEvents()
            for _ in range(3):
                status = typography.typography_status()
        assert status['selected_family'] == 'Segoe UI' and status['fallback_used']
        assert sum('emphasis uses Segoe UI' in record.message for record in caplog.records) == 1
        assert card.value.font().pixelSize() == 21 and card.value.font().weight() == 600
        assert not card.value.font().isVariableAxisSet(QFont.Tag('opsz'))
        for text, expected in [('0123456789E:/.,-km', 'Segoe UI'), ('线路车库次日班辆人次', FONT_FAMILY)]:
            layout = QTextLayout(text, card.value.font())
            layout.beginLayout()
            line = layout.createLine()
            line.setLineWidth(1000)
            layout.endLayout()
            runs = layout.glyphRuns()
            assert runs and all(run.glyphIndexes() for run in runs)
            assert all(run.rawFont().familyName() == expected for run in runs)
            assert all(run.rawFont().weight() == 600 for run in runs)
            assert all(len(run.rawFont().fontTable('fvar')) == 0 for run in runs)
    finally:
        if card is not None:
            card.close()
            card.deleteLater()
        for key, value in saved.items():
            qt_application.setProperty(key, value)
        qt_application.processEvents()
