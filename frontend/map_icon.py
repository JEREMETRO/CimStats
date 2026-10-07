"""Map navigation glyph following the application's linear icon treatment."""
from pathlib import Path
import sys
from qfluentwidgets import FluentIconBase, Theme


class MapIcon(FluentIconBase):
    def path(self, theme=Theme.AUTO):
        if getattr(sys, 'frozen', False):
            return str(Path(sys._MEIPASS) / 'frontend' / 'static' / 'cimstats' / 'map.svg')
        return str(Path(__file__).resolve().parent / 'static' / 'cimstats' / 'map.svg')


MAP_ICON = MapIcon()
