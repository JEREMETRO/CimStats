"""Colored Fluent SVGs rendered by Qt's native icon engine."""
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from PySide6.QtGui import QColor, QIcon
from qfluentwidgets import Theme
from qfluentwidgets.common.icon import writeSvg


# QIcon loads SVGs lazily. Keep their files alive for the application lifetime,
# including copies held by widgets, instead of using a Python QIconEngine whose
# parent/child wrappers can be destroyed in the wrong order by cyclic GC.
_resources = None
_paths = {}


def colored_icon(icon, color, theme=Theme.AUTO):
    """Preserve Fluent SVG geometry and color at every device pixel ratio."""
    global _resources
    source, fill = icon.path(theme), QColor(color).name()
    key = (source, fill)
    path = _paths.get(key)
    if path is None:
        svg = writeSvg(source, fill=fill).encode('utf-8')
        if _resources is None:
            _resources = TemporaryDirectory(prefix='cimstats-icons-')
        path = Path(_resources.name) / (sha256(svg).hexdigest() + '.svg')
        path.write_bytes(svg)
        _paths[key] = path
    return QIcon(str(path))
