import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtTest import QSignalSpy

@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])

def options():
    return {'modes': [{'id':'bus','name':'公交','color':'#0067C0'}, {'id':'tram','name':'有轨电车','color':'#FF6600'}],
            'company_ids':[{'id':'real-a','name':'公司甲','color':'#009966'}],
            'road_levels':[{'id':'local','name':'普通道路'}],
            'building_classes':[{'id':'student','name':'学生'},{'id':'worker','name':'工人'}],
            'building_uses':[{'id':'transport','name':'交通设施'},{'id':'unknown','name':'未知'}],
            'lines':[{'id':12,'name':'12 长途公交','mode':'bus','company_id':'real-a','passengers':234,'profit':1,'color':'#0067C0'},
                     {'id':23,'name':'23 电车','mode':'tram','company_id':'real-a','passengers':0,'profit':None}],
            'passenger_date':'2030-01-02'}

def test_empty_manual_selection_survives_option_refresh(app):
    from map_panels import MapPanelSet
    p=MapPanelSet(); p.set_options(options())
    assert p.state()['manual_line_ids']=={12,23}
    p.set_state({'manual_line_ids':[], 'company_ids':[], 'stop_names':True})
    spy=QSignalSpy(p.stateChanged)
    p.set_options(options())
    assert p.state()['manual_line_ids']==set()
    assert p.state()['company_ids']==set()
    assert p.state()['stop_names'] is True and spy.count()==0

def test_search_selects_only_visible_lines_and_emits_one_state(app):
    from map_panels import MapPanelSet
    p=MapPanelSet(); p.set_options(options()); p.set_state({'manual_line_ids':[]}); p.search.setText('电车')
    p.manual_none.click(); spy=QSignalSpy(p.stateChanged); p.manual_all.click()
    assert p.state()['manual_line_ids']==set() and spy.count()==0
    p.filter_apply_buttons['manual_line_ids'].click()
    assert p.state()['manual_line_ids']=={23} and spy.count()==1
    assert p.line_list.count()==1

def test_class_filter_and_colour_target_are_independent(app):
    from map_panels import MapPanelSet
    p=MapPanelSet(); p.set_options(options())
    p.set_state({'building_classes':['student'], 'building_class_target':'worker'})
    assert p.state()['building_classes']=={'student'}
    assert p.state()['building_class_target']=='worker'
    p.group_lists['building_classes'].buttons['student'].click()
    assert p.state()['building_classes']==set()
    assert p.state()['building_class_target']=='worker'

def test_tri_state_and_order_survive_refresh(app):
    from map_panels import MapPanelSet
    p=MapPanelSet(); p.set_options(options())
    p.group_lists['layer_modes'].buttons['bus'].click()
    assert p.layer_checks['routes'].checkState()==Qt.CheckState.PartiallyChecked
    p.set_state({'mode_order':['tram','bus'], 'direction':'down', 'deadhead':True})
    p.set_options(options())
    assert p.state()['mode_order']==['tram','bus']
    assert p.state()['direction']=='down' and p.state()['deadhead'] is True

def test_layer_master_toggles_and_independent_labels(app):
    from map_panels import MapPanelSet
    p=MapPanelSet(); p.set_options(options())
    p.layer_checks['routes'].click()
    assert p.state()['layer_modes']==set() and not p.state()['routes']
    p.layer_checks['routes'].click()
    assert p.state()['layer_modes']=={'bus','tram'} and p.state()['routes']
    p.controls['stop_names'].click()
    assert p.state()['stop_names'] and p.state()['stops'] and not p.state()['line_numbers']

def test_signal_snapshot_cannot_mutate_state_and_manual_none_reset(app):
    from map_panels import MapPanelSet
    p=MapPanelSet(); p.set_options(options()); spy=QSignalSpy(p.stateChanged)
    p.manual_none.click();p.filter_apply_buttons['manual_line_ids'].click(); assert p.state()['manual_line_ids']==set()
    received=spy.at(0)[0]; received['manual_line_ids'].add(999)
    assert p.state()['manual_line_ids']==set()
    p.set_state({'manual_line_ids':None}); p.set_options(options())
    assert p.state()['manual_line_ids']=={12,23}

