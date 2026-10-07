from decimal import Decimal
from PySide6.QtGui import QColor
from stats_charts import ChartPanel, _category_color
from latest_info_charts import mode_color
from test_stats_fluent_page import _loaded_page
from network_model import build_network_snapshot
import stats_tokens as tokens

EXPECTED={'bus':'#1976d2','trolley':'#7b2cbf','tram':'#d32f2f',
          'waterbus':'#f2c230','monorail':'#f06a24','metro':'#1e9e59'}

def test_all_transport_keys_and_aliases_have_authorized_colors():
    panel=type('Palette',(),{'_category_palette':tokens.DATA_CATEGORY_COLORS})()
    for key,color in EXPECTED.items():
        assert ChartPanel._category_color(panel,key).name()==color
        assert mode_color(key).name()==color
    for key,canonical in [('trolleybus','trolley'),('ferry','waterbus'),('单轨列车','monorail')]:
        assert ChartPanel._category_color(panel,key).name()==EXPECTED[canonical]
    assert ChartPanel._category_color(panel,'Student').name()==tokens.DATA_CATEGORY_COLORS[4].lower()
    assert ChartPanel._category_color(panel,'misc').name()!=EXPECTED['monorail']

def test_real_network_series_legend_detail_and_png_keep_transport_palette(qt_application,tmp_path):
    from test_network_model import dashboard,history
    from network_dashboard import NetworkDashboard
    from network_model import NetworkOptions
    rows=[history('transport-by-type','a',hour,20+i,group=key)
          for i,key in enumerate(EXPECTED) for hour in (0,1)]
    model=dashboard(rows,ids=('a',),comparison=None)
    snapshot=build_network_snapshot(model,NetworkOptions(),{'a':'Company A'})
    board=NetworkDashboard();board.set_snapshot(snapshot)
    panel=board.chart_panels[(None,'transport-by-type')]
    clone=panel._create_clone(None)
    try:
        for view in (*panel.chart_views,*clone.chart_views):
            for series in view.data.series:
                assert series.color.name()==EXPECTED[series.key]
        for key,chip in panel.legend_buttons.items():
            assert panel._legend_key_color(key).name()==EXPECTED[key]
        from stats_exports import export_png
        path=tmp_path/'transport.png';export_png(panel,path)
        assert path.exists() and path.stat().st_size>100
    finally:
        board.close();clone.close();board.deleteLater();clone.deleteLater()
