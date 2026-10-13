"""Actual output: fitted geography, complete text, pixels and vector PDF."""
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
    assert w>0 and h>0
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
    from route_export_render import preview,build_layout
    from map_model import MapRoute,MapSnapshot
    from route_export_model import ExportOptions,build_export_request
    a,b,c=(0.,0.,0.),(100.,0.,0.),(200.,0.,0.)
    route=MapRoute(42,'1',1,'owner','公司','bus',(),((a,b),(b,c)))
    req=build_export_request({'lines':[{'对象ID':42}]},MapSnapshot(routes=(route,)),42,
        ExportOptions(show_stops=False))
    image=preview(req,(1536,1024))
    # At the seam, line interior must match the adjacent interior. White caps
    # from separately cased segments otherwise punch a hole in the route.
    mx,my,mw,mh=build_layout(req).map_rect
    center_x,center_y=round(mx+mw/2),round(my+mh/2)
    assert image.pixelColor(center_x,center_y)==image.pixelColor(center_x-5,center_y)


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


def test_portrait_places_map_above_information_and_preserves_datetime_tokens(qt_application):
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
    assert any(req.information.company_name in i.text for i in layout.text_items)
    assert max(i.rect[1]+i.rect[3] for i in layout.text_items)<layout.height


@pytest.mark.parametrize('bridge',[False,True])
def test_same_level_road_segment_casings_do_not_cut_across_saved_joints(qt_application,bridge):
    from map_model import MapRoad
    from route_export_render import preview,_prepare_scene
    req=request(show_stops=False)
    # Roads are split at an identical saved point. Sample the upper road
    # interior, away from the operating route, at and beside that joint.
    paths=(((0.,0.,80.),(100.,0.,80.)),((100.,0.,80.),(200.,0.,80.)))
    roads=tuple(MapRoad(i,'road','', (path,),road_class='express',express=True,width=16,
        bridge=bridge and i==2) for i,path in enumerate(paths,1))
    req=replace(req,snapshot=replace(req.snapshot,roads=roads))
    image=preview(req,(1536,1024))
    scene=_prepare_scene(req)
    road_shape=next(s for s in scene.shapes if s.path.boundingRect().height()==0)
    y=round(road_shape.path.boundingRect().top())
    x=round(scene.layout.map_rect[0]+scene.layout.map_rect[2]/2)
    assert image.pixelColor(x,y)==image.pixelColor(x-8,y)


def test_portrait_map_uses_the_same_horizontal_margins_as_information(qt_application):
    from route_export_model import ALL_FIELDS
    from route_export_render import build_layout
    layout=build_layout(request(aspect='A4',orientation='portrait',selected_fields=ALL_FIELDS))
    mx,my,mw,mh=layout.map_rect;ix,iy,iw,ih=layout.info_rect
    assert mx==ix and mw==iw
    assert my+mh<iy
    assert max(i.rect[1]+i.rect[3] for i in layout.text_items)<layout.height


def test_whole_view_distinguishes_up_dashed_and_down_solid_in_actual_pixels(qt_application):
    from route_export_render import preview,build_layout,_prepare_scene
    from PySide6.QtCore import Qt
    from map_model import MapStop
    req=request(show_stops=False)
    a,b,c=(0.,0.,0.),(100.,0.,0.),(200.,0.,0.)
    route=replace(req.route,paths=((a,b),(b,c)),leg_paths=(((a,b),),((b,c),)))
    snapshot=replace(req.snapshot,routes=(route,),stops=tuple(MapStop(i,'',p) for i,p in enumerate((a,b,c),1)))
    from route_export_model import build_export_request
    session,_=source()
    selected=build_export_request(session,snapshot,42,req.options)
    image=preview(selected,(1536,1024));mx,my,mw,mh=build_layout(selected).map_rect
    scene=_prepare_scene(selected)
    y=next(s.path.elementAt(0).y for s in scene.shapes
        if s.pen is not None and s.pen.color().name()==scene.line.lower() and s.pen.style()==Qt.PenStyle.SolidLine)
    colors=[{image.pixelColor(x,round(y)).name()
        for x in range(round(mx+mw*left),round(mx+mw*right))}
        for left,right in ((.20,.40),(.60,.80))]
    assert colors[0]=={scene.line.lower()}
    assert len(colors[1])>1


