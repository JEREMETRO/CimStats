"""Feedback contracts: compact identity rows, sidebar search and time ranges."""
from types import SimpleNamespace
from PySide6.QtCore import Qt, QPoint
from PySide6.QtTest import QSignalSpy,QTest
from PySide6.QtWidgets import QWidget
from map_model import MapRoute,RouteDirection


def catalog():
    path=(((0.,0.,0.),(100.,0.,0.)),)
    return [MapRoute(12,'12 中央线',12,'a','公司甲','bus',(),path,RouteDirection('roundtrip'),depot_paths=path),
            MapRoute(23,'23 环线',23,'b','公司乙','tram',(),path,RouteDirection('ring'))]


def test_all_route_lists_are_one_line_with_mode_color_and_stable_selection(qt_application):
    from map_panels import MapPanelSet
    from map_preset_panels import PlanningPanel,SingleLinePanel
    p=MapPanelSet();p.set_options({'modes':[{'id':'bus','name':'公交'}],
        'lines':[{'id':12,'name':'12 中央线','mode':'bus','passengers':1234,'color':'#0067C0'}]})
    assert p.line_list.item(0).text()=='公交12 中央线'
    assert not p.line_list.item(0).icon().isNull()
    p.manual_none.click();assert p.state()['manual_line_ids']==set()
    single=SingleLinePanel();single.set_routes(catalog())
    assert single.route_list.item(0).text()=='公交12 中央线'
    assert not single.route_list.item(0).icon().isNull()
    plan=PlanningPanel();plan.set_routes(catalog(),{12})
    assert plan.line_list.item(1).text()=='有轨电车23 环线'
    assert plan.line_list.item(0).checkState()==Qt.CheckState.Checked
    plan.line_list.item(1).setCheckState(Qt.CheckState.Checked)
    assert plan.state()['selected_ids']=={12,23}


def test_sidebar_search_expands_on_input_and_collapses_after_stable_id_activation(qt_application):
    from map_preset_panels import SingleLinePanel
    p=SingleLinePanel();p.resize(360,680);p.set_routes(catalog());p.show();qt_application.processEvents()
    assert p.search.isVisible() and not p.route_list.isVisible()
    p.search.setText('23');qt_application.processEvents()
    assert p.route_list.isVisible() and p.route_list.count()==1
    spy=QSignalSpy(p.routeSelected);p.route_list.setCurrentRow(0)
    QTest.keyClick(p.route_list,Qt.Key.Key_Return);qt_application.processEvents()
    assert spy.count()==1 and spy.at(0)[0]==23
    assert p.state()['selected_route_id']==23 and p.search.text()=='23'
    assert not p.route_list.isVisible()
    p.set_state({'selected_route_id':23})
    assert p.route_list.currentItem().data(Qt.ItemDataRole.UserRole)==23 and spy.count()==1


def test_sidebar_two_information_groups_consume_formatter_text_without_geometry_conversion(qt_application):
    from map_preset_panels import SingleLinePanel
    p=SingleLinePanel();p.set_state({'direction':'whole'})
    info={'identity':{'id':12,'name':'12 中央线','mode':'公交','company_id':'a','company_name':'已解析公司'},
          'sections':(('line_information','线路信息',(('地图里程','地图里程（全线）','17.57 km'),('每周收入','每周收入','-123.45'),('单程时间','核定时间（全线）','55 min'))),
                      ('passenger_data','客流数据',(('今日客流','今日客流','8,250 人次'),('平均客流','平均客流','—'))))}
    p.set_route(catalog()[0],SimpleNamespace(),11.236,.2,information=info)
    assert p.route_identity.text()=='已解析公司'
    assert p.fact_labels['geometry_km'].text()=='11.23 km'
    assert p.information_labels['地图里程'].text()=='17.57 km'
    assert p.information_labels['每周收入'].text()=='-123.45'
    assert set(p.data_sections)=={'line_information','passenger_data'}
    p.deadhead_check.click()
    assert p.fact_labels['geometry_km'].text()=='11.43 km'
    assert p.information_labels['地图里程'].text()=='17.57 km'
    assert p.information_labels['平均客流'].text()=='—'


