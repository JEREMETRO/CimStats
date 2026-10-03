"""Polished Fluent content and common homepage edges, not widget bounds alone."""
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'frontend'))
from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QStyle, QStyleOptionButton
from frontend.latest_info_alerts import LatestInfoAlertsPanel
from latest_info_page import LatestInfoPage
from statistics_page import StatisticsPage


@pytest.fixture(autouse=True)
def themed_application(qt_application):
    from stats_style import initialize_theme
    initialize_theme(qt_application)


def button_text_bounds(button):
    button.ensurePolished()
    option = QStyleOptionButton()
    button.initStyleOption(option)
    contents = button.style().subElementRect(QStyle.SubElement.SE_PushButtonContents, option, button)
    ink = option.fontMetrics.boundingRect(contents, int(Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextSingleLine), button.text())
    return contents, ink


@pytest.mark.parametrize('name', ['all_button', 'more_button', 'company_button'])
def test_button_complete_text_fits_polished_contents(qt_application, name):
    owner = StatisticsPage() if name == 'company_button' else LatestInfoAlertsPanel()
    owner.resize(912, 680) if name == 'company_button' else owner.resize(260, 494)
    owner.show()
    for _ in range(8): qt_application.processEvents()
    try:
        button = getattr(owner, name)
        contents, ink = button_text_bounds(button)
        assert contents.contains(ink), (button.text(), contents, ink, button.font().pixelSize())
    finally:
        owner.close()


@pytest.mark.parametrize('width', [912, 1200, 1440])
def test_alert_card_uses_same_upper_edges_as_home_columns(qt_application, width):
    page = LatestInfoPage()
    panel = LatestInfoAlertsPanel()
    page.set_alert_panel(panel)
    page.resize(width, 852)
    page.show()
    for _ in range(12): qt_application.processEvents()
    try:
        host_rect = page.alert_host.rect()
        assert panel.mapTo(page.alert_host, QPoint()) == host_rect.topLeft()
        assert panel.size() == host_rect.size()
        if width >= 1180:
            assert page.alert_host.mapTo(page.board, QPoint()).y() == page.city.mapTo(page.board, QPoint()).y()
            assert page.alert_host.height() == page.main.height()
        else:
            assert page.alert_host.mapTo(page.board, QPoint()).x() == page.city.mapTo(page.board, QPoint()).x()
            assert page.alert_host.width() == page.city.width()
    finally:
        page.close()


def test_home_city_caption_and_value_rows_have_common_baselines(qt_application):
    page = LatestInfoPage()
    page.resize(912, 680)
    page.show()
    for _ in range(8): qt_application.processEvents()
    try:
        # Natural label heights must not center each value at a different y.
        assert page.city_fields[1].rect().contains(page.city_date.geometry())
        for widget in (page.city_clock, page.city_name, page.city_save):
            assert widget.height() >= widget.fontMetrics().height()
            ink = widget.fontMetrics().boundingRect(widget.contentsRect(), int(widget.alignment()), widget.text())
            assert widget.contentsRect().contains(ink)
        def baseline(label):
            if getattr(label, 'visual_center', None) is not None:
                return label.mapTo(page.city, QPoint()).y() + label.visual_center - label.glyph_center(label.text())
            ink = label.fontMetrics().boundingRect(label.contentsRect(), int(label.alignment()), label.text())
            return label.mapTo(page.city, QPoint()).y() + ink.y() + label.fontMetrics().ascent()
        assert baseline(page.city_name) == baseline(page.city_clock)
        assert page.city_date.visual_center == page.city_clock.visual_center
        assert page.city_date.y() == page.city_clock.y()
        def pixel_center(label):
            image = label.grab().toImage()
            rows = [y for y in range(image.height()) for x in range(image.width())
                    if image.pixelColor(x, y).alpha() > 100
                    and image.pixelColor(x, y).red() < 130
                    and image.pixelColor(x, y).green() < 150]
            assert rows, label.text()
            return (min(rows) + max(rows) + 1) / 2
        assert abs(pixel_center(page.city_date) - pixel_center(page.city_clock)) <= 1
        assert baseline(page.city_population) == baseline(page.city_save)
        assert page.city_date.geometry().right() < page.city_clock.x()
        assert page.city_clock.geometry().right() == page.city_fields[1].width() - 1
        assert page.city_save.alignment() & Qt.AlignmentFlag.AlignRight
    finally:
        page.close()