def test_numeric_filter_requires_valid_confirmed_bounds_and_keeps_unknown_distinct(app):
    from map_panels import MapPanelSet
    p=MapPanelSet(); p.set_options(options())
    p.controls['passenger_min'].setText('200'); p.controls['passenger_min'].editingFinished.emit()
    p.controls['passenger_max'].setText('10'); p.controls['passenger_max'].editingFinished.emit()
    p.filter_apply_buttons['passengers'].click()
    assert p.state()['passenger_min'] is None and p.state()['passenger_max'] is None
    p.controls['passenger_max'].setText('∞');p.filter_apply_buttons['passengers'].click()
    assert p.state()['passenger_min']==200 and p.state()['passenger_max'] is None

def test_order_list_move_persists_across_options_and_mode_switch(app):
    from map_panels import MapPanelSet
    from PySide6.QtCore import QModelIndex
    p=MapPanelSet(); p.set_options(options()); view=p.order_lists['mode_order']
    assert view.model().moveRow(QModelIndex(),0,QModelIndex(),2)
    assert p.state()['mode_order']==['tram','bus']
    p.set_state({'priority_by':'company'}); p.set_options(options())
    p.set_state({'priority_by':'mode'})
    assert p.state()['mode_order']==['tram','bus']
    assert view.item(0).data(Qt.ItemDataRole.UserRole)=='tram'

def test_building_special_categories_are_filterable_without_becoming_metric_targets(app):
    from map_panels import MapPanelSet
    p=MapPanelSet(); data=options()
    data['building_classes'] += [{'id':'transport','name':'交通设施'}, {'id':'special','name':'特殊建筑'}, {'id':'unknown','name':'未知'}]
    p.set_options(data)
    grid=p.group_lists['building_classes']
    assert set(grid.buttons)=={'student','worker','transport','special','unknown'}
    assert p.state()['building_class_target']=='student'
    assert 'building_class_target' not in p.controls and 'building_metric' not in p.controls

def test_break_even_routes_remain_selected_in_shared_query(app):
    from map_panels import MapPanelSet
    from map_query import MapQuery, RouteStats
    from map_model import MapSnapshot, MapRoute
    p=MapPanelSet(); route=MapRoute(12,'12',12,'real-a','公司甲','bus',(),())
    q=MapQuery(MapSnapshot(routes=(route,)),{12:RouteStats(234,0)})
    p.set_options(q.panel_options())
    assert [r.id for r in q.select(p.state()).routes]==[12]

def test_long_company_name_wraps_without_tooltip_or_horizontal_scroll(app):
    from map_panels import MapPanelSet
    from map_docking import MapDockHost
    from PySide6.QtWidgets import QWidget
    p=MapPanelSet(); data=options(); data['company_ids'][0]['name']='公司长名称'*12
    p.set_options(data); h=MapDockHost(QWidget(),p.panels); h.resize(960,680); h.show()
    p.filter_sections['company_ids'].set_expanded(True)
    h.activate_panel('filters'); app.processEvents()
    view=p.group_lists['company_ids']; item=view.item(0)
    assert view.visualItemRect(item).height()>50
    assert not item.toolTip() and view.horizontalScrollBar().maximum()==0
    h.close()

def test_dock_resize_and_tab_switch_do_not_emit_map_state_or_add_tooltips(app):
    from map_panels import MapPanelSet
    from map_docking import MapDockHost
    from PySide6.QtWidgets import QWidget
    p=MapPanelSet(); p.set_options(options()); h=MapDockHost(QWidget(),p.panels)
    h.resize(960,680); h.show(); app.processEvents(); spy=QSignalSpy(p.stateChanged)
    before=p.state(); h.resize(1440,960); h.activate_panel('filters'); app.processEvents()
    h.float_panel('display'); h.set_group_collapsed(True); app.processEvents()
    assert p.state()==before and spy.count()==0
    assert all(not w.toolTip() for w in h.findChildren(QWidget))
    h.close()

def test_display_choices_are_always_visible_and_exclusive(app):
    from map_panels import MapPanelSet
    from map_docking import MapDockHost
    from PySide6.QtWidgets import QWidget
    p=MapPanelSet(); p.set_options(options()); h=MapDockHost(QWidget(),p.panels)
    h.resize(960,680); h.show(); h.activate_panel('display'); app.processEvents()
    assert len(p.controls['direction'].buttons)==3
    assert len(p.controls['color_by'].buttons)==6
    assert len(p.controls['priority_by'].buttons)==3
    assert all(b.isVisible() for key in ('direction','color_by','priority_by') for b in p.controls[key].buttons.values())
    p.controls['direction'].buttons['down'].click()
    assert p.state()['direction']=='down'
    assert [b.isChecked() for b in p.controls['direction'].buttons.values()]==[False,False,True]
    h.close()

