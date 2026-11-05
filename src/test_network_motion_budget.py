"""Viewport budgets must follow the visible summary during its animation."""
import pytest
from PySide6.QtTest import QTest
from test_network_dashboard import _fixture,_view


@pytest.mark.parametrize('mode',['overall','companies','period'])
def test_summary_reclaims_tall_viewport_continuously_without_rebuilding_charts(mode,tmp_path,monkeypatch):
    monkeypatch.setattr('stats_motion.animations_enabled',lambda:True)
    view,_=_view(_fixture(mode),tmp_path,monkeypatch)
    view.resize(1300,2600);view.show();view.reflow(1300,2600);QTest.qWait(30)
    panel=next(iter(view.chart_panels.values()));identity=id(panel)
    expanded=panel.height()
    assert expanded>460,'legacy chart height cap leaves a tall viewport blank'
    view.set_summary_collapsed(True)
    heights=[]
    for _ in range(10):
        QTest.qWait(25);heights.append(panel.height())
    assert len(set(heights))>2 and heights==sorted(heights)
    assert heights[-1]>expanded and id(next(iter(view.chart_panels.values())))==identity
    view.set_summary_collapsed(False);QTest.qWait(320)
    assert panel.height()==expanded
    view.close()


def test_company_summary_does_not_rebound_at_the_collapse_endpoint(tmp_path, monkeypatch, qt_application):
    monkeypatch.setattr('stats_motion.animations_enabled', lambda: True)
    view, _ = _view(_fixture('companies'), tmp_path, monkeypatch)
    try:
        view.resize(1300, 2600)
        view.show()
        view.reflow(1300, 2600)
        qt_application.processEvents()
        panel = next(iter(view.chart_panels.values()))
        view.set_summary_collapsed(True)
        for card in view.summary_cards:
            animation = card.summary_motion.animation
            animation.pause()
            animation.setCurrentTime(animation.duration() - 1)
        qt_application.processEvents()
        before_finish = panel.height()
        for card in view.summary_cards:
            card.summary_motion.finish()
        qt_application.processEvents()
        assert before_finish <= panel.height()
    finally:
        view.close()
