"""Shared light Fluent palette and semantic shell stylesheet."""

from stats_tokens import (ACCENT, BORDER, CARD_BG, CARD_PADDING, CONTROL_GAP,
                          FONT_FAMILY, FONT_SIZE_BODY, FONT_SIZE_CAPTION,
                          FONT_SIZE_CHART_TITLE, FONT_SIZE_PAGE_TITLE,
                          GRID_COLOR, NARROW_PAGE_MARGIN, PAGE_BG, PAGE_MARGIN,
                          RADIUS_CARD, SECTION_GAP, TEXT_PRIMARY, TEXT_SECONDARY)

NARROW_MARGIN = NARROW_PAGE_MARGIN

TOOLTIP_STYLE = f"""
QToolTip {{ background-color: {CARD_BG}; color: {TEXT_PRIMARY};
    border: 1px solid {BORDER}; border-radius: 6px; padding: 6px 8px;
    font-family: "{FONT_FAMILY}"; font-size: {FONT_SIZE_CAPTION}px; }}
"""

STYLE = TOOLTIP_STYLE + f"""
QMainWindow {{ background: {PAGE_BG}; }}
QWidget#statsPage, QWidget#overviewPage, QWidget#linesPage {{ background: transparent; }}
QLabel#pageTitle, QLabel#sectionTitle {{ font-size: {FONT_SIZE_PAGE_TITLE}px; font-weight: 600; color: {TEXT_PRIMARY}; }}
QLabel#panelTitle {{ font-size: {FONT_SIZE_CHART_TITLE}px; font-weight: 600; color: {TEXT_PRIMARY}; }}
QLabel#muted, QLabel#footerContext, QLabel#hint, QLabel#cardNote,
QLabel#extremeMetric, QLabel#legend, QLabel#rangeSummary {{ color: {TEXT_SECONDARY}; }}
QLabel#cardLabel, QLabel#factLabel {{ color: {TEXT_SECONDARY}; font-size: {FONT_SIZE_CAPTION}px; }}
QLabel#cardValue, QLabel#factValue, QLabel#extremeLine,
QLabel#categoryValue {{ color: {TEXT_PRIMARY}; font-weight: 600; }}
QLabel#chartTotal {{ color: {TEXT_PRIMARY}; font-size: 20px; font-weight: 600; }}
QFrame#metricCard, QFrame#panel, QFrame#scheduleCard,
QFrame#factCard, QFrame#extremeCard, QFrame#statsHeader {{
    background: {CARD_BG}; border: 1px solid {BORDER}; border-radius: {RADIUS_CARD}px;
}}
QFrame#timeCell {{ background: #F8FBFE; border: 1px solid {BORDER}; border-radius: 7px; }}
QWidget#factsHost {{ background: {CARD_BG}; }}
QScrollArea {{ border: 0; background: transparent; }}
QTableWidget {{ background: {CARD_BG}; border: 1px solid {BORDER}; gridline-color: {GRID_COLOR}; }}
QHeaderView::section {{ background: #F8FBFE; border: 0; border-bottom: 1px solid {BORDER}; padding: 7px; }}
"""


def initialize_theme(app):
    """Initialize the same native Fluent theme for the app and QA windows."""
    import os
    from pathlib import Path
    from PySide6.QtGui import QColor, QFont, QFontDatabase
    from qfluentwidgets import Theme, setTheme, setThemeColor, qconfig
    from touch_input import install_touch_input

    install_touch_input(app)

    if not hasattr(app, '_stats_tooltip_style'):
        from PySide6.QtCore import QObject, QEvent

        class TooltipStyleBoundary(QObject):
            def eventFilter(self, watched, event):
                # Native tips inherit the source widget's local stylesheet.
                # An unqualified transparent background overrides application
                # QSS and leaves a transparent (black on Windows) popup.
                if (event.type() == QEvent.Type.Show
                        and watched.objectName() == 'qtooltip_label'):
                    watched.setStyleSheet(TOOLTIP_STYLE)
                return False

        app._stats_tooltip_style = TooltipStyleBoundary(app)
        app.installEventFilter(app._stats_tooltip_style)

    if qconfig.theme != Theme.LIGHT:
        setTheme(Theme.LIGHT)
    if qconfig.get(qconfig.themeColor).rgba() != QColor(ACCENT).rgba():
        setThemeColor(ACCENT)
    if os.environ.get('QT_QPA_PLATFORM') == 'offscreen' and not app.property('statsFontsLoaded'):
        for filename in ('msyh.ttc', 'msyhbd.ttc'):
            font_path = Path('C:/Windows/Fonts') / filename
            if font_path.exists():
                QFontDatabase.addApplicationFont(str(font_path))
        app.setProperty('statsFontsLoaded', True)
    qconfig.set(qconfig.fontFamilies, [FONT_FAMILY], save=False)
    font = QFont(FONT_FAMILY)
    font.setPixelSize(FONT_SIZE_BODY)
    if app.font() != font:
        app.setFont(font)
    if app.styleSheet() != STYLE:
        app.setStyleSheet(STYLE)
