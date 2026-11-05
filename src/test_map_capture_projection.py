"""The smoke check compares a fractional-DPI capture in its own pixel grid."""
from types import SimpleNamespace

import numpy as np
import pytest
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QWidget

from package_smoke import _assert_map_composition


def image(array):
    height, width, _ = array.shape
    result = QImage(array.data, width, height, array.strides[0],
                    QImage.Format.Format_RGBA8888).copy()
    result.setDevicePixelRatio(1.25)
    return result


@pytest.mark.parametrize('corrupt', [False, True])
def test_fractional_capture_accepts_qt_sampling_but_rejects_wrong_pixels(qt_application, corrupt):
    frame = np.full((544, 630, 4), 255, dtype=np.uint8)
    frame[::2, :, :3] = [0, 10, 240]
    frame[1::2, :, :3] = [240, 10, 0]
    ancestor = np.full((850, 1200, 4), 255, dtype=np.uint8)
    # The observed Qt mapping starts at physical row 183 and skips source
    # row 273 when drawing this 435-logical-pixel viewport at 125%.
    ancestor[183:726, 90:720] = np.concatenate((frame[:273], frame[274:]))
    if corrupt:
        ancestor[420:480, 200:400, :3] = 0
    captured = QPixmap.fromImage(image(ancestor))
    window = QWidget()
    canvas = QWidget(window)
    canvas.setGeometry(72, 146, 504, 435)
    canvas._vector_gl_failed = False
    framebuffer = image(frame).convertToFormat(QImage.Format.Format_RGB32)
    canvas._vector_viewport = SimpleNamespace(grabFramebuffer=lambda: framebuffer)
    try:
        if corrupt:
            with pytest.raises(AssertionError, match='composited map differs'):
                _assert_map_composition(window, captured, canvas)
        else:
            report = _assert_map_composition(window, captured, canvas)
            assert report == {'pixels_compared': 630 * 543, 'mismatch_fraction': 0.}
    finally:
        window.close()
