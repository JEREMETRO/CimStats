"""Whole-shell capacity contracts; component tests alone cannot prove this budget."""
import copy
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings, QRect, Qt
from PySide6.QtTest import QTest
from PySide6.QtCore import QPoint

import desktop_app
from report_model import load_session


def entries(count):
    return [dict(time=f'{(300+i*6)//60%24:02d}:{(300+i*6)%60:02d}',
                 next_day=300+i*6>=1440,vehicle_type='任意') for i in range(count)]


@pytest.fixture
def visual_window(qt_application,monkeypatch,tmp_path):
    monkeypatch.setattr(desktop_app,'QSettings',lambda *a:QSettings(str(tmp_path/'qa.ini'),QSettings.Format.IniFormat))
    monkeypatch.setattr(desktop_app.MainWindow,'check_install',lambda self:None)
    w=desktop_app.MainWindow()
    data=load_session(Path(__file__).resolve().parents[1]/'exports','望春市_test_运行时')
    data.update(save_path='测试数据.save',save_key='capacity-test',history=[])
    w.on_completed(data)
    w.show();w.navigate(1)
    QTest.qWait(200)
    # Measured 100% native DWM visible frame: 4px horizontal border and 60px
    # title/bottom. Offscreen frame margins are smaller and cannot prove this budget.
    w.resize(1436,900)
    QTest.qWait(100)
    assert hasattr(w,'lines_page')
    assert data['lines']
    yield w
    w.close();w.deleteLater()


@pytest.mark.parametrize('count',[0,1,50,72,100,140])
def test_actual_whole_shell_has_capacity_without_scroll(visual_window,count,qt_application):
    w=visual_window;p=w.lines_page
    line=copy.deepcopy(w.data['lines'][0]);line.pop('时刻表',None)
    line['班次']={'周一至周四':entries(count)}
    line['日组']=tuple(line['班次'])
    w.show_line(line);QTest.qWait(100)
    panel=p.schedule_panel;matrix=panel.matrix
    assert matrix.total_count==count and matrix.display_count==count
    assert panel.display_label.text()==f'显示 {count} / {count}'
    assert p.right_scroll.verticalScrollBar().maximum()==0
    assert p.right_scroll.horizontalScrollBar().maximum()==0
    assert panel.matrix_scroll.verticalScrollBar().maximum()==0
    assert matrix.font().pixelSize()==14
    assert w.legacy_header.isVisible() and not w.line_footer.isVisible()
    assert w.legacy_header.height()==44 and w.page_title.font().pixelSize()==29
    assert w.line_table.font().pixelSize()==14
    assert p.height()>=818 and p.detail.height()==348 and panel.height()>=458
    assert len(w.fact_cards)==9 and all(c.isVisible() for c in w.fact_cards)
    assert all(c.height()==86 for c in w.fact_cards)
    if count:
        for i in range(count):
            cell=matrix.cell_rect(i)
            assert p.rect().contains(QRect(matrix.mapTo(p,cell.topLeft()),cell.size()))
            assert cell.height()>=matrix.fontMetrics().height()
        assert matrix.columns==10
    if count==140:
        from stats_tokens import FONT_FAMILY
        assert matrix.font().family()==FONT_FAMILY, 'timetable font differs from statistics tab'
        assert matrix.cell_rect(139).y()==13*matrix.row_height


def test_compact_fact_text_has_vertical_room(visual_window):
    w=visual_window;w.line_clicked(0,0);QTest.qWait(100)
    for card in w.fact_cards:
        for name in ['label','value','note_label','note_value']:
            label=getattr(card,name)
            if label.text():
                assert label.height()>=label.fontMetrics().height(), f'{card.label.text()} {name} clips vertically'
        assert not card.value.geometry().intersects(card.note_label.geometry()), f'{card.label.text()} rows overlap'
        assert not card.value.geometry().intersects(card.note_value.geometry()), f'{card.label.text()} rows overlap'
        if card.note_label.text():
            assert card.note_value.x()-card.note_label.geometry().right()-1==8, (card.label.text(),card.note_label.text(),card.note_label.geometry(),card.note_value.geometry(),card.note_label.isVisible(),card.note_value.isVisible(),card.note_value.parentWidget() is card)
            assert card.note_value.alignment() & Qt.AlignmentFlag.AlignLeft


