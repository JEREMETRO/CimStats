from dataclasses import replace
from math import cos, sin, radians
from test_latest_info_page import page, snapshot, session
from test_latest_info_alerts import gui_panel, gui_snapshot, gui_application


def test_full_label_resizes_and_respects_explicit_business_tip(qt_application):
    from latest_info_charts import FullLabel
    label = FullLabel('完整文字')
    label.resize(200, 30); label.show(); qt_application.processEvents()
    assert label.toolTip() == ''
    label.resize(10, 30); qt_application.processEvents()
    assert label.toolTip() == label.text()
    label.resize(200, 30); qt_application.processEvents()
    assert label.toolTip() == ''
    label.setToolTip('业务说明'); label.setText('新内容')
    label.resize(5, 30); qt_application.processEvents()
    assert label.toolTip() == '业务说明'
    label.setToolTip(''); label.setText('城市名称永不提示')
    label.resize(3, 10); qt_application.processEvents()
    assert label.toolTip() == ''
    label.close()


def test_full_label_font_height_and_original_name(qt_application):
    from latest_info_charts import FullLabel
    label = FullLabel('101路'); label.resize(200, 30); label.show()
    label.set_full_text('101路·始发站至终点站'); qt_application.processEvents()
    assert label.toolTip() == '101路·始发站至终点站'
    label.set_full_text('101路')
    font = label.font(); font.setPixelSize(80); label.setFont(font)
    qt_application.processEvents()
    assert label.toolTip() == '101路'
    label.close()


def test_home_entries_keep_clicks_without_repeated_tips(page, qt_application):
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    page.set_session(session()); page.set_snapshot(snapshot())
    panel = page.passengers
    assert panel.mode_combo.toolTip() == ''
    assert all(row.toolTip() == '' for row in panel.visible_mode_rows())
    panel.ranking_button.click(); qt_application.processEvents()
    assert panel.ranking_button.toolTip() == ''
    assert snapshot().lines[0].name in panel.visible_ranking_rows()[0].name.toolTip()
    assert '公司：' not in panel.visible_ranking_rows()[0].name.toolTip()
    panel.share_button.click(); qt_application.processEvents()
    assert panel.share_button.toolTip() == ''
    ring = panel.share_ring
    def move(point):
        event = QMouseEvent(QEvent.Type.MouseMove, point, point, Qt.MouseButton.NoButton,
                            Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
        qt_application.sendEvent(ring, event)
    move(QPointF(1, 1)); assert ring.toolTip() == ''
    start, end, key, value = ring.sectors()[0]
    center, radius = ring.geometry_for_hit(); angle = radians((start+end)/2-90)
    move(QPointF(center.x()+cos(angle)*radius*.9, center.y()+sin(angle)*radius*.9))
    assert snapshot().lines[0].name in ring.toolTip()
    assert '人次' in ring.toolTip() and '%' in ring.toolTip()
    move(center); assert ring.toolTip() == ''


def test_alert_rows_do_not_expose_parent_tip_on_actions(gui_panel):
    from PySide6.QtWidgets import QPushButton
    panel, settings, application = gui_panel
    panel.set_snapshot(gui_snapshot(), 'save-a', {'p1': '公司'})
    assert panel.more_button.toolTip() == ''
    alert = panel.alerts[0]
    row = panel._row(alert, panel, expanded=True)
    assert row.toolTip() == '' and alert.reason in row.accessibleName()
    assert all(button.toolTip() == '' for button in row.findChildren(QPushButton))


def test_duplicate_route_identity_only_when_needed(page, qt_application):
    from latest_info_model import ModeCount
    data = snapshot()
    first = replace(data.lines[0], name='101路', passengers=8)
    second = replace(first, key='other-company', company_id='company-b', passengers=4)
    data = replace(data, lines=(first, second), passenger_top10=(first, second), passenger_modes=(ModeCount(first.mode, 12),))
    page.set_session(session()); page.set_snapshot(data)
    page.passengers.show_ranking(); qt_application.processEvents()
    assert all('公司标识：' in row.name.toolTip() for row in page.passengers.visible_ranking_rows())
    page.passengers.show_line_share(); qt_application.processEvents()
    assert all('公司标识：' in row.name.toolTip() for row in page.passengers.visible_share_rows())
    assert 'company-b' in page.passengers.share_ring.display_labels[second.key]

def test_alert_labels_accept_hover_without_losing_row_click(gui_panel):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QLabel
    panel, settings, application = gui_panel
    panel.set_snapshot(gui_snapshot(), 'save-a', {'p1': '很长的公司名称'})
    row = panel._row(panel.alerts[0], panel)
    labels = row.findChildren(QLabel)
    assert all(not item.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents) for item in labels)
    assert row.findChild(QLabel, 'alertNeutralMarker').toolTip() == '未读'