def test_filter_reset_restores_full_current_selection_and_clears_bounds(app):
    from map_panels import MapPanelSet
    p=MapPanelSet(); p.set_options(options()); p.set_state({'manual_line_ids':[],'modes':[],'passenger_min':10})
    p.reset_filters.click()
    assert p.state()['manual_line_ids']=={12,23} and p.state()['modes']=={'bus','tram'}
    assert p.state()['passenger_min'] is None

def test_filter_result_list_obeys_company_mode_profit_and_passenger_bounds(app):
    from map_panels import MapPanelSet
    p=MapPanelSet(); p.set_options(options())
    p.set_state({'modes':['bus'],'passenger_min':100,'profit_statuses':['profit']})
    assert p.line_list.count()==1 and p.line_list.item(0).data(Qt.ItemDataRole.UserRole)==12
    p.set_state({'company_ids':[]}); assert p.line_list.count()==0
    p.reset_filters.click(); assert p.line_list.count()==2

def test_direction_text_uses_shared_dark_blue_in_actual_paint(app):
    from map_panels import MapPanelSet
    from map_docking import MapDockHost
    from PySide6.QtWidgets import QWidget
    p=MapPanelSet(); p.set_options(options()); h=MapDockHost(QWidget(),p.panels)
    h.resize(960,680); h.show(); h.activate_panel('display'); app.processEvents()
    button=p.controls['direction'].buttons['whole']; image=button.grab().toImage()
    pixels=sum(image.pixelColor(x,y).name()=='#18314f' for y in range(image.height()) for x in range(image.width()))
    assert pixels>10
    assert not h.frames['display'].header.isVisible()
    h.close()

def test_single_line_results_preserve_passenger_filter_without_metric_text(app):
    from map_panels import MapPanelSet
    p=MapPanelSet(); p.set_options(options())
    assert p.line_list.item(0).text()=='公交12 长途公交'
    assert p.line_list.item(1).text()=='有轨电车23 电车'
    data=options(); data['lines'][1]['passengers']=None; p.set_options(data)
    assert p.line_list.item(1).text()=='有轨电车23 电车'
    p.set_state({'passenger_min':1})
    assert p.line_list.count()==1 and p.line_list.item(0).data(Qt.ItemDataRole.UserRole)==12

def test_class_and_road_grids_reuse_controls_on_same_options(app):
    from map_panels import MapPanelSet
    p=MapPanelSet(); p.set_options(options())
    road=p.group_lists['road_levels'].buttons['local']; social=p.group_lists['building_classes'].buttons['student']
    p.set_state({'direction':'down'}); p.set_options(options())
    assert p.group_lists['road_levels'].buttons['local'] is road
    assert p.group_lists['building_classes'].buttons['student'] is social

def test_company_drag_order_is_independent_and_survives_mode_switch(app):
    from map_panels import MapPanelSet
    from PySide6.QtCore import QModelIndex
    p=MapPanelSet(); data=options(); data['company_ids'].append({'id':'real-b','name':'公司乙','color':'#7967B7'})
    p.set_options(data); p.set_state({'priority_by':'company'})
    view=p.order_lists['company_order']; assert view.model().moveRow(QModelIndex(),0,QModelIndex(),2)
    assert p.state()['company_order']==['real-b','real-a']
    assert p.state()['mode_order']==['bus','tram']
    p.set_state({'priority_by':'mode'}); p.set_options(data); p.set_state({'priority_by':'company'})
    assert p.state()['company_order']==['real-b','real-a']
    assert view.item(0).data(Qt.ItemDataRole.UserRole)=='real-b'


def test_mode_width_controls_are_actual_options_and_preserve_overrides(app):
    from map_panels import MapPanelSet
    p=MapPanelSet(); p.set_options(options())
    assert set(p.mode_width_controls)=={'bus','tram'}
    spy=QSignalSpy(p.stateChanged)
    p.mode_width_controls['bus'].setValue(4.5)
    assert p.state()['mode_widths']=={'bus':4.5} and spy.count()==1
    p.set_options(options()); assert p.mode_width_controls['bus'].value()==4.5
    p.set_state({'mode_widths':{'bus':5.0,'metro':3.0}}); p.set_options(options())
    assert p.state()['mode_widths']=={'bus':5.0,'metro':3.0}
    assert 'metro' not in p.mode_width_controls
    p.mode_width_controls['bus'].setValue(0)
    assert p.state()['mode_widths']=={'metro':3.0}