def test_selected_route_fills_map_with_safe_stroke_margin_without_clipping(qt_application):
    import route_export_render as renderer
    req=request(show_stops=False)
    scene=renderer._prepare_scene(req)
    mx,my,mw,mh=scene.layout.map_rect
    from PySide6.QtCore import QRectF
    extent=QRectF()
    for shape in scene.shapes:
        if shape.pen is not None and shape.pen.color().name()==scene.line.lower():
            extent=extent.united(shape.path.boundingRect())
    assert extent.left()>=mx+12 and extent.right()<=mx+mw-12
    assert extent.top()>=my+12 and extent.bottom()<=my+mh-12
    assert abs(max(extent.width()/(mw-32),extent.height()/(mh-32))-1)<1e-6


def test_portrait_map_height_adapts_to_information_space(qt_application):
    from route_export_model import ALL_FIELDS
    from route_export_render import build_layout
    layouts=[build_layout(request(aspect='A4',orientation='portrait',selected_fields=fields))
        for fields in (('今日客流',),ALL_FIELDS)]
    assert layouts[0].map_rect[2]==layouts[1].map_rect[2]
    assert layouts[0].map_rect[3]>layouts[1].map_rect[3]
    assert any(l.map_rect[2]!=l.map_rect[3] for l in layouts)


def test_rectangular_map_keeps_equal_horizontal_and_vertical_geometry_scale(qt_application):
    import route_export_render as renderer
    scene=renderer._prepare_scene(request(aspect='16:9',show_stops=False))
    mx,my,mw,mh=scene.layout.map_rect
    assert mw!=mh
    route_shape=next(s for s in scene.shapes if s.pen is not None and s.pen.color().name()==scene.line.lower())
    a,b=route_shape.path.elementAt(0),route_shape.path.elementAt(1)
    assert abs(abs(b.x-a.x)-abs(b.y-a.y))<1e-6


def test_fit_includes_visible_station_markers_with_safe_margin(qt_application):
    import route_export_render as renderer
    req=request()
    stops=tuple(replace(s,position=(s.position[0]-20,s.position[1],s.position[2]+30)) for s in req.stops)
    scene=renderer._prepare_scene(replace(req,stops=stops))
    mx,my,mw,mh=scene.layout.map_rect
    assert all(mx+12<=p.x()<=mx+mw-12 and my+12<=p.y()<=my+mh-12 for p in scene.station_points)


def test_passenger_heading_and_number_form_one_visually_close_group(qt_application):
    from route_export_render import preview,build_layout
    from stats_style import initialize_theme
    initialize_theme(qt_application)
    req=request(theme='night',selected_fields=('今日客流',))
    layout=build_layout(req);image=preview(req,(1536,1024))
    heading=next(i for i in layout.text_items if i.text=='今日客流')
    number=next(i for i in layout.text_items if i.role=='number')
    x=int(heading.rect[0]);w=int(heading.rect[2]);top=int(heading.rect[1])
    white=[];cyan=[]
    for y in range(top,round(number.rect[1]+number.rect[3])):
        for px in range(x,x+w):
            c=image.pixelColor(px,y)
            if y<heading.rect[1]+heading.rect[3] and min(c.red(),c.green(),c.blue())>220:white.append(y)
            if c.red()<80 and c.green()>200 and c.blue()>200:cyan.append(y)
    assert white and cyan
    assert min(cyan)-max(white)<=18


@pytest.mark.parametrize('aspect,orientation',[('3:2','landscape'),('A4','portrait')])
def test_user_header_footer_and_inline_passenger_unit(qt_application,aspect,orientation):
    from route_export_render import build_layout
    req=request(aspect=aspect,orientation=orientation,direction='up')
    items=build_layout(req).text_items;layout=build_layout(req)
    assert any(i.text==req.information.company_name+'·城市公交' for i in items)
    route=next(i for i in items if i.role=='route')
    direction=next(i for i in items if i.text=='上行')
    assert direction.size<=20 and direction.weight==400
    assert direction.rect[0]>=route.rect[0]+route.rect[2]
    assert route.rect[1]<=direction.rect[1]<route.rect[1]+route.rect[3]
    footer=next(i for i in items if i.text=='最后更新日期：2013-05-23')
    assert footer.role=='footer' and footer.size<=16 and footer.align=='right'
    assert footer.rect[1]>=layout.height-60
    number=next(i for i in items if i.role=='number');unit=next(i for i in items if i.role=='unit')
    assert unit.text=='人次' and unit.size<=20
    assert unit.rect[0]>number.rect[0]+number.rect[2]
    assert not any('全线' in i.text or '公交 · 上行' in i.text or '客流数据'==i.text for i in items)


