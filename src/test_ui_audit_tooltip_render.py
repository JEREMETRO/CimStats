"""Read-only real snapshot regression and offscreen UI-09 evidence renderer."""
from datetime import datetime
import json
from math import ceil
import os
from pathlib import Path
import sys

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'frontend'), str(ROOT / 'src')]

import pytest
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QApplication

from report_model import load_session
from statistics_model import HistoryStore, Query
from stats_charts import ChartPanel
from stats_typography import ui_font
from test_bar_tooltip import PaintedCanvas, deliver
from test_ui_audit_tooltip_units import (render_tooltip, image_for, assert_complete_single_line,
                                       tooltip_theme)

SAVE = Path('D:/test/CimStats/jobs/c60207891e1d4b36ba0b89026b830dcc')
OUT = ROOT / 'jobs/ui-audit-20261007/tooltip-evidence'


def real_chart():
    session = load_session(SAVE, '秋山市n6 (4)_运行时')
    names = {str(company['公司标识']): company['公司名称'] for company in session['companies']}
    store = HistoryStore(session['history'], session['simulation_time'])
    query = Query('transport-by-type', tuple(names), None,
                  datetime(2013, 5, 13), datetime(2013, 5, 20), 'day')
    result = store.query(query)
    panel = ChartPanel('客流', default_mode='trend-bar')
    panel.set_result(result, names)
    return panel, panel.chart_views[0].data, session['simulation_time']


@pytest.mark.skipif(not SAVE.is_dir(), reason='UI-09 read-only real archive is unavailable')
@pytest.mark.parametrize('size,detailed', [((480, 260), False), ((400, 190), False), ((960, 540), True)])
def test_real_snapshot_hover_retains_values_and_clears_after_resize(size, detailed):
    panel, data, _ = real_chart()
    canvas = PaintedCanvas(detailed=detailed); canvas.resize(*size); canvas.set_data(data)
    canvas.show(); QApplication.processEvents(); canvas.grab()
    try:
        index, stack, path = canvas._bar_hits[-1]
        deliver(canvas, path.boundingRect().center())
        assert canvas._hover == index and canvas._hover_stack == stack
        rows = canvas._tooltip_rows(index, stack)
        assert canvas.painted_tip[1] == rows
        for _, name, value, note in rows:
            _, actual, expected, box, draws = render_tooltip(canvas, name, value, note=note)
            assert_complete_single_line(actual, expected, box, draws, value)
        canvas.resize(size[0] + 10, size[1] + 10)
        QApplication.processEvents()
        assert canvas._hover is None
        assert canvas._overflow_tip is None or not canvas._overflow_tip.isVisible()
    finally:
        canvas.close(); panel.close()


def evidence():
    app = QApplication.instance() or QApplication([])
    from stats_style import initialize_theme
    initialize_theme(app)
    OUT.mkdir(parents=True, exist_ok=True)
    dpr = app.primaryScreen().devicePixelRatio()
    tag = str(dpr).replace('.', '_')
    panel, data, simulation_time = real_chart()
    records = []
    for label, size, detailed in [('normal', (480, 260), False), ('compact', (400, 190), False),
                                   ('detail', (960, 540), True)]:
        canvas = PaintedCanvas(detailed=detailed); canvas.resize(*size); canvas.set_data(data)
        canvas.show(); app.processEvents(); canvas.grab()
        index, stack, path = canvas._bar_hits[-1]
        deliver(canvas, path.boundingRect().center()); app.processEvents()
        assert canvas.grab().save(str(OUT / f'real-{label}-dpr{tag}.png'))
        tip = canvas._overflow_tip
        if tip is not None and tip.isVisible():
            assert tip.grab().save(str(OUT / f'real-{label}-overflow-dpr{tag}.png'))
        records.append(dict(mode=label, size=size, actual_dpr=canvas.devicePixelRatioF(),
                            title=canvas.painted_tip[0],
                            rows=[list(map(str, row[1:])) for row in canvas.painted_tip[1]],
                            draws=[dict(text=text, rect=rect.getRect(), flags=int(flags),
                                        font=font.toString()) for rect, flags, text, font in canvas.drawn]))
        canvas.close()
    panel.close()
    short = '八连交通集团'
    long = '环比 · 滨海市公共交通运营有限公司 [76561198845688243]'
    cases = [(short, '123,456.78 人次'), (long, '123,456.78 人次'),
             (short, '0 人数'), (long, '-123,456.78 人数'),
             (short, '123,456,789,012,345,678,901,234,567.89 人次每班'),
             (long, '123,456.78 人次每车公里'), (short, '-123,456.78 人次每班'),
             (long, '0 人次每车公里')]
    canvas = PaintedCanvas()
    tiles = []
    for name, value in cases:
        tile, actual, expected, box, draws = render_tooltip(canvas, name, value, dpr, '边界合成样本')
        assert_complete_single_line(actual, expected, box, draws, value)
        tiles.append(tile)
        records.append(dict(sample='synthetic boundary', name=name, value=value,
                            draws={text: dict(rect=rect.getRect(), flags=int(flags))
                                   for text, (rect, flags, _) in draws.items()}))
    tile_width = ceil(max(tile.width() / dpr for tile in tiles)) + 20
    tile_height = ceil(max(tile.height() / dpr for tile in tiles)) + 40
    sheet = image_for(tile_width * 2, tile_height * 4, dpr)
    sheet.fill(Qt.GlobalColor.white)
    painter = QPainter(sheet); painter.setFont(ui_font(12)); painter.setPen(Qt.GlobalColor.black)
    for index, tile in enumerate(tiles):
        x, y = (index % 2) * tile_width, (index // 2) * tile_height
        painter.drawText(QRectF(x + 8, y + 2, tile_width - 16, 24),
                         Qt.TextFlag.TextSingleLine, f'边界样本 {index + 1} · DPR {dpr}')
        painter.drawImage(x + 8, y + 28, tile)
    painter.end()
    assert sheet.save(str(OUT / f'edge-values-dpr{tag}.png'))
    canvas.close()
    (OUT / f'render-dpr{tag}.json').write_text(json.dumps(dict(source=str(SAVE),
        simulation_time=simulation_time, real_query='transport-by-type [2013-05-13,2013-05-20)',
        screen_dpr=dpr, records=records), ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'UI-09 offscreen evidence rendered at DPR {dpr}: {OUT}')


if __name__ == '__main__':
    evidence()
