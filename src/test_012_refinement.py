"""User-visible corrections after the 0.1.2 candidate review."""
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget
from PySide6.QtTest import QTest
import pytest
from stats_motion import SurfaceMotion
from stats_controls import FluentSegmentedControl
from stats_charts import ChartPanel
from chart_canvas import ChartCanvas, ChartData, Series
from test_stats_charts import bucket, result


def test_monorail_display_is_consistent():
    from stats_text import group_label
    from display_rules import display_mode
    assert group_label('monorail') == '单轨'
    assert group_label('公交 · monorail') == '公交 · 单轨'
    assert display_mode('MonoRail') == '单轨'
    assert display_mode('单轨列车') == '单轨'


def test_zero_categories_default_hidden_and_manual_choice_survives_modes(qt_application):
    data = result({('a', 'bus'): [bucket(1, 0), bucket(2, 0)],
                   ('a', 'tram'): [bucket(1, 2), bucket(2, -2)],
                   ('a', 'metro'): [bucket(1, None)]})
    panel = ChartPanel('客流', default_mode='trend-bar')
    panel.set_result(data)
    assert panel.chart_views[0].hidden == {'bus'}
    assert not panel.legend_buttons['bus'].isChecked()
    assert panel.summary_values['a'] == 0
    assert [b.value for b in data.series[('a', 'bus')]] == [0, 0]
    panel.legend_buttons['bus'].click()
    panel.set_mode('bar'); panel.set_mode('trend-bar')
    assert 'bus' not in panel.chart_views[0].hidden
    assert panel.legend_buttons['bus'].isChecked()
    panel.close()


@pytest.mark.parametrize('kind', ['mouse', 'touch'])
def test_floating_visual_position_receives_first_press(qt_application, monkeypatch, kind):
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtWidgets import QPushButton
    from touch_input import install_touch_input
    monkeypatch.setattr('stats_motion.animations_enabled', lambda: True)
    install_touch_input(qt_application)
    host = QWidget(); host.resize(360, 260)
    surface = QWidget(host); surface.setGeometry(30, 40, 260, 170)
    button = QPushButton('点击', surface); button.setGeometry(30, 20, 160, 32)
    hits = []; button.clicked.connect(lambda: hits.append(True))
    host.show(); qt_application.processEvents()
    base = button.mapTo(host, button.rect().center())
    motion = SurfaceMotion(surface); motion.reveal(True); motion.animation.pause()
    offset = round(surface.graphicsEffect().offset)
    visual = base + QPoint(0, offset)
    # The visible entrance position must be the real input position too.
    if kind == 'mouse':
        QTest.mousePress(host.windowHandle(), Qt.MouseButton.LeftButton, pos=visual)
        QTest.qWait(280)
        QTest.mouseRelease(host.windowHandle(), Qt.MouseButton.LeftButton, pos=visual)
    else:
        device = QTest.createTouchDevice()
        QTest.touchEvent(host.windowHandle(), device).press(0, visual, host.windowHandle()).commit()
        QTest.qWait(280)
        QTest.touchEvent(host.windowHandle(), device).release(0, visual, host.windowHandle()).commit()
    qt_application.processEvents()
    assert hits == [True]
    assert not motion.running and surface.pos() == QPoint(30, 40)
    host.close()


@pytest.mark.parametrize('kind', ['mouse', 'touch'])
def test_floating_segmented_selection_uses_window_visual_coordinates(qt_application, monkeypatch, kind):
    from PySide6.QtCore import QPoint, Qt
    from touch_input import install_touch_input
    monkeypatch.setattr('stats_motion.animations_enabled', lambda: True)
    install_touch_input(qt_application)
    host = QWidget(); host.resize(400, 250)
    surface = QWidget(host); surface.setGeometry(20, 30, 350, 180)
    control = FluentSegmentedControl(surface, compact=True, subtle=False)
    control.addItem('structure', '制式分布'); control.addItem('ranking', '线路排行'); control.move(20, 20)
    signals = []; control.currentKeyChanged.connect(signals.append)
    host.show(); qt_application.processEvents()
    button = control._buttons['ranking']; base = button.mapTo(host, button.rect().center())
    motion = SurfaceMotion(surface); motion.reveal(True); motion.animation.pause(); motion.animation.setCurrentTime(10)
    visual = base + QPoint(0, round(surface.graphicsEffect().offset))
    if kind == 'mouse': QTest.mouseClick(host.windowHandle(), Qt.MouseButton.LeftButton, pos=visual)
    else:
        device = QTest.createTouchDevice()
        QTest.touchEvent(host.windowHandle(), device).press(0, visual, host.windowHandle()).commit()
        QTest.touchEvent(host.windowHandle(), device).release(0, visual, host.windowHandle()).commit()
    qt_application.processEvents()
    assert control.currentKey() == 'ranking' and signals == ['ranking']
    assert not motion.running
    host.close()


