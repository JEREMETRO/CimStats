"""Approved compact filter summary wording and date boundaries."""
from datetime import datetime
from PySide6.QtWidgets import QApplication
from statistics_page import StatisticsPage


def test_approved_summary_keeps_labels_and_actual_comparison_dates():
    app = QApplication.instance() or QApplication([])
    page = StatisticsPage()
    page._range_window = (datetime(2013,5,13),datetime(2013,5,20))
    page._update_compact_filter_summary()
    text = page.compact_filter_summary.text()
    assert '公司：' in text and '图表模式：默认模式' in text
    assert '统计时间：2013-05-13—05-19' in text and '按日' in text
    assert '本期' not in text and '对象' not in text
    page.analysis_mode_control.setCurrentKey('period')
    page._update_compact_filter_summary()
    text = page.compact_filter_summary.text()
    assert '图表模式：同期对比' in text and '对比时间：2013-05-06—05-12' in text
    page.tab_bar.setCurrentItem('city')
    assert '公司：' not in page.compact_filter_summary.text()
    assert '统计时间：' in page.compact_filter_summary.text()
    page.close()


def test_summary_only_elides_company_before_essential_fields():
    from filter_summary import CompactFilterSummary
    app = QApplication.instance() or QApplication([])
    widget = CompactFilterSummary()
    widget.set_summary('公司：非常长的真实公司名称', ['图表模式：默认模式','统计时间：2013-05-13—05-19','按日'])
    widget.resize(480,30); widget.show(); app.processEvents()
    assert '\n' not in widget.visible_text
    assert '统计时间：2013-05-13—05-19' in widget.visible_text
    assert '图表模式：默认模式' in widget.visible_text
    widget.resize(1000,30);app.processEvents()
    assert widget.toolTip()==''
    widget.close()


def test_custom_hour_range_keeps_exclusive_end_and_cross_year_dates():
    from filter_summary import summary_window
    assert summary_window((datetime(2013,12,30),datetime(2014,1,2)))=='2013-12-30—2014-01-01'
    assert summary_window((datetime(2013,5,13,8),datetime(2013,5,13,10)))=='2013-05-13 08:00—10:00（结束不含）'


def test_network_never_adds_baseline_header_even_when_comparison_is_available(tmp_path, monkeypatch):
    from dataclasses import replace
    from card_comparisons import CardComparison
    from test_network_dashboard import _fixture, _view
    from PySide6.QtWidgets import QLabel
    for mode in ('overall', 'period'):
        snapshot = _fixture(mode)
        summary = snapshot.summaries[0]
        summary = replace(summary, values=(replace(summary.values[0],
            comparison=CardComparison(text='较上周 +1%', available=True)), *summary.values[1:]))
        snapshot = replace(snapshot, summaries=(summary, *snapshot.summaries[1:]))
        view, _ = _view(snapshot, tmp_path, monkeypatch)
        assert not hasattr(view.summary_cards[0], 'baseline_context')
        assert not any('卡片基准' in label.text() for label in view.findChildren(QLabel))
        view.close()


def test_company_and_city_headers_do_not_add_internal_baseline_information():
    from PySide6.QtWidgets import QLabel
    from test_stats_fluent_page import _loaded_page
    from city_dashboard import CityDashboard
    from test_city_model import build, r
    page = _loaded_page()
    assert page.company_dashboard.groups
    for group in page.company_dashboard.groups.values():
        assert not hasattr(group, 'baseline_context')
    city = CityDashboard()
    city.set_snapshot(build([r('population', '', 0, 100), r('population', '', 1, 120)]))
    assert not hasattr(city, 'baseline_context')
    for widget in (page.company_dashboard, city):
        assert not any('卡片基准' in label.text() for label in widget.findChildren(QLabel))
    city.close()
    page.stop_workers()
    page.close()