def test_selected_direction_replaces_full_time_and_speed_and_hides_redundant_whole_length(qt_application):
    from map_preset_panels import SingleLinePanel
    from map_line_presentation import line_information
    p=SingleLinePanel();p.resize(360,680);p.show()
    session={'lines':[{'对象ID':12,'地图里程':17.57,'单程时间':80,'核定速度':13.17,'今日客流':823,'当日发班数':70,'站点数':12}]}
    for direction,label,length,duration,speed in [('up','上行',8.18,23.9115,20.525),('down','下行',9.12,23.411,23.37),('whole','全线',17.3,47.3225,21.93)]:
        metrics=SimpleNamespace(effective_direction=direction,duration_minutes=duration,speed_kmh=speed)
        info=line_information(session,12,direction_metrics=metrics)
        p.set_state({'direction':direction});p.set_route(catalog()[0],None,length,.2,information=info)
        qt_application.processEvents()
        assert p.information_captions['geometry_km'].text()==f'{label}长度'
        assert p.information_captions['单程时间'].text()==f'核定时间（{label}）'
        assert p.information_captions['核定速度'].text()==f'核定速度（{label}）'
        assert ('地图里程' in p.information_labels)==(direction=='whole')
        assert p.fact_labels['duration_minutes'].text()=={'up':'23.91 min','down':'23.41 min','whole':'80 min'}[direction]
        assert p.information_labels['核定速度'].text()=={'up':'20.52 km/h','down':'23.37 km/h','whole':'13.17 km/h'}[direction]
        assert p.fact_labels['transported_today'].text()=='823 人次'
        assert p.information_captions['当日发班数'].text()=='当日发班'


def test_legacy_full_line_information_is_not_shown_as_a_selected_leg(qt_application):
    from map_preset_panels import SingleLinePanel
    from map_line_presentation import line_information
    p=SingleLinePanel();p.set_route(catalog()[0],None,8,0,information=line_information(
        {'lines':[{'对象ID':12,'地图里程':17.57,'单程时间':80,'核定速度':13.17}]},12))
    assert p.information_labels['地图里程'].parentWidget().isHidden()
    assert p.fact_labels['duration_minutes'].text()=='—' and p.information_labels['核定速度'].text()=='—'


def test_ring_information_uses_whole_titles_and_keeps_direction_buttons_hidden(qt_application):
    from map_preset_panels import SingleLinePanel
    from map_line_presentation import line_information
    p=SingleLinePanel();info=line_information({'lines':[{'对象ID':23,'单程时间':20}]},23,
        direction_metrics=SimpleNamespace(effective_direction='whole',duration_minutes=20,speed_kmh=12))
    p.set_route(catalog()[1],None,4,0,information=info)
    assert p.information_captions['geometry_km'].text()=='全线长度'
    assert p.information_captions['单程时间'].text()=='核定时间（全线）'
    assert not p._direction.isVisible() and p.fact_labels['duration_minutes'].text()=='20 min'


def test_length_duration_speed_are_contiguous_before_stop_count_after_line_dates(qt_application):
    from map_preset_panels import SingleLinePanel
    from map_line_presentation import line_information
    p=SingleLinePanel()
    session={'lines':[{'对象ID':12,'地图里程':17.57,'单程时间':55,'核定速度':19.17,'站点数':12,
                      '线路车库':'东库','开线日期':'2013-05-01','最近改线日期':'2013-05-02'}]}
    for direction in ('up','whole'):
        p.set_state({'direction':direction})
        info=line_information(session,12,direction_metrics=SimpleNamespace(
            effective_direction=direction,duration_minutes=23.9115,speed_kmh=21.655))
        p.set_route(catalog()[0],None,8.63,.2,information=info)
        layout=p._data_layouts['line_information']
        # Actual visible Qt row positions, rather than a source-code order check.
        keys=[next(key for key,value in p.information_labels.items() if value.parentWidget() is layout.itemAt(i).widget())
              for i in range(1,layout.count()) if not layout.itemAt(i).widget().isHidden()]
        expected=['线路车库','开线日期','最近改线日期','geometry_km']
        if direction=='whole':expected+=['地图里程']
        expected+=['单程时间','核定速度','站点数']
        assert keys[:len(expected)]==expected


def test_replacing_information_schema_hides_old_rows_immediately(qt_application):
    from map_preset_panels import SingleLinePanel
    p=SingleLinePanel();p.show();qt_application.processEvents()
    old=p.fact_labels['duration_minutes'].parentWidget()
    info={'sections':(('line_information','线路信息',(('地图里程','地图里程（全线）','17.57 km'),)),('passenger_data','客流数据',()))}
    p.set_route(catalog()[0],None,11.23,0,information=info)
    assert old.isHidden()