def test_floating_native_slider_touch_drag_keeps_native_values(qt_application, monkeypatch):
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtWidgets import QSlider
    from touch_input import install_touch_input
    monkeypatch.setattr('stats_motion.animations_enabled', lambda: True)
    install_touch_input(qt_application)
    host = QWidget(); host.resize(400, 250)
    surface = QWidget(host); surface.setGeometry(20, 30, 350, 180)
    slider = QSlider(Qt.Orientation.Horizontal, surface); slider.setGeometry(20, 20, 260, 32); slider.setValue(50)
    host.show(); qt_application.processEvents()
    base = slider.mapTo(host, slider.rect().center())
    motion = SurfaceMotion(surface); motion.reveal(True); motion.animation.pause()
    visual = base + QPoint(0, round(surface.graphicsEffect().offset)); device = QTest.createTouchDevice()
    QTest.touchEvent(host.windowHandle(), device).press(0, visual, host.windowHandle()).commit()
    QTest.touchEvent(host.windowHandle(), device).move(0, visual + QPoint(70, 0), host.windowHandle()).commit()
    QTest.touchEvent(host.windowHandle(), device).release(0, visual + QPoint(70, 0), host.windowHandle()).commit()
    qt_application.processEvents()
    assert slider.value() > 50 and not slider.isSliderDown()
    assert not motion.running
    host.close()


@pytest.mark.parametrize('kind', ['mouse', 'touch'])
def test_floating_bottom_control_accepts_visible_click_outside_old_bounds(qt_application, monkeypatch, kind):
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtWidgets import QPushButton
    from touch_input import install_touch_input
    monkeypatch.setattr('stats_motion.animations_enabled', lambda: True)
    install_touch_input(qt_application)
    host = QWidget(); host.resize(360, 260)
    surface = QWidget(host); surface.setGeometry(20, 20, 300, 160)
    button = QPushButton('底部动作', surface); button.setGeometry(30, 130, 140, 28)
    hits = []; button.clicked.connect(lambda: hits.append(True))
    host.show(); qt_application.processEvents(); base = button.mapTo(host, button.rect().center())
    motion = SurfaceMotion(surface); motion.reveal(True); motion.animation.pause()
    visual = base + QPoint(0, round(surface.graphicsEffect().offset))
    assert not surface.geometry().contains(visual)
    if kind == 'mouse': QTest.mouseClick(host.windowHandle(), Qt.MouseButton.LeftButton, pos=visual)
    else:
        device = QTest.createTouchDevice()
        QTest.touchEvent(host.windowHandle(), device).press(0, visual, host.windowHandle()).commit()
        QTest.touchEvent(host.windowHandle(), device).release(0, visual, host.windowHandle()).commit()
    qt_application.processEvents()
    assert hits == [True] and not motion.running
    host.close()


def test_floating_hit_mapping_respects_covering_sibling(qt_application, monkeypatch):
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtWidgets import QPushButton
    monkeypatch.setattr('stats_motion.animations_enabled', lambda: True)
    host = QWidget(); host.resize(360, 260)
    surface = QWidget(host); surface.setGeometry(20, 20, 300, 160)
    button = QPushButton('底部动作', surface); button.setGeometry(30, 130, 140, 28)
    cover = QPushButton('覆盖层', host); cover.setGeometry(40, 180, 180, 40)
    hits = []; button.clicked.connect(lambda: hits.append('source')); cover.clicked.connect(lambda: hits.append('cover'))
    host.show(); qt_application.processEvents(); motion = SurfaceMotion(surface); motion.reveal(True); motion.animation.pause()
    visual = button.mapTo(host, button.rect().center()) + QPoint(0, round(surface.graphicsEffect().offset))
    QTest.mouseClick(host.windowHandle(), Qt.MouseButton.LeftButton, pos=visual)
    qt_application.processEvents()
    assert hits == ['cover']
    host.close()


