"""Page refreshes must preserve default intent separately from visible checks."""
import json
import pytest
from PySide6.QtCore import QSettings
from map_page import MapPage
from map_model import MapBuilding,MapSnapshot,GroupFunctionCount,SOCIAL_GROUPS


def snapshot(*groups):
    capacity=tuple(GroupFunctionCount(group,10 if group in groups else 0,0,0)
                   for group in SOCIAL_GROUPS)
    buildings=(MapBuilding(1,'depot','depot',(0.,0.,0.),category='transport'),)
    if groups:
        buildings+=(MapBuilding(2,'house','house',(10.,0.,10.),category='residential',
                                function_capacities=capacity),)
    return MapSnapshot(buildings=buildings,bounds=(0.,0.,20.,20.))


def saved_classes(settings):
    return json.loads(settings.value('map/presets/A'))['planning']['query']['building_classes']


def test_default_selection_survives_zero_options_then_new_population(qt_application,tmp_path):
    settings=QSettings(str(tmp_path/'default.ini'),QSettings.Format.IniFormat)
    page=MapPage(settings)
    try:
        page.set_session({'save_key':'A'});page.set_preset('planning');page.set_snapshot(snapshot())
        assert page.planning_panel.state()['building_classes']==set()
        assert saved_classes(settings) is None
        page._sync_preset_panels();page.set_snapshot(snapshot('BlueCollar'))
        assert page.planning_panel.state()['building_classes']=={'BlueCollar'}
        assert page.planning_panel.class_grid.buttons['BlueCollar'].isChecked()
        assert {building.id for building in page.result.snapshot.buildings}=={1,2}
        assert page._current_state()['building_classes'] is None and saved_classes(settings) is None
        page.set_preset('network');page.set_preset('planning')
        page.set_snapshot(snapshot('BlueCollar','Student'))
        assert page.planning_panel.state()['building_classes']=={'BlueCollar','Student'}
        assert saved_classes(settings) is None
    finally:page.close()


def test_user_clear_survives_empty_options_refresh_and_restore(qt_application,tmp_path):
    settings=QSettings(str(tmp_path/'empty.ini'),QSettings.Format.IniFormat)
    page=MapPage(settings)
    try:
        page.set_session({'save_key':'A'});page.set_preset('planning')
        page.set_snapshot(snapshot('BlueCollar'))
        page.planning_panel.class_grid.buttons['BlueCollar'].click()
        assert saved_classes(settings)==[]
        page.set_snapshot(snapshot());page._sync_preset_panels()
        page.set_snapshot(snapshot('BlueCollar','Student'))
        assert page.planning_panel.state()['building_classes']==set()
        assert {building.id for building in page.result.snapshot.buildings}=={1}
        assert saved_classes(settings)==[]
    finally:page.close()
    restored=MapPage(settings)
    try:
        restored.set_session({'save_key':'A'});restored.set_preset('planning')
        restored.set_snapshot(snapshot('BlueCollar'))
        assert restored.planning_panel.state()['building_classes']==set()
        assert saved_classes(settings)==[]
        assert {building.id for building in restored.result.snapshot.buildings}=={1}
    finally:restored.close()


@pytest.mark.parametrize('preference',[None,[]])
def test_saved_default_and_explicit_empty_restore_differently_after_zero_options(qt_application,tmp_path,preference):
    settings=QSettings(str(tmp_path/'restore.ini'),QSettings.Format.IniFormat)
    settings.setValue('map/presets/A',json.dumps({'planning':{'query':{'building_classes':preference}}}))
    page=MapPage(settings)
    try:
        page.set_session({'save_key':'A'});page.set_preset('planning');page.set_snapshot(snapshot())
        page.set_session({'save_key':'B'});page.set_session({'save_key':'A'})
        page.set_snapshot(snapshot('BlueCollar'))
        expected={'BlueCollar'} if preference is None else set()
        assert page.planning_panel.state()['building_classes']==expected
        assert saved_classes(settings)==preference
        assert {building.id for building in page.result.snapshot.buildings}==({1,2} if preference is None else {1})
    finally:page.close()