def test_sidebar_enter_unique_and_multi_match_are_real_keyboard_actions(qt_application):
    from map_preset_panels import SingleLinePanel
    p=SingleLinePanel();p.resize(360,680);p.set_routes(catalog());p.show();qt_application.processEvents()
    spy=QSignalSpy(p.routeSelected);p.search.setText('23')
    QTest.keyClick(p.search,Qt.Key.Key_Return);qt_application.processEvents()
    assert spy.count()==1 and spy.at(0)[0]==23 and not p.route_list.isVisible()
    p.search.clear();QTest.keyClick(p.search,Qt.Key.Key_Return);qt_application.processEvents()
    assert p.route_list.isVisible() and p.route_list.hasFocus() and spy.count()==1
    p.route_list.setCurrentRow(0);QTest.keyClick(p.route_list,Qt.Key.Key_Return)
    assert spy.count()==2 and spy.at(1)[0]==12


def test_planning_search_enter_adds_only_unique_match_and_preserves_global_set(qt_application):
    from map_preset_panels import PlanningPanel
    p=PlanningPanel();p.set_routes(catalog(),{99});p.resize(360,680);p.show();qt_application.processEvents()
    spy=QSignalSpy(p.selectionChanged);p.search.setText('23')
    QTest.keyClick(p.search,Qt.Key.Key_Return)
    assert p.state()['selected_ids']=={23,99} and spy.count()==1
    QTest.keyClick(p.search,Qt.Key.Key_Return);assert spy.count()==1


def test_shared_catalog_label_does_not_gain_company_id_or_duplicate_mode(qt_application):
    from map_preset_panels import PlanningPanel
    p=PlanningPanel();p.set_routes([{'id':1,'name':'1路','mode':'bus','company_id':'private-id','company_name':'八连交通集团','selectable':True,'display_label':'八连交通集团公交1路'}],set())
    assert p.line_list.item(0).text()=='八连交通集团公交1路'


def test_current_route_heading_uses_complete_catalog_display_label(qt_application):
    from map_preset_panels import SingleLinePanel
    p=SingleLinePanel();p.set_routes(catalog());p.set_route(catalog()[0],None,1,0)
    assert p.route_title.text()=='公交12 中央线'


def test_disabled_known_route_keeps_shared_label_and_exposes_reason_accessibly(qt_application):
    from map_preset_panels import PlanningPanel
    p=PlanningPanel();p.set_routes([{'id':1,'name':'1路','mode':'bus','company_id':'private-id','company_name':'八连交通集团','selectable':False,'display_label':'八连交通集团公交1路'}],set())
    item=p.line_list.item(0)
    assert item.text()=='八连交通集团公交1路' and item.toolTip()==''
    assert item.data(Qt.ItemDataRole.AccessibleDescriptionRole)=='无地图路径'
    spy=QSignalSpy(p.selectionChanged);p.search.setText('1路')
    QTest.keyClick(p.search,Qt.Key.Key_Return)
    assert spy.count()==0 and p.state()['selected_ids']==set()


def test_time_inputs_and_keyboard_handles_preserve_cross_midnight_endpoint_roles(qt_application):
    from map_panels import MapPanelSet
    p=MapPanelSet();p.set_options({'simulated_datetime':'2030-01-02T23:30:00'})
    p.controls['service_time_mode'].buttons['range'].click()
    editor=p.service_editor;editor.end_edit.setText('01:00')
    assert p.state()['service_start']=='2030-01-02T23:30:00'
    assert p.state()['service_end']=='2030-01-03T01:00:00'
    assert editor.time_axis.values()==(1410,60)
    spy=QSignalSpy(p.stateChanged)
    QTest.keyClick(editor.time_axis.handles[0],Qt.Key.Key_Right)
    assert editor.start_edit.text()=='23:31' and p.state()['service_start']=='2030-01-02T23:31:00'
    assert p.state()['service_end']=='2030-01-03T01:00:00' and spy.count()==1


