"""Task 3: repeated menu updates and constrained responsive controls."""
import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QPoint, QRect, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QLabel
from qfluentwidgets import FluentIcon


def settle(app):
    for _ in range(8):
        app.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def inside(parent, child):
    return parent.rect().contains(QRect(child.mapTo(parent, QPoint()), child.size()))


def dispose(widget, app):
    widget.close()
    widget.deleteLater()
    settle(app)


def test_export_rebuild_has_only_current_rows_and_stable_height(qt_application):
    from app_shell import AppHeader
    header = AppHeader()
    header.set_page('最新信息', FluentIcon.HOME)
    items = [('report', '首页报告 XLSX', FluentIcon.DOCUMENT, True),
             (None, '', None, False), ('png', '首页图片 PNG', FluentIcon.PHOTO, True),
             ('unavailable', '公司工作簿 XLSX', None, False)]
    emitted = []
    header.export_requested.connect(emitted.append)
    for _ in range(40):
        header.set_exports(items)
        settle(qt_application)
        assert header.export_menu.view.count() == 4
        assert len(header.export_menu.actions()) == 3
        assert header.export_menu.height() < 200
        assert len([a for a in header.export_menu.findChildren(QAction) if a.text()]) == 3
    header.export_actions['png'].trigger()
    assert emitted == ['png']
    header.set_exports([('report', '报告', None, True)])
    assert header.export_menu.view.count() == 1
    dispose(header, qt_application)


def test_export_normalizes_empty_and_repeated_separators(qt_application):
    from app_shell import AppHeader
    header = AppHeader()
    sep = (None, '', None, False)
    header.set_exports([sep, ('a', 'A', None, True), sep, sep, ('b', 'B', None, False), sep])
    assert header.export_menu.view.count() == 3
    header.set_exports([sep, sep])
    assert header.export_menu.view.count() == 0
    assert not header.export_button.isEnabled()
    dispose(header, qt_application)


def test_rebuilt_export_menu_keeps_keyboard_navigation_and_activation(qt_application):
    from app_shell import AppHeader
    from PySide6.QtTest import QTest
    header = AppHeader()
    for _ in range(5):
        header.set_exports([('first', '报告', None, True), (None, '', None, False),
                            ('second', '图片', None, True), ('disabled', '工作簿', None, False)])
    emitted = []
    header.export_requested.connect(emitted.append)
    header.export_menu.exec(QPoint(100, 100), ani=False)
    view = header.export_menu.view
    view.setFocus()
    view.setCurrentRow(0)
    QTest.keyClick(view, Qt.Key.Key_Down)
    assert view.currentRow() == 2
    QTest.keyClick(view, Qt.Key.Key_Return)
    assert emitted == ['second']
    dispose(header, qt_application)


def test_home_company_selection_works_with_keyboard(qt_application):
    from stats_controls import ElidingComboBox
    from PySide6.QtTest import QTest
    combo = ElidingComboBox()
    combo.addItem('公司甲', userData='a')
    combo.addItem('公司乙', userData='b')
    combo.show()
    combo.setFocus()
    QTest.keyClick(combo, Qt.Key.Key_Space)
    assert combo.dropMenu is not None and combo.dropMenu.isVisible()
    combo.dropMenu.view.setCurrentRow(1)
    QTest.keyClick(combo.dropMenu.view, Qt.Key.Key_Return)
    assert combo.currentData() == 'b'
    dispose(combo, qt_application)


def test_medium_numeric_font_resolves_to_a_lighter_face_than_large(qt_application):
    from PySide6.QtGui import QFontDatabase, QFontInfo
    from stats_typography import numeric_font
    medium = QFontInfo(numeric_font(20))
    large = QFontInfo(numeric_font(24, large=True))
    if not any('Segoe UI' in family for family in QFontDatabase.families()):
        pytest.skip('Windows Segoe family unavailable')
    assert 400 < int(medium.weight()) < int(large.weight())


@pytest.mark.parametrize('width', [912, 680, 580])
def test_header_controls_fit_constrained_width(qt_application, width):
    from app_shell import AppHeader
    header = AppHeader()
    header.set_page('最新信息', FluentIcon.HOME)
    header.resize(width, 64)
    header.show()
    settle(qt_application)
    assert header.width() == width
    widgets = [header.icon_base, header.title, header.save_chip, header.export_button, header.open_button]
    for widget in widgets:
        assert inside(header, widget)
    for left, right in zip(widgets, widgets[1:]):
        assert left.geometry().right() < right.geometry().left()
    dispose(header, qt_application)


def test_home_long_company_retains_identity_and_elides_with_arrow_budget(qt_application):
    from latest_info_page import LatestInfoPage
    page = LatestInfoPage()
    page.resize(864, 608)
    page.show()
    name = '滨海市公共交通运营管理集团及城市轨道交通有限公司'
    page._populate_scopes((('long-id', name),), ('综合', '有轨电车'))
    page.company_combo.setCurrentIndex(1)
    settle(qt_application)
    combo = page.company_combo
    assert combo.currentText() == name and combo.currentData() == 'long-id'
    assert '…' in combo.text()
    assert combo.fontMetrics().horizontalAdvance(combo.text()) <= combo.width() - 40
    assert inside(page.scope_host, combo) and inside(page.scope_host, page.mode_combo)
    assert combo.geometry().right() < page.mode_combo.geometry().left()
    dispose(page, qt_application)


@pytest.mark.parametrize('width', [1204, 864])
def test_long_selected_company_tags_do_not_expand_or_clip_selector(qt_application, width):
    from statistics_page import StatisticsPage
    page = StatisticsPage()
    names = ['滨海市公共交通运营管理集团及城市轨道交通有限公司'+str(i) for i in range(3)]
    for i, name in enumerate(names):
        action = QAction(name, page.company_menu)
        action.setData(str(i)); action.setCheckable(True); action.setChecked(True)
        action.toggled.connect(page._refresh_company_tags)
        page.company_menu.addAction(action)
    page._refresh_company_tags()
    page.resize(width, 566)
    page.show()
    settle(qt_application)
    assert page.width() == width
    assert inside(page.company_selector, page.company_button)
    for tag in page.company_tags.values():
        assert inside(page.company_tag_host, tag)
        assert inside(tag, tag.close_button)
        assert inside(tag, tag.name_label)
        assert tag.name_label.toolTip() == ''
        assert tag.name_label.accessibleName() in names
        assert tag.name_label.fontMetrics().horizontalAdvance(QLabel.text(tag.name_label)) <= tag.name_label.width()
        assert tag.close_button.text() == '' and not tag.close_button.icon().isNull()
    page.company_tags['0'].close_button.click()
    assert page.selected_companies() == ('1', '2')
    dispose(page, qt_application)
