"""Filters keep independent drafts until their own confirmation button."""
import pytest
from PySide6.QtCore import Qt, QPoint
from PySide6.QtTest import QSignalSpy, QTest


def panel():
    from map_panels import MapPanelSet
    p=MapPanelSet();p.set_options({'modes':[{'id':'bus','name':'公交'},{'id':'tram','name':'有轨电车'}],
        'company_ids':[{'id':'a','name':'甲公司'},{'id':'b','name':'乙公司'}],
        'simulated_datetime':'2030-01-02T23:30:00','passenger_label':'平均客流',
        'lines':[{'id':1,'name':'1路','mode':'bus','company_id':'a','passengers':0},
                 {'id':2,'name':'2路','mode':'tram','company_id':'b','passengers':50000},
                 {'id':3,'name':'3路','mode':'bus','company_id':'a','passengers':None}]})
    return p


def uncheck(p,key,identity):
    view=p.group_lists[key]
    next(view.item(i) for i in range(view.count()) if view.item(i).data(Qt.ItemDataRole.UserRole)==identity).setCheckState(Qt.CheckState.Unchecked)


def test_confirming_one_filter_applies_only_that_block_and_folds_it(qt_application):
    p=panel();spy=QSignalSpy(p.stateChanged)
    uncheck(p,'company_ids','b');uncheck(p,'modes','tram')
    assert p.state()['company_ids']=={'a','b'} and p.state()['modes']=={'bus','tram'} and spy.count()==0
    p.filter_sections['company_ids'].set_expanded(True)
    p.filter_apply_buttons['company_ids'].click()
    assert p.state()['company_ids']=={'a'} and p.state()['modes']=={'bus','tram'} and spy.count()==1
    assert not p.filter_sections['company_ids'].is_expanded()
    assert p.group_lists['modes'].item(1).checkState()==Qt.CheckState.Unchecked
    p.filter_apply_buttons['modes'].click()
    assert p.state()['modes']=={'bus'} and spy.count()==2
    snapshot=spy.at(0)[0];snapshot['modes'].clear();assert p.state()['modes']=={'bus'}


def test_pending_manual_selection_survives_display_and_option_refresh_without_being_applied(qt_application):
    p=panel();spy=QSignalSpy(p.stateChanged);p.manual_none.click()
    assert p.state()['manual_line_ids']=={1,2,3} and spy.count()==0
    p.controls['stop_names'].click()
    assert spy.count()==1 and spy.at(0)[0]['manual_line_ids']=={1,2,3}
    p.set_options(dict(p._options,passenger_label='今日客流'))
    assert all(p.line_list.item(i).checkState()==Qt.CheckState.Unchecked for i in range(3))
    p.filter_apply_buttons['manual_line_ids'].click()
    assert p.state()['manual_line_ids']==set() and spy.count()==2


def test_unfinished_precise_input_and_invalid_time_survive_another_block_confirmation(qt_application):
    p=panel();p.controls['passenger_min'].setText('12.345');p.controls['passenger_max'].setText('45.678')
    p.controls['service_time_mode'].buttons['range'].click();p.service_editor.end_edit.setText('bad')
    uncheck(p,'modes','tram');p.filter_apply_buttons['modes'].click();p.set_options(p._options)
    assert p.controls['passenger_min'].text()=='12.345' and p.controls['passenger_max'].text()=='45.678'
    assert p.service_editor.end_edit.text()=='bad' and p.state()['service_time_mode']=='off'
    p.filter_apply_buttons['passengers'].click()
    assert p.state()['passenger_min']==12.34 and p.state()['passenger_max']==45.67


def test_programmatic_restore_is_silent_and_resets_pending_edits(qt_application):
    p=panel();uncheck(p,'modes','tram');spy=QSignalSpy(p.stateChanged)
    p.set_state({'modes':{'tram'},'passenger_min':12.34,'passenger_max':45.67})
    assert p.state()['modes']=={'tram'} and spy.count()==0
    assert p.controls['passenger_min'].text()=='12.34' and p.controls['passenger_max'].text()=='45.67'
    p.filter_apply_buttons['modes'].click();assert p.state()['modes']=={'tram'} and spy.count()==0


def test_default_range_displays_zero_infinity_but_does_not_convert_unknown_passengers_to_zero(qt_application):
    p=panel();spy=QSignalSpy(p.stateChanged)
    assert p.controls['passenger_min'].text()=='0' and p.controls['passenger_max'].text()=='∞'
    assert p.state()['passenger_min'] is None and p.state()['passenger_max'] is None and p.line_list.count()==3
    p.filter_apply_buttons['passengers'].click()
    assert p.state()['passenger_min']==0 and p.state()['passenger_max'] is None and spy.count()==1
    assert [p.line_list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(p.line_list.count())]==[1,2]


