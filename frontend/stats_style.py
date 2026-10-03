"""Shared light Fluent palette and semantic shell stylesheet."""

from stats_tokens import (ACCENT, BORDER, CARD_BG, CARD_PADDING, CONTROL_GAP,
                          FONT_FAMILY, FONT_SIZE_BODY, FONT_SIZE_CAPTION,
                          FONT_SIZE_CHART_TITLE, FONT_SIZE_PAGE_TITLE,
                          GRID_COLOR, NARROW_PAGE_MARGIN, PAGE_BG, PAGE_MARGIN,
                          RADIUS_CARD, SECTION_GAP, TEXT_PRIMARY, TEXT_SECONDARY)
from stats_tokens import TOOLTIP_TEXT, TOOLTIP_BG, TOOLTIP_BORDER, TOOLTIP_FONT_SIZE, TOOLTIP_RADIUS
from stats_typography import tooltip_font

NARROW_MARGIN = NARROW_PAGE_MARGIN

TOOLTIP_STYLE = f"""
QToolTip {{ background-color: {TOOLTIP_BG}; color: {TOOLTIP_TEXT};
    border: 1px solid {TOOLTIP_BORDER}; border-radius: {TOOLTIP_RADIUS}px; padding: 6px 9px 8px 9px;
    font-family: "Segoe UI", "{FONT_FAMILY}"; font-size: {TOOLTIP_FONT_SIZE}px;
    font-weight: 400; font-style: normal; }}
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
    from qfluentwidgets import Theme, ToolTip as FluentToolTip, setTheme, setThemeColor, qconfig
    from touch_input import install_touch_input

    install_touch_input(app)

    if not hasattr(app, '_stats_tooltip_style'):
        from PySide6.QtCore import QObject, QEvent, QRect, Qt

        class TooltipStyleBoundary(QObject):
            def eventFilter(self, watched, event):
                if getattr(self, '_updating', False):
                    return False
                # Native tips inherit the source widget's local stylesheet.
                # An unqualified transparent background overrides application
                # QSS and leaves a transparent (black on Windows) popup.
                if (event.type() in (QEvent.Type.Show, QEvent.Type.Paint)
                        and watched.objectName() == 'qtooltip_label'):
                    signature = (watched.text(), watched.font().toString(), watched.styleSheet())
                    if event.type() != QEvent.Type.Show and getattr(watched, '_tip_signature', None) == signature:
                        return False
                    self._updating = True
                    try:
                        self._style_native(watched)
                        watched._tip_signature = (watched.text(), watched.font().toString(), watched.styleSheet())
                    finally:
                        self._updating = False
                elif event.type() == QEvent.Type.Show and isinstance(watched, FluentToolTip):
                    self._style_fluent(watched)
                return False

            def _style_native(self, watched):
                watched.setFont(tooltip_font())
                watched.setStyleSheet(TOOLTIP_STYLE)
                watched.setMargin(0)
                watched.setWordWrap(True)
                metrics = watched.fontMetrics()
                content_width = min(300, max(metrics.horizontalAdvance(line) for line in watched.text().split('\n')))
                bounds = metrics.boundingRect(QRect(0, 0, max(1, content_width), 10000),
                                              Qt.TextFlag.TextWordWrap, watched.text())
                watched.setFixedSize(content_width + 20, bounds.height() + 16)

            def _style_fluent(self, watched):
                watched.label.setFont(tooltip_font())
                watched.label.setStyleSheet(
                    f'color:{TOOLTIP_TEXT}; background:transparent; border:0;'
                    f'font-family:"Segoe UI","{FONT_FAMILY}"; font-size:{TOOLTIP_FONT_SIZE}px;'
                    'font-weight:400; font-style:normal;')
                watched.container.setStyleSheet(
                    f'QFrame#container {{background:{TOOLTIP_BG}; border:1px solid {TOOLTIP_BORDER};'
                    f'border-radius:{TOOLTIP_RADIUS}px;}}')
                watched.containerLayout.setContentsMargins(9, 6, 9, 8)
                # QLabel's wrapped sizeHint prefers a narrow multi-line
                # shape even for short text. Preserve the natural width
                # below the limit; only long content needs wrapping.
                watched.label.setWordWrap(False)
                watched.label.setMinimumWidth(0)
                watched.label.setMaximumWidth(16777215)
                content_width = min(300, watched.label.sizeHint().width())
                watched.label.setWordWrap(True)
                watched.label.setMinimumWidth(content_width)
                watched.label.setMaximumWidth(300)
                watched.label.adjustSize()
                watched.container.adjustSize()
                watched.adjustSize()

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
