"""Shared width rules and annotation collision behavior for retained maps."""
import numpy as np
from PySide6.QtCore import QRectF
from map_canvas import MapCanvas,road_style
from map_gpu_renderer import _road_widths
from map_gpu_annotations import _Occupied
from map_gpu_geometry import _road_parameters
from map_model import MapRoad


def test_gpu_draw_order_uses_the_shared_road_width_curve():
    roads=[MapRoad(i,level,level,(),road_class=level,width=width)
           for i,(level,width) in enumerate((('ordinary',12.),('expressway',22.),
                                             ('pedestrian',4.),('rail',10.),('unknown',None)))]
    parameters=np.asarray([_road_parameters(road)[0] for road in roads],dtype=np.float32)
    for zoom in (.0001,.0999,.10,.1001,.1499,.15,.1501,.2499,.25,.2501,.4499,.45,.4501,1.,16.,100.):
        actual=_road_widths(parameters,zoom)
        expected=np.asarray([road_style(road,zoom).width for road in roads])
        np.testing.assert_allclose(actual,expected,rtol=1e-6,atol=1e-6)


def test_annotation_grid_has_identical_collision_result_to_full_rectangle_scan():
    rectangles=[QRectF(x,y,w,h) for x,y,w,h in
                [(-89.,-39.,130.,27.),(0.,0.,62.,31.),(63.9,31.9,45.,18.),
                 (121.,95.,300.,65.),(-4.,200.,90.,20.)]]
    grid=_Occupied(rectangles)
    for x in range(-100,500,13):
        for y in range(-60,280,17):
            candidate=QRectF(x+.13,y+.77,93.,22.)
            assert grid.intersects(candidate)==any(candidate.intersects(r) for r in rectangles)


def test_annotation_and_legend_options_keep_the_uploaded_scene(qt_application):
    canvas=MapCanvas();scene=object();annotations=object()
    canvas._gpu_scene=scene;canvas._gpu_annotations=annotations;canvas._gpu_key=canvas._revision
    for options in ({'stops':False},{'stop_names':False},{'line_numbers':False},
                    {'legend_external':True},{'legend_items':(('a','b'),)}):
        canvas.set_options(**options)
        assert canvas._gpu_key==canvas._revision
        assert canvas._gpu_scene is scene and canvas._gpu_annotations is annotations
    canvas.close()


def test_font_change_redraws_current_view_without_compiling_gpu_geometry(qt_application):
    canvas=MapCanvas();scene=object();annotations=object()
    canvas._gpu_scene=scene;canvas._gpu_annotations=annotations;canvas._gpu_key=canvas._revision
    previous=canvas._render_key()
    font=canvas.font();font.setPointSizeF(font.pointSizeF()+2)
    canvas.setFont(font)
    assert canvas._render_key()!=previous
    assert canvas._prepare_gpu()
    assert canvas._gpu_scene is scene and canvas._gpu_annotations is annotations
    assert canvas._gpu_job is None
    canvas.close()