def test_passenger_range_has_separate_fifty_thousand_and_infinity_keyboard_positions(qt_application):
    p=panel();editor=p.passenger_editor;spy=QSignalSpy(p.stateChanged)
    assert editor.axis.values()==(0,editor.axis.maximum)
    QTest.keyClick(editor.axis.handles[1],Qt.Key.Key_Left)
    assert p.controls['passenger_max'].text()=='50000' and p.state()['passenger_max'] is None and spy.count()==0
    p.filter_apply_buttons['passengers'].click();assert p.state()['passenger_max']==50000
    QTest.keyClick(editor.axis.handles[1],Qt.Key.Key_Right)
    p.filter_apply_buttons['passengers'].click();assert p.state()['passenger_max'] is None and spy.count()==2


def test_precise_typed_bounds_are_not_rounded_to_slider_thousands_and_invalid_ranges_do_not_apply(qt_application):
    p=panel();spy=QSignalSpy(p.stateChanged)
    p.controls['passenger_min'].setText('2155.599');p.controls['passenger_max'].setText('12345.678')
    p.filter_apply_buttons['passengers'].click()
    assert p.state()['passenger_min']==2155.59 and p.state()['passenger_max']==12345.67 and spy.count()==1
    p.filter_sections['passengers'].set_expanded(True)
    p.controls['passenger_max'].setText('2000');p.filter_apply_buttons['passengers'].click()
    assert p.state()['passenger_max']==12345.67 and spy.count()==1 and p.filter_sections['passengers'].is_expanded()
    assert p.passenger_editor.error_label.text()


def test_passenger_slider_cannot_cross_or_put_the_lower_bound_at_infinity(qt_application):
    p=panel();axis=p.passenger_editor.axis
    QTest.keyClick(axis.handles[0],Qt.Key.Key_End)
    assert axis.values()==(axis.finite_maximum,axis.maximum) and p.controls['passenger_min'].text()=='50000'
    QTest.keyClick(axis.handles[1],Qt.Key.Key_Home)
    assert axis.values()==(axis.finite_maximum,axis.finite_maximum) and p.controls['passenger_max'].text()=='50000'


def test_operating_time_keeps_cross_midnight_as_draft_until_confirmed(qt_application):
    p=panel();spy=QSignalSpy(p.stateChanged)
    p.controls['service_time_mode'].buttons['range'].click();p.service_editor.end_edit.setText('01:00')
    assert p.state()['service_time_mode']=='off' and spy.count()==0
    p.filter_apply_buttons['service'].click()
    assert p.state()['service_start']=='2030-01-02T23:30:00'
    assert p.state()['service_end']=='2030-01-03T01:00:00' and spy.count()==1
    assert not p.filter_sections['service'].is_expanded()


def test_invalid_service_draft_stays_open_and_disabled_end_does_not_block_instant(qt_application):
    p=panel();spy=QSignalSpy(p.stateChanged)
    p.filter_sections['service'].set_expanded(True)
    p.controls['service_time_mode'].buttons['range'].click();p.service_editor.end_edit.setText('bad')
    p.filter_apply_buttons['service'].click()
    assert spy.count()==0 and p.state()['service_time_mode']=='off' and p.filter_sections['service'].is_expanded()
    p.controls['service_time_mode'].buttons['instant'].click();p.filter_apply_buttons['service'].click()
    assert spy.count()==1 and p.state()['service_time_mode']=='instant' and not p.service_editor.end_edit.isEnabled()


@pytest.mark.parametrize('color',['interval','passengers'])
def test_numeric_color_change_hides_stops_atomically_and_preserves_pending_filters_and_name_preference(qt_application,color):
    p=panel();p.set_state({'stop_names':True});uncheck(p,'modes','tram');spy=QSignalSpy(p.stateChanged)
    p._changed('color_by',color)
    assert spy.count()==1 and p.state()['color_by']==color and p.state()['stops'] is False
    assert p.state()['stop_names'] is True and spy.at(0)[0]['modes']=={'bus','tram'}
    p.controls['stops'].click();assert p.state()['stops'] is True
    p._changed('color_by',color);p.set_options(p._options)
    assert p.state()['stops'] is True and spy.count()==2
    p.set_state({'color_by':color,'stops':True});assert p.state()['stops'] is True


