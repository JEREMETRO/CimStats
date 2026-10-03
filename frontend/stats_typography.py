"""Segoe Variable emphasis shared by labels, painters and rich-text measurement.

Only the process font database may load an existing Windows system font. No font
is installed, copied into the app, or applied globally to ordinary UI text.
"""
from __future__ import annotations

from html import escape
import logging
import os
from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase, QFontInfo, QGuiApplication
import stats_tokens as tokens

MEDIUM_NUMERIC_WEIGHT = QFont.Weight.DemiBold
LARGE_NUMERIC_WEIGHT = QFont.Weight.Bold


def _smooth_windows_font(font: QFont) -> QFont:
    # DirectWrite's default/vertical hinting leaves small YaHei CJK strokes
    # stepped. Natural symmetric rendering smooths both axes at device DPR;
    # pixel size, family, weight and optical axes remain owned by the caller.
    if os.name == 'nt':
        font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    return font


def ui_font(size: int, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    """Ordinary UI font in logical pixels, with continuous Windows glyph edges."""
    result = QFont(tokens.FONT_FAMILY)
    result.setPixelSize(size)
    result.setWeight(QFont.Weight(int(weight)))
    return _smooth_windows_font(result)


def numeric_font(size: int, *, large: bool = False) -> QFont:
    """Home numeric hierarchy; labels and units keep the ordinary font."""
    result = emphasis_font(size, LARGE_NUMERIC_WEIGHT if large else MEDIUM_NUMERIC_WEIGHT)
    if not large and QGuiApplication.instance():
        # Windows exposes Variable Display's semibold face as a separate family;
        # asking the Regular/Bold family for 600 otherwise resolves to 700.
        tier = 'Display' if size >= 20 else 'Text' if size >= 14 else 'Small'
        candidates = ('Segoe UI Variable ' + tier + ' Semibold', 'Segoe UI Semibold')
        available = QFontDatabase.families()
        family = next((name for name in candidates if name in available), None)
        if family:
            result.setFamilies([family, *result.families()])
    return result


def _load_system_font(filename):
    if os.name != 'nt':
        return -1
    path = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / filename
    return QFontDatabase.addApplicationFont(str(path)) if path.is_file() else -1


def _prepare_variable_font():
    app = QGuiApplication.instance()
    if app is None or app.property('statsVariableFontPrepared'):
        return
    available = QFontDatabase.families()
    if not any('Segoe UI Variable' in family for family in available) and os.name == 'nt':
        _load_system_font('SegUIVar.ttf')
    available = QFontDatabase.families()
    if not any('Segoe UI Variable' in family for family in available) and 'Segoe UI' not in available:
        for filename in ('segoeui.ttf', 'seguisb.ttf', 'segoeuib.ttf'):
            _load_system_font(filename)
    app.setProperty('statsVariableFontPrepared', True)


def emphasis_families(size: int) -> tuple[str, ...]:
    """Actual available family names; optical tier is applied by emphasis_font."""
    _prepare_variable_font()
    tier = 'Display' if size >= 20 else 'Text' if size >= 14 else 'Small'
    app = QGuiApplication.instance()
    names = QFontDatabase.families() if app else None
    specific = 'Segoe UI Variable ' + tier
    selected = (specific if names is not None and specific in names else
                'Segoe UI Variable' if names is None or 'Segoe UI Variable' in names else 'Segoe UI')
    if selected == 'Segoe UI' and app and not app.property('statsVariableFontFallbackLogged'):
        logging.getLogger(__name__).info('Segoe UI Variable unavailable; emphasis uses Segoe UI with CJK fallback')
        app.setProperty('statsVariableFontFallbackLogged', True)
    return (selected, tokens.FONT_FAMILY, 'Microsoft YaHei')


def emphasis_font(size: int, weight: QFont.Weight = QFont.Weight.DemiBold) -> QFont:
    """>=20px Display, 14–19px Text, <14px Small; CJK keeps the existing fallback."""
    result = QFont()
    result.setFamilies(list(emphasis_families(size)))
    result.setPixelSize(size)
    result.setWeight(QFont.Weight(int(weight)))
    if result.families()[0].startswith('Segoe UI Variable') and hasattr(result, 'setVariableAxis'):
        # Do not pin wght: rich-text spans must remain able to change weight.
        result.setVariableAxis(QFont.Tag('opsz'), 36. if size >= 20 else 20. if size >= 14 else 8.)
    return _smooth_windows_font(result)


def tooltip_font() -> QFont:
    """Independent regular font; never inherit a KPI's size or emphasis."""
    result = QFont()
    result.setFamilies(['Segoe UI', tokens.FONT_FAMILY])
    result.setPixelSize(tokens.TOOLTIP_FONT_SIZE)
    result.setWeight(QFont.Weight.Normal)
    return _smooth_windows_font(result)


def typography_status() -> dict:
    """Internal availability record; actual glyph verification remains separate."""
    families = emphasis_families(20)
    return {'selected_family': families[0], 'fallback_used': families[0] == 'Segoe UI',
            'chinese_fallback': tokens.FONT_FAMILY,
            'selected_family_available': (families[0] in QFontDatabase.families())
                if QGuiApplication.instance() else None,
            'variable_available': families[0].startswith('Segoe UI Variable')}


def emphasis_css(size: int, weight: QFont.Weight = QFont.Weight.DemiBold) -> str:
    """QSS/HTML declarations; set the matching QFont to retain its optical axis."""
    families = ', '.join('"' + name + '"' for name in emphasis_families(size))
    return f'font-family: {families}; font-size: {size}px; font-weight: {int(weight)};'


def apply_emphasis_font(widget, size: int | None = None,
                        weight: QFont.Weight = QFont.Weight.DemiBold):
    """Call after removing/replacing old font-family QSS; no stylesheet mutation."""
    if size is None:
        size = widget.font().pixelSize()
        if size < 1:
            size = QFontInfo(widget.font()).pixelSize()
    widget.setFont(emphasis_font(size, weight))


def emphasis_html(text, size: int, weight: QFont.Weight = QFont.Weight.DemiBold) -> str:
    """Escaped emphasis span; QTextDocument must use the same emphasis_font base."""
    return (f'<span style="{escape(emphasis_css(size, weight), quote=True)}">'
            f'{escape(str(text))}</span>')