def test_folded_information_gives_200_departures_without_scroll_and_restores_cards(visual_window):
    w=visual_window;p=w.lines_page
    line=copy.deepcopy(w.data['lines'][0]);line.pop('时刻表',None)
    line['班次']={'周一至周四':entries(200)};line['日组']=tuple(line['班次'])
    w.show_line(line);QTest.qWait(100)
    p.set_schedule_expanded(True,animated=False);QTest.qWait(400)
    panel=p.schedule_panel;matrix=panel.matrix
    assert p.schedule_expanded and panel.expanded and not p.detail.isVisible()
    assert matrix.capacity==200 and matrix.minimum_row_height==24 and matrix.row_height==min(30,max(24,matrix.height()//20)) and matrix.display_count==200
    assert 28<=matrix.row_height<=30 and 20*matrix.row_height<=matrix.height()
    assert matrix.row_offset==0 and matrix.cell_rect(0).top()==0
    assert 0<=matrix.height()-20*matrix.row_height<30
    assert matrix.mapTo(panel,matrix.cell_rect(0).topLeft()).y()-(panel.summary_host.y()+panel.summary_host.height())==12
    assert panel.group_host.y()>=panel.title_label.y()+panel.title_label.height()+12
    assert all(value.font().pixelSize()==21 and value.width()>=value.fontMetrics().horizontalAdvance(value.text())
               for value in panel.summary_values.values())
    assert panel.display_label.text()=='显示 200 / 200'
    assert p.right_scroll.verticalScrollBar().maximum()==0
    assert panel.matrix_scroll.verticalScrollBar().maximum()==0
    assert p.right_scroll.viewport().rect().contains(QRect(matrix.mapTo(p.right_scroll.viewport(),matrix.cell_rect(199).topLeft()),matrix.cell_rect(199).size()))
    assert matrix.entries[-1]['time']=='00:54' and matrix.entries[-1]['next_day']
    panel.expansion_button.click();QTest.qWait(400)
    assert not p.schedule_expanded and p.detail.isVisible()
    assert matrix.capacity==140 and len(w.fact_cards)==9 and all(c.isVisible() and c.height()==86 for c in w.fact_cards)
    p.fact_fold_button.click();QTest.qWait(400)
    assert p.schedule_expanded and matrix.display_count==200
    panel.expansion_button.click();QTest.qWait(400)
    assert p.detail.isVisible() and all(c.isVisible() for c in w.fact_cards)


def test_separate_peak_summaries_backgrounds_and_all_day_order(visual_window):
    w=visual_window
    line=copy.deepcopy(w.data['lines'][0]);line.pop('时刻表',None)
    line['班次']={'周一至周四':[dict(time=f'{m//60:02d}:{m%60:02d}',vehicle_type='任意') for m in range(0,1440,10)]}
    line['日组']=tuple(line['班次']);w.show_line(line);QTest.qWait(100)
    panel=w.schedule_panel;matrix=panel.matrix
    assert set(panel.summary_values)=={'first','last','count','morning_peak','evening_peak','offpeak','night'}
    assert panel.summary['all_day'] and matrix.entries[0]['time']=='00:00'
    assert panel.summary_values['morning_peak'].text()=='10m0s'
    assert panel.summary_values['evening_peak'].text()=='10m0s'
    morning=next(e for e in matrix.entries if e.get('morning_peak'))
    evening=next(e for e in matrix.entries if e.get('evening_peak'))
    assert matrix.background_color(morning)!=matrix.background_color(evening)


def test_overlay_selection_reverse_and_navigation_do_not_change_detail_budget(visual_window):
    w=visual_window;p=w.lines_page
    w.line_table.sortItems(7,Qt.SortOrder.DescendingOrder);w.line_clicked(0,0)
    key=w.selected_key
    detail=p.right_scroll.geometry()
    w.refresh_lines()
    assert w.line_table.item(w.line_table.currentRow(),0).data(Qt.ItemDataRole.UserRole)==key
    p.set_expanded(True,animated=False)
    assert [i for i in range(14) if not w.line_table.isColumnHidden(i)] == [i for i in range(14) if i != 4]
    assert p.right_scroll.geometry()==detail
    p.set_expanded(False,animated=False)
    for expanded in [True,False,True,False]:
        p.set_expanded(expanded);QTest.qWait(30)
    QTest.qWait(350)
    assert p.left.width()==p._compact_width()
    assert p.right_scroll.geometry()==detail
    p.set_expanded(True);QTest.qWait(30)
    w.navigate(0);w.navigate(1);QTest.qWait(350)
    assert p.left.geometry()==p._left_rect()
    assert w.selected_key==key


def test_narrow_page_retains_fields_and_reaches_last_departure(visual_window):
    w=visual_window;p=w.lines_page
    line=copy.deepcopy(w.data['lines'][0]);line.pop('时刻表',None)
    line['班次']={'周一至周四':entries(140)}
    line['日组']=tuple(line['班次'])
    w.show_line(line);w.resize(920,680);QTest.qWait(250)
    assert len(w.fact_cards)==9 and all(c.isVisible() for c in w.fact_cards)
    assert p.schedule_panel.matrix.total_count==140
    garage=next(c for c in w.fact_cards if c.label.text()=='线路车库')
    wrapped=garage.value.fontMetrics().boundingRect(garage.value.contentsRect(),
        int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap),garage.value.text())
    assert garage.value.fontMetrics().height()<wrapped.height()<=garage.value.height(), 'narrow garage does not show both full lines'
    assert p.right_scroll.verticalScrollBar().maximum()>0
    line['班次']['周一至周四']=entries(200)
    w.show_line(line);p.set_schedule_expanded(True,animated=False);QTest.qWait(250)
    assert p.schedule_panel.matrix.total_count==200 and not p.detail.isVisible()
    p.right_scroll.verticalScrollBar().setValue(p.right_scroll.verticalScrollBar().maximum())
    p.right_scroll.horizontalScrollBar().setValue(p.right_scroll.horizontalScrollBar().maximum())
    QTest.qWait(100)
    matrix=p.schedule_panel.matrix;last=matrix.cell_rect(199)
    viewport=p.right_scroll.viewport()
    point=matrix.mapTo(viewport,last.bottomRight())
    assert viewport.rect().contains(point), 'narrow viewport cannot reach 200th departure'


def test_tooltip_is_three_lines_with_independent_duplicate_numbers(visual_window):
    w=visual_window
    line=copy.deepcopy(w.data['lines'][0]);line.pop('时刻表',None)
    line['班次']={'周一至周四':[
        dict(time='23:50',vehicle_type='小型',原始备注='内部字段'),
        dict(time='00:10',vehicle_type='大型',next_day=True),
        dict(time='23:50',vehicle_type='中型')]}
    line['日组']=tuple(line['班次'])
    w.show_line(line);QTest.qWait(100)
    matrix=w.schedule_panel.matrix
    tips=[matrix.tooltip_for(i) for i in range(3)]
    assert all(len(t.splitlines())==3 for t in tips)
    assert all(str(i+1) in t.splitlines()[0] for i,t in enumerate(tips))
    assert '23:50' in tips[0] and '23:50' in tips[1]
    assert '次日00:10' in tips[2]
    assert '大型' in tips[2]
    assert not any('内部字段' in t or '原始备注' in t for t in tips)


def test_hover_elevation_keeps_whole_shell_geometry_and_opacity(visual_window):
    w=visual_window;w.line_clicked(0,0);QTest.qWait(100)
    p=w.lines_page;card=w.fact_cards[0]
    controller=getattr(card,'_card_elevation',None)
    assert controller is not None
    before=[c.geometry() for c in w.fact_cards];effect=p.graphicsEffect()
    QTest.mouseMove(card,card.rect().center());QTest.qWait(250)
    assert controller.level>.9
    assert before==[c.geometry() for c in w.fact_cards]
    assert p.graphicsEffect() is effect


def test_requested_full_labels_and_same_row_week_tabs(visual_window):
    w=visual_window;p=w.lines_page
    w.line_clicked(0,0);QTest.qWait(150)
    garage=next(c for c in w.fact_cards if c.label.text()=='线路车库')
    assert garage.value.wordWrap(), 'garage still paints one elided line'
    bounds=garage.value.fontMetrics().boundingRect(garage.value.contentsRect(),
        int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap),garage.value.text())
    assert bounds.height()<=garage.value.contentsRect().height(), 'full garage text clips vertically'
    assert p.line_columns_button.width()>=p.line_columns_button.fontMetrics().horizontalAdvance('显示列')+48
    assert p.line_count.y()>=p.line_table.geometry().bottom(), 'filter count still consumes dropdown width'
    assert p.list_footer.text().startswith('选中：') and '共 ' not in p.list_footer.text()
    panel=p.schedule_panel
    title_center=panel.title_label.mapTo(panel,QPoint(0,panel.title_label.height()//2)).y()
    tabs_center=panel.group_host.mapTo(panel,QPoint(0,panel.group_host.height()//2)).y()
    assert abs(title_center-tabs_center)<=2, 'week tabs still occupy the following row'


def test_default_140_uses_height_released_by_lifted_tabs(visual_window):
    w=visual_window;p=w.lines_page
    line=copy.deepcopy(w.data['lines'][0]);line.pop('时刻表',None)
    line['班次']={'周一至周四':entries(140)};line['日组']=tuple(line['班次'])
    w.show_line(line);QTest.qWait(150)
    matrix=p.schedule_panel.matrix
    assert matrix.display_count==140 and matrix.row_height>=22
    assert matrix.font().pixelSize()==14
    assert p.right_scroll.verticalScrollBar().maximum()==0