def test_service_boundary_title_and_input_rows_stay_above_the_full_width_time_axis(qt_application):
    from map_docking import MapDockHost
    from PySide6.QtWidgets import QWidget
    p=panel();p.filter_sections['service'].set_expanded(True)
    p.controls['service_time_mode'].buttons['range'].click()
    host=MapDockHost(QWidget(),p.panels);host.resize(960,680);host.show();host.activate_panel('filters')
    qt_application.processEvents();editor=p.service_editor
    for key in ('start','end'):
        label=editor.labels[key];edit=getattr(editor,key+'_edit')
        assert label.mapTo(editor,QPoint(0,label.height())).y()<=edit.mapTo(editor,QPoint(0,0)).y()
        assert edit.mapTo(editor,QPoint(0,edit.height())).y()<editor.time_axis.y()
    assert editor.time_axis.width()>=editor.width()-2 and editor.time_axis.handles[1].isEnabled()


def test_filter_headers_align_title_left_arrow_right_and_profit_has_no_suffix(qt_application):
    from map_docking import MapDockHost
    from PySide6.QtWidgets import QWidget
    p=panel();host=MapDockHost(QWidget(),p.panels);host.resize(960,680);host.show();host.activate_panel('filters')
    qt_application.processEvents()
    for section in p.filter_sections.values():
        assert section.title_label.x()<section.width()/3
        assert section.arrow_label.mapTo(section,QPoint()).x()>section.width()*2/3
        expanded=section.is_expanded();section.toggle.click()
        assert section.is_expanded()!=expanded
    assert p.filter_sections['profit_statuses'].title_label.text()=='盈亏'


def test_filter_summaries_show_applied_criteria_and_combined_count_only(qt_application):
    p=panel()
    assert all(section.summary_label.text()=='' for section in p.filter_sections.values())
    uncheck(p,'modes','tram')
    assert p.filter_sections['modes'].summary_label.text()==''
    p.filter_apply_buttons['modes'].click()
    assert p.filter_sections['modes'].summary_label.text()=='筛选制式：公交 已选：2条'
    p.set_result_count(22)
    assert p.filter_sections['modes'].summary_label.text()=='筛选制式：公交 已选：22条'
    p.set_state({'modes':{'bus','tram'}})
    assert p.filter_sections['modes'].summary_label.text()==''


def test_service_summary_uses_weekday_range_and_empty_criteria_remain_blank(qt_application):
    p=panel();p.controls['service_time_mode'].buttons['range'].click()
    p.service_editor.start_edit.setText('17:00');p.service_editor.end_edit.setText('18:00')
    p.service_editor._weekday_changed(2,2)
    assert p.filter_sections['service'].summary_label.text()==''
    p.filter_apply_buttons['service'].click();p.set_result_count(22)
    assert p.filter_sections['service'].summary_label.text()=='周三17:00-18:00 已选：22条'
    p.service_editor.start_edit.setText('23:30');p.service_editor.end_edit.setText('01:00')
    p.filter_apply_buttons['service'].click()
    assert p.filter_sections['service'].summary_label.text()=='周三23:30-周四01:00 已选：22条'
    p.controls['service_time_mode'].buttons['off'].click();p.filter_apply_buttons['service'].click()
    assert p.filter_sections['service'].summary_label.text()==''


def test_explicit_zero_infinity_and_empty_manual_selection_have_real_summaries(qt_application):
    p=panel();p.manual_none.click();p.filter_apply_buttons['passengers'].click()
    assert p.filter_sections['passengers'].summary_label.text()=='筛选客流：0-∞人次 已选：2条'
    assert p.filter_sections['manual_line_ids'].summary_label.text()==''
    p.filter_apply_buttons['manual_line_ids'].click()
    assert p.filter_sections['manual_line_ids'].summary_label.text()=='筛选线路：0条 已选：0条'
    assert p.filter_sections['passengers'].summary_label.text().endswith('已选：0条')
    p.reset_filters.click()
    assert all(section.summary_label.text()=='' for section in p.filter_sections.values())


