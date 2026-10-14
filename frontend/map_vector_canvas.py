"""Native vector viewport; the parent MapCanvas owns data and interaction."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter
from PySide6.QtOpenGLWidgets import QOpenGLWidget


class VectorMapViewport(QOpenGLWidget):
    """Draw retained world paths without scaling a previous raster frame."""

    def __init__(self, canvas):
        super().__init__(canvas)
        self.canvas = canvas
        # OpenGL's path engine needs a multisampled framebuffer for smooth
        # primitive edges; QPainter's hint alone does not configure one.
        surface_format = self.format()
        surface_format.setSamples(4)
        self.setFormat(surface_format)
        # Qt's discard mode invalidates the buffers between composition and
        # QWidget capture. Keep their contents valid for both paths; paintGL
        # still fills and redraws the complete current vector view each time.
        self.setUpdateBehavior(QOpenGLWidget.UpdateBehavior.PartialUpdate)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAutoFillBackground(False)

    def initializeGL(self):
        self.canvas._vector_context_ready = True

    def paintGL(self):
        canvas = self.canvas
        if canvas._index_closed:
            return
        key, view = canvas._render_key(), (*canvas.center, canvas.zoom)
        painter = QPainter(self)
        try:
            if not painter.isActive():
                raise RuntimeError('Vector map paint device is unavailable')
            if canvas._vector_key != canvas._revision or canvas._vector_prepared is None:
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
        canvas._vector_presented(key, view)
