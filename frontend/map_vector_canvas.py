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
        # OpenGL's path engine needs a multisampled framebuffer for smooth
        # primitive edges; QPainter's hint alone does not configure one.
        surface_format = self.format()
        surface_format.setSamples(4)
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
        self.canvas._vector_context_ready = True

    def resizeGL(self, width, height):
        self._painted_stamp = None

    def paintGL(self):
        canvas = self.canvas
        if canvas._index_closed:
            return
        key, view = canvas._render_key(), (*canvas.center, canvas.zoom)
        stamp = (key, view, self.defaultFramebufferObject(), self._context_generation)
        ready = canvas._vector_key == canvas._revision and canvas._vector_prepared is not None
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
            canvas._paint_vectors(painter, overlays=True)
        except Exception as error:
            canvas._vector_paint_failed(key, view, str(error))
            return
        finally:
            painter.end()
        self._painted_stamp = stamp
        canvas._vector_presented(key, view)