def test_weekday_handles_select_simulated_week_and_sunday_wraps_to_next_monday(qt_application):
    from map_panels import MapPanelSet
    p=MapPanelSet();p.set_options({'simulated_datetime':'2030-01-02T23:30:00'})
    p.controls['service_time_mode'].buttons['range'].click();editor=p.service_editor
    editor.end_edit.setText('01:00')
    QTest.keyClick(editor.week_axis.handles[0],Qt.Key.Key_End)
    QTest.keyClick(editor.week_axis.handles[1],Qt.Key.Key_Home)
    assert p.state()['service_start']=='2030-01-06T23:30:00'
    assert p.state()['service_end']=='2030-01-07T01:00:00'


def test_mouse_drag_keeps_start_end_roles_and_syncs_text(qt_application):
    from map_panels import MapPanelSet
    from map_docking import MapDockHost
    p=MapPanelSet();p.set_options({'simulated_datetime':'2030-01-02T23:30:00'})
    p.controls['service_time_mode'].buttons['range'].click();p.service_editor.end_edit.setText('01:00')
    host=MapDockHost(QWidget(),p.panels);host.resize(960,800);host.show();host.activate_panel('filters');qt_application.processEvents()
    axis=p.service_editor.time_axis;old_end=p.state()['service_end']
    QTest.mousePress(axis,Qt.MouseButton.LeftButton,pos=QPoint(round(axis._x(1410)),24))
    target=QPoint(round(axis._x(1380)),24)
    QTest.mouseMove(axis,target);QTest.mouseRelease(axis,Qt.MouseButton.LeftButton,pos=target)
    assert axis.values()[0]>axis.values()[1]
    assert abs(axis.values()[0]-1380)<=3
    assert p.service_editor.start_edit.text()==p.service_editor._text(axis.values()[0])
    assert p.state()['service_end']==old_end


def test_24_hour_endpoint_carries_date_once_and_remains_editable(qt_application):
    from map_panels import MapPanelSet
    p=MapPanelSet();p.set_options({'simulated_datetime':'2030-01-02T12:00:00'})
    p.controls['service_time_mode'].buttons['range'].click();p.service_editor.end_edit.setText('24:00')
    assert p.state()['service_end']=='2030-01-03T00:00:00'
    assert p.service_editor.end_edit.text()=='00:00'
    p.service_editor.end_edit.setText('01:00')
    assert p.state()['service_end']=='2030-01-03T01:00:00'


def test_network_core_filters_fit_top_of_formal_1440_height_without_smaller_fonts(qt_application):
    from map_panels import MapPanelSet
    from map_docking import MapDockHost
    p=MapPanelSet();p.set_options({'company_ids':[{'id':'a','name':'八连交通集团'}],
        'modes':[{'id':m,'name':n} for m,n in [('bus','公交'),('tram','有轨电车'),('trolley','无轨电车')]],
        'lines':[{'id':i,'name':str(i),'mode':'bus','company_id':'a','passengers':1,'profit':1,'service_matches':True} for i in range(13)],
        'simulated_datetime':'2013-05-23T23:59:00'})
    p.set_state({'service_time_mode':'range','service_start':'2013-05-23T23:30:00','service_end':'2013-05-24T01:00:00'})
    host=MapDockHost(QWidget(),p.panels);host.resize(1344,774);host.show();host.activate_panel('filters');qt_application.processEvents()
    panel=p.panels['filters'];panel.verticalScrollBar().setValue(0)
    assert panel.widget().minimumSizeHint().height()<=panel.viewport().height()
    assert p.line_list.height()>=3*(p.line_list.item(0).sizeHint().height()+6)
    assert p.line_list.item(0).font().pixelSize()==14


def test_editing_restored_time_does_not_replace_dates_with_current_week(qt_application):
    from map_panels import MapPanelSet
    p=MapPanelSet();p.set_options({'simulated_datetime':'2030-01-02T12:00:00'})
    p.set_state({'service_time_mode':'range','service_start':'2031-02-03T08:00:00','service_end':'2031-02-04T09:00:00'})
    p.service_editor.start_edit.setText('08:30')
    assert p.state()['service_start']=='2031-02-03T08:30:00'
    assert p.state()['service_end']=='2031-02-04T09:00:00'
    before=p.state();spy=QSignalSpy(p.stateChanged);p.service_editor.end_edit.setText('25:99')
    assert p.state()==before and spy.count()==0 and p.service_error.text()