def test_direction_style_setting_survives_single_direction_without_filter_changes(app):
    from map_panels import MapPanelSet
    p=MapPanelSet(); p.set_options(options()); selected=p.state()['manual_line_ids']
    p.controls['distinguish_directions'].click()
    assert p.state()['distinguish_directions'] is True
    p.set_state({'direction':'up'})
    assert p.state()['distinguish_directions'] is True
    assert not p.controls['distinguish_directions'].isEnabled()
    assert p.state()['manual_line_ids']==selected
    p.set_state({'direction':'whole'})
    assert p.controls['distinguish_directions'].isEnabled() and p.controls['distinguish_directions'].isChecked()


def test_building_emphasis_keeps_auto_state_and_uses_root_effective_value(app):
    from map_panels import MapPanelSet
    p=MapPanelSet(); data=options(); data['building_emphasis_effective']=False; p.set_options(data)
    before=p.state()
    assert p.state()['building_emphasis'] is None and not p.controls['building_emphasis'].isChecked()
    p.controls['building_emphasis'].click()
    assert p.state()['building_emphasis'] is True
    p.set_options(data); assert p.controls['building_emphasis'].isChecked()
    p.building_emphasis_auto.click()
    assert p.state()['building_emphasis'] is None and not p.controls['building_emphasis'].isChecked()
    data['building_emphasis_effective']=True; spy=QSignalSpy(p.stateChanged); p.set_options(data)
    assert p.controls['building_emphasis'].isChecked() and p.state()['building_emphasis'] is None and spy.count()==0
    assert p.state()['building_classes']==before['building_classes']
    assert p.state()['manual_line_ids']==before['manual_line_ids']
    assert 'building_color_by' not in p.controls


def test_width_defaults_reset_preserves_selection_and_normalizes_invalid_values(app):
    from map_panels import MapPanelSet
    p=MapPanelSet(); p.set_options(options()); before=p.state()
    p.set_state({'mode_widths':{'bus':100,'tram':.1,'metro':float('nan'),'unused':-2}})
    assert p.state()['mode_widths']=={'bus':12.0,'tram':.5}
    p.reset_widths.click(); assert p.state()['mode_widths']=={}
    assert p.state()['manual_line_ids']==before['manual_line_ids']
    assert p.state()['building_classes']==before['building_classes']
    assert p.state()['color_by']==before['color_by']
    assert p.state()['mode_order']==before['mode_order']


def test_retired_building_mode_cannot_hide_class_selection(app):
    from map_panels import MapPanelSet
    from map_docking import MapDockHost
    from PySide6.QtWidgets import QWidget
    p=MapPanelSet(); p.set_options(options()); p.set_state({'building_color_by':'use','building_classes':['student']})
    h=MapDockHost(QWidget(),p.panels); h.resize(960,680); h.show(); h.activate_panel('layers'); app.processEvents()
    assert p.group_lists['building_classes'].isVisible()
    assert 'building_uses' not in p.group_lists
    assert 'building_color_by' not in p.controls and 'building_metric' not in p.controls
    assert p.layer_checks['buildings'].checkState()==Qt.CheckState.PartiallyChecked
    h.close()


def test_building_auto_emphasis_tracks_actual_query_visibility_without_becoming_manual(app):
    from map_panels import MapPanelSet
    from map_query import MapQuery
    from map_model import MapSnapshot,MapRoute
    route=MapRoute(12,'12',12,'real-a','公司甲','bus',(),(((0.,0.,0.),(100.,0.,0.)),))
    query=MapQuery(MapSnapshot(routes=(route,)))
    p=MapPanelSet(); p.set_options(query.panel_options(state=p.state()))
    assert not p.controls['building_emphasis'].isChecked() and p.state()['building_emphasis'] is None
    p.layer_checks['routes'].click(); result=query.select(p.state())
    p.set_options(query.panel_options(state=p.state(),result=result))
    assert p.controls['building_emphasis'].isChecked() and p.state()['building_emphasis'] is None
    p.set_state({'building_emphasis':False})
    assert not p.controls['building_emphasis'].isChecked()
    p.building_emphasis_auto.click()
    assert p.controls['building_emphasis'].isChecked() and p.state()['building_emphasis'] is None


