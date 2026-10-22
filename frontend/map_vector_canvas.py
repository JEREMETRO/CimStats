"""Native vector viewport; the parent MapCanvas owns data and interaction."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter
from PySide6.QtOpenGLWidgets import QOpenGLWidget


class VectorMapViewport(QOpenGLWidget):
    """Draw retained world paths without scaling a previous raster frame."""

    def __init__(self, canvas):
        super().__init__(canvas)
        self.canvas = canvas
        self._painted_stamp = None
        self._context_generation = 0
        self._gpu_renderer = None
        # OpenGL's path engine needs a multisampled framebuffer for smooth
        # primitive edges; QPainter's hint alone does not configure one.
        surface_format = self.format()
        surface_format.setSamples(4)
        surface_format.setStencilBufferSize(8)
        surface_format.setVersion(3,3)
        self.setFormat(surface_format)
        # Qt's discard mode invalidates the buffers between composition and
        # QWidget capture. Reuse a completed view during overlay composition;
        # a changed view is always drawn from its vector geometry.
        self.setUpdateBehavior(QOpenGLWidget.UpdateBehavior.PartialUpdate)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAutoFillBackground(False)

    def initializeGL(self):
        self._context_generation += 1
        self._painted_stamp = None
        self.canvas._vector_presented_key = self.canvas._vector_presented_view = None
        self.canvas._vector_context_ready = True
        self.canvas._vector_gl_failed = False
        self.canvas._vector_gl_error = None
        self.context().aboutToBeDestroyed.connect(self._release_gpu)
        self.canvas._notify_export_availability()

    def _release_gpu(self):
        if self._gpu_renderer is not None:
            self.makeCurrent()
            self._gpu_renderer.destroy()
            self._gpu_renderer=None
            self.doneCurrent()
        self._painted_stamp=None
        self.canvas._vector_presented_key = self.canvas._vector_presented_view = None
        self.canvas._notify_export_availability()

    def resizeGL(self, width, height):
        self._painted_stamp = None

    def paintGL(self):
        canvas = self.canvas
        if canvas._index_closed:
            return
        key, view = canvas._render_key(), (*canvas.center, canvas.zoom)
        stamp = (key, view, self.defaultFramebufferObject(), self._context_generation)
        ready = (canvas._vector_key == canvas._revision and canvas._vector_prepared is not None
                 and canvas._gpu_key == canvas._revision and canvas._gpu_scene is not None)
        if ready and self._painted_stamp == stamp:
            canvas._vector_presented(key, view)
            return
        self._painted_stamp = None
        painter = QPainter(self)
        try:
            if not painter.isActive():
                raise RuntimeError('Vector map paint device is unavailable')
            if not ready:
                from map_canvas import MAP_BACKGROUND
                from PySide6.QtGui import QColor
                painter.fillRect(self.rect(), QColor(MAP_BACKGROUND))
                return
            if self._gpu_renderer is None:
                from map_gpu_renderer import GpuMapRenderer
                self._gpu_renderer=GpuMapRenderer()
            painter.beginNativePainting()
            try:
                self._gpu_renderer.paint(canvas._gpu_scene,canvas.center,canvas.zoom,
                                         canvas.width(),canvas.height(),self.devicePixelRatioF())
            finally:
                painter.endNativePainting()
            canvas._paint_gpu_annotations(painter)
        except Exception as error:
            canvas._vector_paint_failed(key, view, str(error))
            return
        finally:
            painter.end()
        self._painted_stamp = stamp
        canvas._vector_presented(key, view)