def test_floating_canvas_mouse_uses_native_window_without_changing_data_window(qt_application, monkeypatch):
    import sys
    errors = []
    monkeypatch.setattr(sys, 'excepthook', lambda *error: errors.append(error))
    from PySide6.QtCore import QPoint, Qt
    monkeypatch.setattr('stats_motion.animations_enabled', lambda: True)
    host = QWidget(); host.resize(400, 260)
    surface = QWidget(host); surface.setGeometry(20, 20, 350, 200)
    canvas = ChartCanvas(surface); canvas.setMinimumHeight(0); canvas.setGeometry(0, 0, 350, 180)
    canvas.set_data(ChartData('line', ['甲', '乙'], [Series('s', '系列', QColor('blue'), [1, 2])]))
    host.show(); qt_application.processEvents(); data_window = canvas.window()
    motion = SurfaceMotion(surface); motion.reveal(True); motion.animation.pause()
    visual = canvas.mapTo(host, canvas.rect().center()) + QPoint(0, round(surface.graphicsEffect().offset))
    QTest.mouseClick(host.windowHandle(), Qt.MouseButton.LeftButton, pos=visual)
    qt_application.processEvents()
    assert canvas.window() == data_window and not motion.running
    host.close()
    qt_application.processEvents()
    assert not errors


def test_hiding_floating_surface_cancels_pressed_button_and_next_click_works(qt_application, monkeypatch):
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtWidgets import QPushButton
    monkeypatch.setattr('stats_motion.animations_enabled', lambda: True)
    host = QWidget(); host.resize(360, 260)
    surface = QWidget(host); surface.setGeometry(30, 40, 260, 170)
    button = QPushButton('点击', surface); button.setGeometry(30, 20, 160, 32)
    hits = []; button.clicked.connect(lambda: hits.append(True))
    host.show(); qt_application.processEvents(); base = button.mapTo(host, button.rect().center())
    motion = SurfaceMotion(surface); motion.reveal(True); motion.animation.pause()
    visual = base + QPoint(0, round(surface.graphicsEffect().offset))
    QTest.mousePress(host.windowHandle(), Qt.MouseButton.LeftButton, pos=visual)
    assert button.isDown()
    surface.hide(); QTest.mouseRelease(host.windowHandle(), Qt.MouseButton.LeftButton, pos=visual)
    assert not button.isDown() and hits == [] and not motion.running
    surface.show(); qt_application.processEvents()
    QTest.mouseClick(host.windowHandle(), Qt.MouseButton.LeftButton, pos=base)
    assert hits == [True]
    host.close()


def test_comparison_nonzero_prevents_default_zero_hiding(qt_application):
    from datetime import datetime
    data = result({('a', 'bus'): [bucket(1, 0)]}, comparison={('a', 'bus'): [bucket(1, 4)]},
                  comparison_window=(datetime(2024,1,1),datetime(2024,1,3)))
    panel=ChartPanel('客流',default_mode='trend-bar');panel.set_result(data)
    assert 'bus' not in panel.chart_views[0].hidden
    panel.close()


def test_zero_time_bar_has_no_glyph_hit_or_numeric_label(qt_application):
    canvas=ChartCanvas(detailed=True);canvas.resize(500,300)
    data=ChartData('bar',['零','非零'],[Series('a','客流',QColor('#1677ff'),[0,8])])
    canvas.set_data(data);canvas.show();qt_application.processEvents();canvas.grab()
    assert not any(index == 0 for index,stack,path in canvas._bar_hits)
    assert any(index == 1 for index,stack,path in canvas._bar_hits)
    assert canvas.data.series[0].values == [0,8]
    canvas.close()


def test_chart_canvas_is_reused_across_type_changes(qt_application):
    panel=ChartPanel('客流');panel.set_result(result({('a','bus'):[bucket(1,8)]}))
    original=panel.chart_views[0]
    for mode in ('bar','pie','line'):
        panel.set_mode(mode)
        assert panel.chart_views[0] is original
    panel.close()