def test_cross_midnight_axis_paints_two_short_ends_and_keeps_instant_end_disabled(qt_application):
    from map_panels import MapPanelSet
    from map_docking import MapDockHost
    p=MapPanelSet();p.set_options({'simulated_datetime':'2030-01-02T23:30:00'})
    p.controls['service_time_mode'].buttons['range'].click();editor=p.service_editor;editor.end_edit.setText('01:00')
    host=MapDockHost(QWidget(),p.panels);host.resize(960,800);host.show();host.activate_panel('filters');qt_application.processEvents()
    image=editor.time_axis.grab().toImage()
    ratio=image.devicePixelRatio()
    def color(x,y):return image.pixelColor(round(x*ratio),round(y*ratio)).name()
    assert color(editor.time_axis.width()/2,20)!='#0067c0'
    assert color(12,20)=='#0067c0'
    end=p.state()['service_end'];p.controls['service_time_mode'].buttons['instant'].click()
    assert not editor.end_edit.isEnabled() and not editor.time_axis.handles[1].isEnabled()
    p.controls['service_time_mode'].buttons['range'].click()
    assert editor.end_edit.isEnabled() and p.state()['service_end']==end


def test_instant_query_ignores_invalid_disabled_end_but_keeps_last_valid_range(qt_application):
    from map_panels import MapPanelSet
    p=MapPanelSet();p.set_options({'simulated_datetime':'2030-01-02T12:00:00'})
    p.controls['service_time_mode'].buttons['range'].click();old_end=p.state()['service_end']
    p.service_editor.end_edit.setText('bad')
    p.controls['service_time_mode'].buttons['instant'].click()
    assert p.state()['service_time_mode']=='instant' and p.state()['service_start']=='2030-01-02T12:00:00'
    assert p.state()['service_end']==old_end


def test_instant_weekday_handle_does_not_rewrite_disabled_restored_end_date(qt_application):
    from map_panels import MapPanelSet
    p=MapPanelSet();p.set_options({'simulated_datetime':'2030-01-02T12:00:00'})
    p.set_state({'service_time_mode':'range','service_start':'2031-02-03T08:00:00','service_end':'2031-02-04T09:00:00'})
    old_end=p.state()['service_end'];p.controls['service_time_mode'].buttons['instant'].click()
    QTest.keyClick(p.service_editor.week_axis.handles[0],Qt.Key.Key_Right)
    assert p.state()['service_end']==old_end
    p.controls['service_time_mode'].buttons['range'].click()
    assert p.state()['service_end']==old_end


def test_building_source_four_states_do_not_turn_partial_into_empty(qt_application):
    from map_preset_panels import PlanningPanel
    host=QWidget();host.resize(960,680);host.show()
    p=PlanningPanel(host);p.set_routes(catalog(),{99})
    cases=[(False,False,None,'线路信息暂不可用'),(True,True,[],'无服务线路'),
           (True,False,[],'线路信息暂不可用'),(True,False,[catalog()[0]],'部分线路不可用')]
    for known,complete,candidates,status in cases:
        building=SimpleNamespace(name='建筑',service_lines=SimpleNamespace(known=known,complete=complete,unresolved_refs=(),diagnostic='internal native detail'))
        p.open_building_menu(building,candidates,p.state()['selected_ids'],host.mapToGlobal(QPoint(30,30)))
        menu=p.building_menu
        assert menu.source_complete==complete and menu.status_label.text()==status
        assert 'internal' not in menu.status_label.text()
        if candidates:
            menu.select_all.click();assert p.state()['selected_ids']=={12,99}
        else:assert not menu.select_all.isEnabled()


def test_unresolved_references_never_become_named_selectable_or_visible_id_rows(qt_application):
    from map_preset_panels import PlanningPanel
    host=QWidget();host.resize(960,680);host.show()
    p=PlanningPanel(host);p.set_routes(catalog(),{99})
    building=SimpleNamespace(name='建筑',service_lines=SimpleNamespace(known=True,complete=True,route_ids=(),unresolved_refs=(808,808)))
    p.open_building_menu(building,[],{99},host.mapToGlobal(QPoint(30,30)))
    assert p.building_menu.line_list.count()==0
    assert p.building_menu.status_label.text()=='线路信息暂不可用'
    assert not p.building_menu.select_all.isEnabled() and p.state()['selected_ids']=={99}
