"""Selected native direction metrics reach the actual map information panel."""
import pytest
from PySide6.QtCore import QSettings


@pytest.fixture
def direction_page(qt_application, tmp_path):
    from map_model import MapRoute, MapSnapshot, RouteDirection
    from map_page import MapPage
    tick = 600_000_000
    paths = (((0., 0., 0.), (100., 0., 0.)),
             ((100., 0., 0.), (0., 0., 0.)))
    route = MapRoute(20, '7路', 7, 'a', '公司', 'bus', (1, 2, 1), paths,
        RouteDirection('roundtrip', 1), ((paths[0],), (paths[1],)),
        depot_paths=(((0., 0., 0.), (10., 0., 0.)),),
        leg_map_length_units=(512000, 1024000),
        depot_map_length_units=(25600, 51200),
        stop_arrival_offsets_ticks=(0, 12*tick, 30*tick))
    page = MapPage(QSettings(str(tmp_path/'directions.ini'), QSettings.Format.IniFormat))
    page.set_session(dict(save_key='directions', simulation_time='2013-05-23T23:59:00',
        lines=[{'对象ID': 20, '线路名称': '7路', '线路号': 7, '运输制式': '公交',
            '公司标识': 'a', '公司名称': '公司', '地图里程': 3.15,
            '单程时间': 55, '核定速度': 3.44, '当日发班数': 0, '今日客流': 0,
            '时刻表': {}, '原始字段': {'单程时间_tick': 55*tick, '客流_今日': 0, '时刻表数': 0}}]))
    page.set_snapshot(MapSnapshot(routes=(route,), bounds=(0, 0, 100, 100)))
    page.set_preset('single')
    assert page.show_route(20, page.save_token)
    yield page
    page.close(); page.deleteLater()


def test_direction_changes_update_lengths_time_speed_and_full_line_visibility(direction_page):
    panel = direction_page.single_panel
    assert panel.fact_labels['geometry_km'].text() == '2 km'
    assert panel.information_labels['单程时间'].text() == '18 min'
    assert panel.information_labels['核定速度'].text() == '6.66 km/h'
    assert '地图里程' not in panel.information_labels
    panel.direction_buttons['down'].click()
    assert panel.fact_labels['geometry_km'].text() == '1 km'
    assert panel.information_labels['单程时间'].text() == '12 min'
    assert panel.information_labels['核定速度'].text() == '5 km/h'
    panel.deadhead_check.click()
    assert panel.fact_labels['geometry_km'].text() == '1.05 km'
    assert panel.information_labels['核定速度'].text() == '5 km/h'
    panel.direction_buttons['both'].click()
    assert panel.information_labels['地图里程'].text() == '3.15 km'
    assert panel.information_labels['单程时间'].text() == '55 min'
    assert panel.information_labels['核定速度'].text() == '3.44 km/h'