def test_float_has_visible_travel_without_repainting_unchanged_content(qt_application,monkeypatch):
    monkeypatch.setattr('stats_motion.animations_enabled',lambda:True)
    class Painted(QWidget):
        paints=0
        def paintEvent(self,event):
            self.paints+=1
            p=QPainter(self);p.fillRect(self.rect(),QColor('white'))
    host=QWidget();host.resize(320,220);child=Painted(host);child.setGeometry(30,30,240,140)
    canvas=ChartCanvas(child);canvas.setMinimumHeight(0);canvas.setGeometry(10,10,220,120)
    canvas.set_data(ChartData('line',['甲','乙'],[Series('s','客流',QColor('blue'),[1,2])]))
    host.show();qt_application.processEvents();motion=SurfaceMotion(child);motion.reveal(True)
    assert child.graphicsEffect().offset >= 20
    qt_application.processEvents();first=child.paints
    QTest.qWait(90)
    assert child.paints-first <= 1
    child.update();qt_application.processEvents();host.grab()
    assert child.paints > first
    canvas.set_data(ChartData('line',['甲','乙'],[Series('s','客流',QColor('blue'),[8,13])]))
    qt_application.processEvents();host.grab()
    assert child.paints > first
    assert not motion.running and canvas.data.series[0].values == [8,13]
    motion.finish();host.close()


def test_selected_fill_moves_continuously_and_does_not_fade_text(qt_application,monkeypatch):
    monkeypatch.setattr('stats_motion.animations_enabled',lambda:True)
    control=FluentSegmentedControl();control.addItem('a','条形图');control.addItem('b','折线图');control.addItem('c','饼图')
    control.show();qt_application.processEvents();before=control.grab().toImage()
    control.setCurrentKey('c');control._animation.setCurrentTime(45)
    middle=control.grab().toImage()
    assert control._buttons['c'].graphicsEffect() is None
    assert before != middle
    control._animation.setCurrentTime(167);after=control.grab().toImage()
    assert middle != after
    assert control.currentKey() == 'c' and control._buttons['c'].isChecked()
    control.close()


def test_home_wide_small_height_difference_does_not_scroll(qt_application,monkeypatch):
    monkeypatch.setenv('CIM2_REDUCED_MOTION','1')
    from latest_info_page import LatestInfoPage
    from test_latest_info_page import snapshot, session
    page=LatestInfoPage();page.resize(1340,816);page.set_session(session());data=snapshot();page.set_snapshot(data);page.show()
    assert page._snapshot is data
    qt_application.processEvents();qt_application.processEvents()
    page.resize(1340,page.board.minimumSizeHint().height()-3)
    qt_application.processEvents();qt_application.processEvents()
    assert page.scroll.horizontalScrollBar().maximum() == 0
    assert page.scroll.verticalScrollBar().maximum() == 0
    page.passengers.show_ranking();qt_application.processEvents();qt_application.processEvents()
    assert page.scroll.verticalScrollBar().maximum() == 0
    page.passengers.show_structure();qt_application.processEvents();qt_application.processEvents()
    assert page.scroll.verticalScrollBar().maximum() == 0
    page.resize(864,576);qt_application.processEvents()
    assert page.scroll.verticalScrollBar().maximum() > 0
    page.close()


def test_home_ranking_rows_are_not_compressed_below_content(qt_application, monkeypatch):
    monkeypatch.setenv('CIM2_REDUCED_MOTION', '1')
    from latest_info_page import LatestInfoPage
    from test_latest_info_page import snapshot, session
    page = LatestInfoPage(); page.resize(1340, 816)
    page.set_session(session()); page.set_snapshot(snapshot()); page.show()
    page.passengers.show_ranking(); qt_application.processEvents(); qt_application.processEvents()
    page.resize(1340, page.board.minimumSizeHint().height() - 24)
    qt_application.processEvents(); qt_application.processEvents()
    rows = page.passengers._ranking_widgets
    assert page.passengers.ranking.height() >= page.passengers.ranking.minimumSizeHint().height()
    assert all(a.geometry().bottom() < b.y() for a, b in zip(rows, rows[1:]))
    assert rows[-1].geometry().bottom() < page.passengers.ranking.height()
    page.close()


@pytest.mark.parametrize('analysis, owners, restored', [('companies', ('a', 'b'), 'a'),
                                                     ('period', ('a',), 'current')])