def test_average_passenger_selection_uses_its_own_heading_and_inline_unit(qt_application):
    from route_export_render import build_layout
    layout=build_layout(request(selected_fields=('平均客流',)))
    assert any(i.text=='平均客流' and i.role=='heading' for i in layout.text_items)
    assert any(i.role=='number' for i in layout.text_items)
    assert any(i.role=='unit' and i.text=='人次' for i in layout.text_items)


def test_whole_direction_legend_is_inside_map_and_clear_of_route_strokes(qt_application):
    import route_export_render as renderer
    req=request();scene=renderer._prepare_scene(req)
    mx,my,mw,mh=scene.layout.map_rect;lx,ly,lw,lh=scene.legend_rect
    assert mx<=lx and my<=ly and lx+lw<=mx+mw and ly+lh<=my+mh
    assert all(s.path.boundingRect().bottom()<ly for s in scene.shapes
        if s.pen is not None and s.pen.color().name()==scene.line.lower())
    assert not any('全线' in i.text for i in scene.layout.text_items)
    assert renderer._prepare_scene(request(direction='up')).legend_rect==()


def test_up_dash_phase_continues_across_saved_path_fragments(qt_application):
    from route_export_model import build_export_request
    from route_export_render import preview,build_layout,_prepare_scene
    from PySide6.QtCore import Qt
    req=request(show_stops=False);session,_=source()
    a,b,c,mid=(0.,0.,0.),(100.,0.,0.),(200.,0.,0.),(137.,0.,0.)
    images=[]
    for up in (((b,c),),((b,mid),(mid,c))):
        route=replace(req.route,paths=((a,b),)+up,leg_paths=(((a,b),),up))
        selected=build_export_request(session,replace(req.snapshot,routes=(route,)),42,req.options)
        images.append(preview(selected,(1536,1024)))
    mx,my,mw,mh=build_layout(selected).map_rect
    scene=_prepare_scene(selected)
    y=round(next(s.path.elementAt(0).y for s in scene.shapes
        if s.pen is not None and s.pen.color().name()==scene.line.lower() and s.pen.style()==Qt.PenStyle.CustomDashLine))
    # Compare after the fragmentation point, away from its antialiased end.
    for x in range(round(mx+mw*.75),round(mx+mw*.90)):
        assert images[0].pixelColor(x,y)==images[1].pixelColor(x,y)
    assert any(images[0].pixelColor(x,y).name()==scene.line.lower()
        for x in range(round(mx+mw*.75),round(mx+mw*.90)))


def test_exactly_shared_direction_paths_both_remain_visible(qt_application):
    from route_export_model import build_export_request
    from route_export_render import preview,build_layout,_prepare_scene
    from PySide6.QtCore import Qt
    req=request(show_stops=False);session,_=source()
    a,b=(0.,0.,0.),(100.,0.,0.)
    route=replace(req.route,paths=((a,b),(b,a)),leg_paths=(((a,b),),((b,a),)))
    selected=build_export_request(session,replace(req.snapshot,routes=(route,)),42,req.options)
    image=preview(selected,(1536,1024));mx,my,mw,mh=build_layout(selected).map_rect
    scene=_prepare_scene(selected)
    ys=[round(next(s.path.elementAt(0).y for s in scene.shapes
        if s.pen is not None and s.pen.color().name()==scene.line.lower() and s.pen.style()==style))
        for style in (Qt.PenStyle.SolidLine,Qt.PenStyle.CustomDashLine)]
    colors=[{image.pixelColor(x,y).name()
        for x in range(round(mx+mw*.25),round(mx+mw*.75))} for y in ys]
    assert colors[0]=={scene.line.lower()} and len(colors[1])>1