def test_passenger_power_mapping_expands_the_middle_range_without_changing_typed_values(qt_application):
    p=panel();axis=p.passenger_editor.axis
    p.passenger_editor.set_values(5000,15000)
    low,high=axis.values()
    assert axis.maximum*.25<low<axis.maximum*.4 and axis.maximum*.45<high<axis.maximum*.6
    assert (high-low)/axis.finite_maximum>.22
    assert p.controls['passenger_min'].text()=='5000' and p.controls['passenger_max'].text()=='15000'
    axis._change(0,axis.finite_maximum//2)
    assert p.controls['passenger_min'].text()=='12500'
    assert p.state()['passenger_min'] is None
    p.passenger_editor.set_values(2155.59,12345.67)
    axis._change(1,axis.position(15000))
    assert p.controls['passenger_min'].text()=='2155.59'


def test_compact_footer_buttons_and_service_handles_fit_a_narrow_filter_column(qt_application):
    from PySide6.QtWidgets import QWidget
    from map_docking import MapDockHost
    from stats_controls import button_text_size
    p=panel();p.set_options(dict(p._options,passenger_date='2030-01-02'))
    host=MapDockHost(QWidget(),p.panels);host.resize(960,680);host.show();host.activate_panel('filters')
    p.filter_sections['passengers'].set_expanded(True);p.filter_sections['service'].set_expanded(True)
    p.controls['service_time_mode'].buttons['range'].click();qt_application.processEvents()
    assert p.passenger_date.text()=='平均客流'
    label=p.passenger_date;button=p.filter_apply_buttons['passengers']
    assert label.parentWidget() is button.parentWidget()
    assert abs(label.geometry().center().y()-button.geometry().center().y())<=2
    assert label.x()<button.x()
    p.set_options(dict(p._options,passenger_label='今日客流',passenger_source='today'))
    assert label.text()=='2030-01-02'
    for button in (p.manual_all,p.manual_none):
        assert button.width()>=button_text_size(button).width()
        assert button.geometry().right()<button.parentWidget().width()
    for axis in (p.service_editor.week_axis,p.service_editor.time_axis):
        for handle in axis.handles:
            assert axis.rect().contains(handle.geometry())
            if axis.show_endpoint_labels:assert handle.y()>=16


def test_short_service_summary_stays_one_line_when_it_fits(qt_application):
    from PySide6.QtWidgets import QWidget
    from map_docking import MapDockHost
    p=panel();host=MapDockHost(QWidget(),p.panels);host.resize(960,680);host.show();host.activate_panel('filters')
    p.set_state({'service_time_mode':'range','service_start':'2030-01-02T17:00:00','service_end':'2030-01-02T18:00:00'})
    p.filter_sections['service'].set_expanded(False);p.set_result_count(22);qt_application.processEvents()
    label=p.filter_sections['service'].summary_label
    assert label.text()=='周三17:00-18:00 已选：22条'
    assert label.fontMetrics().horizontalAdvance(label.text())<=label.width()
    assert label.height()<=label.fontMetrics().height()+4


def test_manual_bulk_buttons_remain_inside_the_smallest_supported_panel(qt_application):
    from PySide6.QtWidgets import QWidget
    from map_docking import MapDockHost
    p=panel();host=MapDockHost(QWidget(),p.panels);host.resize(960,680);host.show()
    host.restore_layout({'dock_width':240,'active':'filters'})
    for _ in range(3):qt_application.processEvents()
    viewport=p.panels['filters'].viewport()
    for button in (p.manual_all,p.manual_none):
        left=button.mapTo(viewport,QPoint()).x()
        assert left>=0 and left+button.width()<=viewport.width()


@pytest.mark.parametrize('minimum,maximum,moving',[
    (2155.59,12345.67,0), (2150.01,12345.67,1),
    (0.03,0.18,0), (0.06,0.22,1),
])
def test_slider_contact_clamps_against_the_other_precise_bound_and_confirms(qt_application,minimum,maximum,moving):
    p=panel();editor=p.passenger_editor;spy=QSignalSpy(p.stateChanged)
    editor.set_values(minimum,maximum)
    stationary_text=(editor.min_edit,editor.max_edit)[1-moving].text()
    editor.axis._change(moving,editor.axis.values()[1-moving])
    values=editor.values()
    assert values is not None and values[0]<=values[1]
    assert (editor.min_edit,editor.max_edit)[1-moving].text()==stationary_text
    p.filter_apply_buttons['passengers'].click()
    assert (p.state()['passenger_min'],p.state()['passenger_max'])==values
    assert spy.count()==1


def test_finite_slider_return_preserves_a_typed_bound_above_the_slider_range(qt_application):
    p=panel();editor=p.passenger_editor;editor.set_values(60000,70000)
    editor.axis._change(1,editor.axis.maximum)
    assert editor.values()==(60000,None)
    editor.axis._change(1,editor.axis.finite_maximum)
    assert editor.values()==(60000,60000) and editor.min_edit.text()=='60000'
    p.filter_apply_buttons['passengers'].click()
    assert p.state()['passenger_min']==p.state()['passenger_max']==60000