def test_network_group_restore_survives_zero_distribution(qt_application, analysis, owners, restored):
    from test_network_charts import make_result, descriptor, snapshot, endpoint_result
    from network_charts import NetworkChartPanel
    from dataclasses import replace
    data = make_result(metric='linecount', companies=owners, groups=('总计',), comparison=analysis == 'period')
    for values in (data.series, data.comparison):
        for key, buckets in list(values.items()): values[key] = [replace(b, value=0) for b in buckets]
    panel = NetworkChartPanel()
    panel.set_descriptor(descriptor(data, key='linecount', allowed=('line', 'bar'), bar_result=endpoint_result(data)), snapshot(analysis))
    panel.legend_buttons[restored].click(); panel.set_mode('bar')
    assert panel.chart_views[0].data.labels == ['总计']
    assert restored in {s.key for s in panel.chart_views[0].visible_series()}
    assert len(panel.chart_views[0].visible_series()) == 1
    panel.set_mode('line'); assert panel.legend_buttons[restored].isChecked()
    panel.close()


def test_network_comparison_nonzero_keeps_current_zero_identity(qt_application):
    from test_network_charts import make_result, descriptor, snapshot
    from network_charts import NetworkChartPanel
    from dataclasses import replace
    data=make_result(companies=('a',),groups=('bus',),comparison=True)
    data.series={key:[replace(b,value=0) for b in buckets] for key,buckets in data.series.items()}
    panel=NetworkChartPanel();panel.set_descriptor(descriptor(data),snapshot('period'))
    assert {'current','comparison'} <= {s.key for s in panel.chart_views[0].visible_series()}
    panel.close()


def test_company_total_restore_survives_distribution_mode(qt_application):
    panel=ChartPanel('总计',default_mode='line')
    panel.set_result(result({('a','总计'):[bucket(1,0)],('b','总计'):[bucket(1,0)]}))
    panel.legend_buttons['a'].click();panel.set_mode('bar')
    assert panel.chart_views[0].data.labels == ['总计']
    assert panel.chart_views[1].data.labels == []
    panel.set_mode('line');assert panel.legend_buttons['a'].isChecked()
    assert not panel.legend_buttons['b'].isChecked()
    panel.close()


@pytest.mark.parametrize('input_kind',['mouse','touch','keyboard'])
def test_repeated_input_during_entrance_is_delivered_once(qt_application,monkeypatch,input_kind):
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtWidgets import QPushButton,QVBoxLayout,QApplication
    from touch_input import install_touch_input
    monkeypatch.setattr('stats_motion.animations_enabled',lambda:True)
    install_touch_input(qt_application)
    host=QWidget();host.resize(320,180);layout=QVBoxLayout(host);button=QPushButton('切换');layout.addWidget(button)
    hits=[];button.clicked.connect(lambda:hits.append(True))
    host.show();qt_application.processEvents();motion=SurfaceMotion(host)
    device=QTest.createTouchDevice() if input_kind=='touch' else None
    for index in range(20):
        motion.reveal(False)
        if input_kind=='mouse': QTest.mouseClick(button,Qt.MouseButton.LeftButton)
        elif input_kind=='keyboard':
            button.setFocus();QTest.keyClick(button,Qt.Key.Key_Space)
        else:
            events=QTest.touchEvent(button,device)
            events.press(0,button.rect().center(),button).commit()
            events.release(0,button.rect().center(),button).commit()
        qt_application.processEvents()
        assert len(hits)==index+1
        assert not motion.running and host.graphicsEffect() is None
        assert QApplication.activeModalWidget() is None
    host.close()


def test_network_single_category_restore_survives_mode_aliases(qt_application):
    from test_network_charts import make_result, descriptor, snapshot, endpoint_result
    from network_charts import NetworkChartPanel
    from dataclasses import replace
    data=make_result(metric='linecount',companies=('a',),groups=('总计',))
    data.series={key:[replace(b,value=0) for b in buckets] for key,buckets in data.series.items()}
    panel=NetworkChartPanel();panel.set_descriptor(descriptor(data,key='linecount',allowed=('line','bar'),bar_result=endpoint_result(data)),snapshot('overall'))
    assert not panel.legend_buttons['a'].isChecked()
    panel.legend_buttons['a'].click();panel.set_mode('bar')
    assert panel.chart_views[0].data.labels == ['总计']
    panel.set_mode('line')
    assert panel.legend_buttons['a'].isChecked()
    panel.close()
