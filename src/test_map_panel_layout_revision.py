"""Approved map panel spacing, applied summaries and flexible list budgets."""
import pytest
from PySide6.QtCore import Qt,QPoint
from PySide6.QtTest import QTest,QSignalSpy
from PySide6.QtWidgets import QWidget
from map_panels import MapPanelSet
from map_preset_panels import PlanningPanel
from map_docking import MapDockHost
from test_map_panels import options


def settle(app):
    for _ in range(4):app.processEvents()


def test_population_controls_reject_legacy_nonpopulation_categories(qt_application):
    legacy=options();legacy['building_classes'] += [dict(id=key,name=key) for key in ('transport','special','unknown')]
    network=MapPanelSet();network.set_options(legacy)
    planning=PlanningPanel();planning.set_options(legacy)
    for grid in (network.group_lists['building_classes'],planning.class_grid):
        assert set(grid.buttons)=={'student','worker'}
    assert network.state()['building_classes']=={'student','worker'}
    assert planning.state()['building_classes']=={'student','worker'}
    assert {'transport','special'}<=set(network.building_function_labels)
    for button in network.group_lists['building_classes'].buttons.values():button.click()
    assert network.state()['building_classes']==set() and network.state()['buildings'] is True
    assert network.layer_checks['buildings'].checkState()==Qt.CheckState.PartiallyChecked


def test_population_only_options_keep_actual_nonpopulation_function_legends(qt_application):
    data=options();data['building_uses'] += [dict(id='special',name='特殊建筑')]
    panel=MapPanelSet();panel.set_options(data)
    assert {'transport','special'}<=set(panel.building_function_labels)
    assert set(panel.group_lists['building_classes'].buttons)=={'student','worker'}
    panel.set_options({})
    assert 'transport' not in panel.building_function_labels and 'special' not in panel.building_function_labels


def test_station_controls_have_one_display_group_and_preserve_dependencies(qt_application):
    panel=MapPanelSet();panel.set_options(options())
    for key in ('stops','line_numbers','stop_names'):
        assert panel.panels['display'].isAncestorOf(panel.controls[key])
        assert not panel.panels['layers'].isAncestorOf(panel.controls[key])
    assert panel.controls['stops'].parentWidget() is panel.controls['stop_names'].parentWidget()
    panel.set_state({'stops':True,'stop_names':False});spy=QSignalSpy(panel.stateChanged)
    panel.controls['stop_names'].click()
    assert panel.state()['stops'] and panel.state()['stop_names'] and spy.count()==1
    panel.controls['stops'].click()
    assert not panel.state()['stops'] and panel.state()['stop_names']


def test_layer_rows_have_normal_spacing_and_long_content_scrolls(qt_application):
    panel=MapPanelSet();panel.set_options(options())
    host=MapDockHost(QWidget(),panel.panels);host.resize(960,480);host.show();settle(qt_application)
    section=panel.layer_checks['buildings'].parentWidget().layout()
    assert section.spacing()>=8
    grid=panel.group_lists['building_classes']
    cells=[button.parentWidget() for button in grid.buttons.values()]
    assert all(cell.minimumHeight()>=36 for cell in cells)
    assert cells[0].parentWidget().layout().verticalSpacing()>=8
    assert panel.panels['layers'].verticalScrollBar().maximum()>0


@pytest.mark.parametrize('minimum,maximum,expected',[(5000,15000,'5000-15000人次'),(5000,None,'5000-∞人次'),(None,15000,'0-15000人次'),(0,None,'0-∞人次')])
def test_passenger_summaries_use_applied_bounds_without_prefix(qt_application,minimum,maximum,expected):
    panel=MapPanelSet();panel.set_options(options());panel.set_state({'passenger_min':minimum,'passenger_max':maximum})
    panel.set_result_count(22);label=panel.filter_sections['passengers'].summary_label
    assert label.text()==expected+' 已选：22条'
    panel.controls['passenger_min'].setText('9999')
    assert label.text()==expected+' 已选：22条'


def test_every_filter_summary_omits_screening_prefix(qt_application):
    panel=MapPanelSet();panel.set_options(options())
    panel.set_state({'company_ids':[],'modes':['bus'],'profit_statuses':['loss'],'manual_line_ids':[],
        'service_time_mode':'range','service_start':'2030-01-02T17:00:00','service_end':'2030-01-02T18:00:00'})
    panel.set_result_count(0)
    assert [panel.filter_sections[key].summary_label.text() for key in ('company_ids','modes','profit_statuses','manual_line_ids','service')]==[
        '无 已选：0条','公交 已选：0条','亏损 已选：0条','0条 已选：0条','周三17:00-18:00 已选：0条']


def test_network_selection_list_fills_remaining_panel_height_and_collapses(qt_application):
    panel=MapPanelSet();panel.set_options(options());host=MapDockHost(QWidget(),panel.panels)
    host.resize(960,680);host.show();host.activate_panel('filters');settle(qt_application)
    view=panel.line_list;before=view.height()
    host.resize(960,900);settle(qt_application)
    assert view.height()>before+150 and view.height()>260
    scroll=panel.panels['filters'];button=panel.filter_apply_buttons['manual_line_ids']
    bottom=button.mapTo(scroll.widget(),QPoint()).y()+button.height()
    assert scroll.widget().height()-bottom<=24
    panel.filter_sections['manual_line_ids'].set_expanded(False);settle(qt_application)
    assert panel.filter_sections['manual_line_ids'].height()<100


def test_planning_comparison_list_fills_height_even_when_empty(qt_application):
    panel=PlanningPanel();panel.set_options(options());host=MapDockHost(QWidget(),{'planning':panel})
    host.resize(960,680);host.show();settle(qt_application);before=panel.line_list.height()
    host.resize(960,900);settle(qt_application)
    assert panel.line_list.height()>before+150 and panel.line_list.height()>260
    bottom=panel.line_list.mapTo(panel.widget(),QPoint()).y()+panel.line_list.height()
    assert panel.widget().height()-bottom<=24


def test_single_panel_has_no_title_tab_and_can_drag_collapse_float_and_pin(qt_application,monkeypatch):
    monkeypatch.setattr('stats_motion.animations_enabled',lambda:False)
    host=MapDockHost(QWidget(),{'planning':PlanningPanel()});host.resize(960,680);host.show();settle(qt_application)
    assert host.tabs_widget.isHidden()
    handle=host.drag_handle;assert handle.isVisible() and handle.accessibleName()=='拖动面板'
    host.group_button.click();settle(qt_application);assert host._group_collapsed and host.dock.width()==44
    host.group_button.click();settle(qt_application);assert not host._group_collapsed and host.tabs_widget.isHidden()
    QTest.mousePress(handle,Qt.MouseButton.LeftButton,pos=QPoint(10,10))
    QTest.mouseMove(handle,QPoint(-70,50));QTest.mouseRelease(handle,Qt.MouseButton.LeftButton,pos=QPoint(-70,50))
    frame=host.frames['planning'];assert frame.floating and frame.header.isVisible()
    host.set_pinned('planning',True);assert frame.pinned
    host.dock_panel('planning');settle(qt_application);assert not frame.floating and host.tabs_widget.isHidden()
