"""Actual output: square geography, complete text, pixels and vector PDF."""
from dataclasses import replace
from pathlib import Path
import pytest
from test_route_export_model import source


def request(**kwargs):
    from route_export_model import ExportOptions,build_export_request
    session,snapshot=source()
    return build_export_request(session,snapshot,42,ExportOptions(**kwargs))


@pytest.mark.parametrize('aspect,orientation',[('16:9','landscape'),('16:10','landscape'),
    ('3:2','landscape'),('A4','landscape'),('A4','portrait')])
def test_complete_layout_never_overlaps_map_or_silently_drops_fields(qt_application,aspect,orientation):
    from route_export_model import ALL_FIELDS
    from route_export_render import build_layout
    req=request(aspect=aspect,orientation=orientation,selected_fields=ALL_FIELDS)
    req=replace(req,information=replace(req.information,
        company_name='长公司名称交通集团及城市综合公共交通运营有限公司',route_name='503E 城市跨区快速公交线路'))
    layout=build_layout(req)
    x,y,w,h=layout.map_rect
    assert w==h
    if orientation=='portrait':assert y+h<=layout.info_rect[1]
    else:assert x+w<=layout.info_rect[0]
    drawn=' '.join(item.text for item in layout.text_items)
    assert req.information.company_name in drawn and req.information.route_name in drawn
    for _,_,rows in req.information.sections:
        for key,label,value in rows:
            assert label in drawn
            if key=='今日客流':assert value.removesuffix(' 人次') in drawn and '人次' in drawn
            else:assert value in drawn
    for item in layout.text_items:
        x,y,w,h=item.rect
        assert x>=layout.info_rect[0] and y>=0 and x+w<=layout.width and y+h<=layout.height
    ordered=sorted(layout.text_items,key=lambda i:i.rect[1])
    for first,second in zip(ordered,ordered[1:]):
        if first.rect[0]==second.rect[0]:assert first.rect[1]+first.rect[3]<=second.rect[1]+.1


def test_preview_dimensions_preserve_paper_aspect(qt_application):
    from route_export_render import preview
    image=preview(request(),(600,600))
    assert (image.width(),image.height())==(600,400)
    assert not image.isNull()


@pytest.mark.parametrize('fmt',['PNG','JPG','PDF'])
def test_outputs_are_real_decodable_files_with_resolution_or_vector_text(qt_application,tmp_path,fmt):
    from route_export_render import render_export
    req=request(format=fmt,width_mm=127,ppi=80)
    path=tmp_path/('route.'+fmt.lower())
    result=render_export(req,path)
    assert Path(result.path)==path and path.stat().st_size>100
    if fmt=='PDF':
        PdfReader=pytest.importorskip('pypdf',reason='PDF vector audit requires optional pypdf').PdfReader
        page=PdfReader(path).pages[0]
        content=page.get_contents().get_data()
        assert b' l' in content and b'BT' in content
        assert '503E' in page.extract_text().replace('\t','')
        assert len(page.images)==0  # This fixture has no logo: page is entirely vector.
        assert abs(float(page.mediabox.width)-360)<.1
    else:
        from PIL import Image
        with Image.open(path) as image:
            assert image.size==(400,267)
            assert abs(image.info['dpi'][0]-80)<.1


def test_cancellation_preserves_existing_destination_and_cleans_partial(qt_application,tmp_path):
    from route_export_model import ExportCancelled
    from route_export_render import render_export
    path=tmp_path/'out.png';path.write_bytes(b'previous')
    count=0
    def cancel():
        nonlocal count
        count+=1
        return count>3
    with pytest.raises(ExportCancelled):render_export(request(),path,cancel)
    assert path.read_bytes()==b'previous'
    assert list(tmp_path.iterdir())==[path]


def test_geometry_selection_survives_actual_paint_and_hides_other_direction(qt_application):
    from route_export_render import preview
    up=preview(request(direction='up',show_stops=False),(768,512))
    down=preview(request(direction='down',show_stops=False),(768,512))
    assert up!=down


def test_extreme_raster_rejected_before_full_image_allocation(qt_application,tmp_path):
    from route_export_render import render_export
    from route_export_model import ExportError
    with pytest.raises(ExportError):render_export(request(format='JPG',width_mm=400,ppi=600),tmp_path/'large.jpg')


def test_route_segment_joints_do_not_turn_white_in_actual_map(qt_application):
    from route_export_render import preview
    from map_model import MapRoute,MapSnapshot
    from route_export_model import ExportOptions,build_export_request
    a,b,c=(0.,0.,0.),(100.,0.,0.),(200.,0.,0.)
    route=MapRoute(42,'1',1,'owner','公司','bus',(),((a,b),(b,c)))
    req=build_export_request({'lines':[{'对象ID':42}]},MapSnapshot(routes=(route,)),42,
        ExportOptions(show_stops=False))
    image=preview(req,(1536,1024))
    # At the seam, line interior must match the adjacent interior. White caps
    # from separately cased segments otherwise punch a hole in the route.
    assert image.pixelColor(510,510)==image.pixelColor(505,510)