def test_building_function_legend_remains_separate_from_class_filter(app):
    from map_panels import MapPanelSet
    from map_docking import MapDockHost
    from PySide6.QtWidgets import QWidget
    p=MapPanelSet(); p.set_options(options())
    h=MapDockHost(QWidget(),p.panels); h.resize(1440,921); h.show(); app.processEvents()
    assert p.building_function_legend.isVisible()
    assert [label.text() for label in p.building_function_labels.values()]==[
        '住宅','工作','商业／休闲','住宅／工作','商业／工作','其他']
    before=p.state(); spy=QSignalSpy(p.stateChanged)
    p.group_lists['building_classes'].buttons['student'].click()
    assert p.state()['building_classes']=={'worker'} and spy.count()==1
    assert p.state()['building_uses']==before['building_uses']
    assert p.building_function_legend.isVisible()
    p.set_state({'building_classes':[]})
    assert p.building_function_legend.isVisible()
    assert 'building_color_by' not in p.controls and 'building_uses' not in p.group_lists
    assert all(not widget.toolTip() for widget in p.building_function_legend.findChildren(QWidget))
    h.close()


def test_function_legend_uses_renderer_colors_and_actual_special_options(app):
    from map_panels import MapPanelSet
    from map_model import BuildingFunctionValues
    from semantic_colors import building_function_fill,map_fill
    p=MapPanelSet(); data=options(); data['building_emphasis_effective']=False
    data['building_classes'] += [{'id':'transport','name':'交通建筑','color':'#D8AF43'}]
    p.set_options(data)
    def swatch_color(key):return p.building_function_swatches[key].palette().window().color().name().upper()
    assert swatch_color('residential')==building_function_fill(BuildingFunctionValues(1,0,0,1),False)
    assert swatch_color('mixed')==building_function_fill(BuildingFunctionValues(0,1,1,1),False)
    assert p.building_function_labels['transport'].text()=='交通建筑'
    assert swatch_color('transport')==map_fill('usage','transport',.20)
    assert 'special' not in p.building_function_labels
    p.set_state({'building_emphasis':True})
    assert swatch_color('residential')==building_function_fill(BuildingFunctionValues(1,0,0,1),True)
    assert swatch_color('transport')==map_fill('usage','transport',.65)
    p.building_function_legend.show(); app.processEvents()
    image=p.building_function_swatches['mixed'].grab().toImage()
    assert image.pixelColor(image.width()//2,image.height()//2).name().upper()==building_function_fill(BuildingFunctionValues(0,1,1,1),True)


def test_native_capacity_options_restore_six_classes_and_drive_function_filter(app):
    from map_panels import MapPanelSet
    from map_query import MapQuery
    from map_model import MapSnapshot,MapBuilding,GroupFunctionCount,SOCIAL_GROUPS
    from semantic_colors import building_function_fill
    from map_model import BuildingFunctionValues
    records=tuple(GroupFunctionCount(g,100 if g=='BlueCollar' else 0,
                                     100 if g=='Student' else 0,20) for g in SOCIAL_GROUPS)
    b=MapBuilding(1,'fixture','',(0,0,0),function_capacities=records)
    query=MapQuery(MapSnapshot(buildings=(b,)))
    p=MapPanelSet(); p.set_options(query.panel_options())
    assert set(SOCIAL_GROUPS)<=set(p.group_lists['building_classes'].buttons)
    p.set_state({'building_classes':['BlueCollar']})
    home=query.select(p.state()); p.set_options(query.panel_options(state=p.state(),result=home))
    assert home.building_colors[1]==building_function_fill(BuildingFunctionValues(100,0,20,120),True)
    assert p.state()['building_classes']=={'BlueCollar'}
    p.set_state({'building_classes':['Student']}); work=query.select(p.state())
    assert work.building_colors[1]!=home.building_colors[1]
    assert p.building_function_labels['mixed'].text()=='商业／工作'
    p.set_state({'building_classes':[]}); empty=query.select(p.state())
    assert not empty.snapshot.buildings
    p.set_options(query.panel_options(state=p.state(),result=empty))
    assert p.state()['building_classes']==set()