def test_streamed_png_tiles_match_the_unsegmented_preview(qt_application,tmp_path,monkeypatch):
    import route_export_render as renderer
    from PySide6.QtGui import QImage
    req=request(width_mm=127,ppi=80)
    monkeypatch.setattr(renderer,'STRIP_BYTES',400*4*(7+4))
    renderer.render_export(req,tmp_path/'tiles.png')
    actual=QImage(str(tmp_path/'tiles.png')).convertToFormat(QImage.Format.Format_RGB32)
    expected=renderer.preview(req,(400,267))
    assert actual==expected


def test_explicit_hide_logo_applies_to_an_already_resolved_brand(qt_application):
    from company_branding import CompanyBranding,RasterImage
    from route_export_render import preview
    brand=CompanyBranding('owner','公司','real',0xffff0000,0xffffffff,
        logo_image=RasterImage(1,1,b'\xff\0\0\xff'),logo_status='available')
    req=replace(request(logo_source='none'),branding=brand)
    image=preview(req,(600,400))
    assert image.text('logo_status')=='hidden'


def test_saved_logo_selection_does_not_reuse_an_already_resolved_custom_image(qt_application):
    from company_branding import CompanyBranding,RasterImage
    from route_export_render import preview
    brand=CompanyBranding('owner','公司','definitely-not-installed',0xffff0000,0xffffffff,
        logo_image=RasterImage(1,1,b'\xff\0\0\xff'),logo_status='custom')
    image=preview(replace(request(logo_source='save'),branding=brand),(600,400))
    assert image.text('logo_status')=='missing_asset'


def test_portrait_places_square_map_above_information_and_preserves_datetime_tokens(qt_application):
    from route_export_model import ALL_FIELDS,ExportOptions,build_export_request
    from route_export_render import build_layout
    session,snapshot=source()
    session['lines'][0].update({'开线日期':'2013-04-10 05:47','最近改线日期':'2013-04-21 05:48'})
    req=build_export_request(session,snapshot,42,ExportOptions(aspect='A4',orientation='portrait',selected_fields=ALL_FIELDS))
    layout=build_layout(req)
    values=[item for item in layout.text_items if item.text in ('2013-04-10 05:47','2013-04-21 05:48')]
    assert [item.display_text for item in values]==['2013-04-10\n05:47','2013-04-21\n05:48']
    assert layout.map_rect[1]+layout.map_rect[3]<=layout.info_rect[1]
    top=min(item.rect[1] for item in layout.text_items)
    bottom=max(item.rect[1]+item.rect[3] for item in layout.text_items)
    assert top>=layout.info_rect[1]
    assert bottom<layout.height


def test_widescreen_long_identity_with_all_fields_remains_complete(qt_application):
    from route_export_model import ALL_FIELDS,ExportOptions,build_export_request
    from route_export_render import build_layout
    from stats_style import initialize_theme
    initialize_theme(qt_application)
    session,snapshot=source()
    session['lines'][0].update({'线路车库':'八连交通集团公交车库12','开线日期':'2013-04-10 05:47',
        '最近改线日期':'2013-04-21 05:48','每周收入':13973.01,'每周支出':15779.87,
        '今日客流':8250,'平均客流':10016.93,'今日平均单班人次':97.06,'今日平均车公里人次':5.52})
    req=build_export_request(session,snapshot,42,ExportOptions(aspect='16:9',selected_fields=ALL_FIELDS))
    req=replace(req,information=replace(req.information,
        company_name='八连交通集团秋山市公共交通运营与城市跨区快速公交有限公司',
        route_name='503E 秋山城市跨区快速公交 · 东北枢纽—南岸综合交通中心'))
    layout=build_layout(req)
    assert req.information.route_name in [i.text for i in layout.text_items]
    assert req.information.company_name in [i.text for i in layout.text_items]
    assert max(i.rect[1]+i.rect[3] for i in layout.text_items)<layout.height


@pytest.mark.parametrize('bridge',[False,True])
def test_same_level_road_segment_casings_do_not_cut_across_saved_joints(qt_application,bridge):
    from map_model import MapRoad
    from route_export_render import preview
    req=request(show_stops=False)
    # Roads are split at an identical saved point. Sample the upper road
    # interior, away from the operating route, at and beside that joint.
    paths=(((0.,0.,80.),(100.,0.,80.)),((100.,0.,80.),(200.,0.,80.)))
    roads=tuple(MapRoad(i,'road','', (path,),road_class='express',express=True,width=16,
        bridge=bridge and i==2) for i,path in enumerate(paths,1))
    req=replace(req,snapshot=replace(req.snapshot,roads=roads))
    image=preview(req,(1536,1024))
    assert image.pixelColor(500,356)==image.pixelColor(490,356)
