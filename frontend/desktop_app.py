from __future__ import annotations

import os
import json
import shutil
import subprocess
import sys
import uuid
import time
import psutil
from pathlib import Path
from shiboken6 import isValid

from PySide6.QtCore import Qt, QSettings, QThread, Signal, QRect, QSize, QMargins, QTimer, QEvent, QPoint
from PySide6.QtGui import QAction, QDragEnterEvent, QDropEvent, QPainter, QColor, QFontMetrics, QFont, QPalette
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QGridLayout,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox, QProgressBar,
    QPushButton, QSplitter, QTabWidget, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget, QHeaderView, QFrame, QStackedWidget,
    QToolButton, QScrollArea, QMenu, QSizePolicy, QLayout, QLayoutItem,
)
from PySide6.QtCharts import (
    QChart, QChartView, QBarSeries, QBarSet, QPieSeries, QLineSeries, QAbstractBarSeries,
    QBarCategoryAxis, QValueAxis, QHorizontalBarSeries,
    QHorizontalStackedBarSeries,
)
from openpyxl import load_workbook

PROJECT = Path(__file__).resolve().parents[1]
SRC = PROJECT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
# Namespace-qualified frontend/src imports must also work from a foreign cwd.
if str(PROJECT) not in sys.path:
    sys.path.insert(sys.path.index(str(SRC)) + 1, str(PROJECT))
from report_model import DAY_GROUPS, MODES, load_session
from statistics_page import StatisticsPage
from stats_style import initialize_theme
from stats_tokens import (ACCENT, ACCENT_SOFT, BORDER, CARD_BG, FONT_FAMILY, FONT_SIZE_BODY, FONT_SIZE_PAGE_TITLE,
                          ACTION_BUTTON_WIDTH,
                          NAV_WIDTH_COMPACT, NAV_WIDTH_EXPANDED, PAGE_BG,
                          TEXT_PRIMARY, TEXT_SECONDARY)
from qfluentwidgets import (CardWidget, CheckableMenu, ComboBox as FluentComboBox,
                            DropDownPushButton, FluentIcon, LineEdit as FluentLineEdit,
                            NavigationInterface, NavigationDisplayMode, NavigationItemPosition, PrimaryPushButton,
                            ProgressBar as FluentProgressBar, PushButton,
                            ScrollArea as FluentScrollArea, TabWidget as FluentTabWidget,
                            TableWidget as FluentTableWidget, ToolButton as FluentToolButton,
                            IconWidget, RoundMenu, Action, TransparentToolButton)
from app_paths import jobs_directory
from app_metadata import APP_NAME, application_version
from stats_identity import save_fingerprint
from loading_overlay import LoadingOverlay
from parse_progress import ParseProgressEstimator
from statistics_model import parse_time
from stats_elevation import attach_card_elevation
from stats_dialogs import FluentMessageBox as QMessageBox
APP_ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else PROJECT
JOBS = jobs_directory(APP_ROOT)
BUNDLE_ROOT = Path(getattr(sys, "_MEIPASS", "")) if getattr(sys, "frozen", False) else PROJECT
RUNTIME_DATA = BUNDLE_ROOT / "data"
CATALOG_DIR = BUNDLE_ROOT / "exports"
APP_VERSION = application_version(BUNDLE_ROOT)
DEFAULT_MANAGED = Path(r"D:\Program Files (x86)\Steam\steamapps\common\Cities in Motion 2\CIM2_Data\Managed")


class ElidedLabel(QLabel):
    """Keep the full accessible text while painting within the allocated width."""

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

    def minimumSizeHint(self):
        return QSize(0, super().minimumSizeHint().height())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setPen(self.palette().color(self.foregroundRole()))
        displayed = self.fontMetrics().elidedText(
            self.text(), Qt.TextElideMode.ElideMiddle, self.contentsRect().width())
        painter.drawText(self.contentsRect(), self.alignment(), displayed)


def bundled_managed_root() -> Path:
    """Return the Managed directory shipped beside the portable executable."""
    extracted = Path(getattr(sys, "_MEIPASS", "")) / "game_runtime" / "Managed"
    if extracted.exists():
        return extracted
    return APP_ROOT / "game_runtime" / "Managed"


def find_managed_roots() -> list[Path]:
    # The portable runtime is authoritative.  Steam locations are fallbacks
    # for development builds or packages built without the local game files.
    roots = [bundled_managed_root(), APP_ROOT / "game_runtime" / "Managed"]
    configured = os.environ.get("CIM2_MANAGED_ROOT", "")
    if configured:
        roots.append(Path(configured))
    roots.append(DEFAULT_MANAGED)
    for base in (Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")), Path(os.environ.get("PROGRAMFILES", r"C:\Program Files"))):
        roots.extend([
            base / "Steam" / "steamapps" / "common" / "Cities in Motion 2" / "CIM2_Data" / "Managed",
            base / "SteamLibrary" / "steamapps" / "common" / "Cities in Motion 2" / "CIM2_Data" / "Managed",
        ])
    seen = set()
    return [p for p in roots if not (str(p).lower() in seen or seen.add(str(p).lower()))]


def locate_managed(saved: str = "") -> Path | None:
    # A frozen portable build must be self-contained.  Do not silently fall
    # back to Steam or a stale user setting, otherwise packaging omissions are
    # hidden on the development machine and only fail after distribution.
    if getattr(sys, "frozen", False):
        embedded = bundled_managed_root()
        return embedded if (embedded / "Assembly-CSharp.dll").exists() else None
    candidates = [bundled_managed_root()]
    if saved:
        candidates.append(Path(saved))
    candidates.extend(find_managed_roots())
    seen = set()
    for path in candidates:
        path = path / "Managed" if path.name.lower() == "cim2_data" else path
        key = str(path).lower()
        if key in seen:
            continue
        seen.add(key)
        if (path / "Assembly-CSharp.dll").exists():
            return path
    return None


def fmt(value, digits=2):
    if value is None or value == "":
        return "-"
    if isinstance(value, float):
        return f"{value:,.{digits}f}"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


class SortItem(QTableWidgetItem):
    def __lt__(self, other):
        left = self.data(Qt.ItemDataRole.UserRole)
        right = other.data(Qt.ItemDataRole.UserRole) if other is not None else None
        if isinstance(left, (int, float)) and isinstance(right, (int, float)):
            return left < right
        return self.text().casefold() < (other.text().casefold() if other is not None else "")


def item(value) -> QTableWidgetItem:
    cell = SortItem(fmt(value) if isinstance(value, (int, float)) else str(value or ""))
    if isinstance(value, (int, float)):
        cell.setData(Qt.ItemDataRole.UserRole, value)
    cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
    return cell


class MetricCard(CardWidget):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("metricCard")
        attach_card_elevation(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 9, 12, 8)
        layout.setSpacing(3)
        self.title = QLabel(title); self.title.setObjectName("cardLabel")
        self.value = QLabel("-"); self.value.setObjectName("cardValue")
        self.note = QLabel(""); self.note.setObjectName("cardNote")
        layout.addWidget(self.title); layout.addWidget(self.value); layout.addWidget(self.note)

    def set_value(self, value, note=""):
        self.value.setText(fmt(value)); self.note.setText(note)


class FactCard(CardWidget):
    """Compact single-line metric card used by the line detail pane."""
    clicked = Signal()

    def __init__(self, label: str, value="", parent=None):
        super().__init__(parent)
        self.setObjectName("factCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 7, 10, 7)
        layout.setSpacing(2)
        self.label = QLabel(label); self.label.setObjectName("factLabel")
        self.value = QLabel(fmt(value)); self.value.setObjectName("factValue")
        self.value.setWordWrap(True)
        layout.addWidget(self.label); layout.addWidget(self.value)

    def set_data(self, label, value):
        self.label.setText(label); self.value.setText(fmt(value))

class FactGroupCard(CardWidget):
    """One card containing the paired fields requested for line details."""
    clicked = Signal()

    def __init__(self, fields, parent=None):
        super().__init__(parent); self.setObjectName("factCard")
        layout = QHBoxLayout(self); layout.setContentsMargins(10, 7, 10, 7); layout.setSpacing(12)
        self.fields = []
        for label, value in fields:
            box = QVBoxLayout(); box.setSpacing(2); lab = QLabel(label); lab.setObjectName("factLabel"); val = QLabel(fmt(value)); val.setObjectName("factValue"); val.setWordWrap(True); box.addWidget(lab); box.addWidget(val); layout.addLayout(box, 1); self.fields.append((lab, val))

    def set_data(self, index, label, value):
        lab, val = self.fields[index]; lab.setText(label); val.setText(fmt(value))

class HoverToggleButton(FluentToolButton):
    """Small switch control with a preview state on hover only."""
    entered = Signal()
    left = Signal()

    def enterEvent(self, event):
        self.entered.emit()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.left.emit()
        super().leaveEvent(event)


class ToggleFactCard(CardWidget):
    """A compact metric card with a primary value and an alternate value.

    Hover temporarily previews the alternate field; clicking toggles the
    displayed field.  This keeps paired line metrics compact while making the
    secondary value discoverable without opening another panel.
    """
    clicked = Signal()

    def __init__(self, primary, primary_value, alternate=None, alternate_value=None, parent=None):
        super().__init__(parent)
        self.setObjectName("factCard")
        self._primary = (primary, primary_value)
        self._alternate = (alternate, alternate_value) if alternate is not None else None
        self._selected_alternate = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 7, 10, 7)
        layout.setSpacing(2)
        self.label = QLabel()
        self.label.setObjectName("factLabel")
        self.value = QLabel()
        self.value.setObjectName("factValue")
        self.value.setWordWrap(True)
        layout.addWidget(self.label)
        layout.addWidget(self.value)
        self.toggle_button = None
        if self._alternate:
            # Keep the switch discoverable without making the whole card feel
            # like a large button.  The card itself remains clickable for
            # keyboard/mouse compatibility.
            self.toggle_button = HoverToggleButton()
            self.toggle_button.setIcon(FluentIcon.SYNC.icon()); self.toggle_button.setIconSize(QSize(14, 14))
            self.toggle_button.setToolTip("切换显示字段")
            self.toggle_button.setFixedSize(25, 22)
            self.toggle_button.setObjectName("factToggle")
            button_row = QHBoxLayout(); button_row.setContentsMargins(0, 0, 0, 0)
            button_row.addStretch(); button_row.addWidget(self.toggle_button)
            layout.addLayout(button_row)
            self.toggle_button.clicked.connect(self._toggle)
            self.toggle_button.entered.connect(self._preview)
            self.toggle_button.left.connect(self._render)
        self._render()
        if self._alternate:
            self.toggle_button.setToolTip("切换显示字段")

    def _render(self):
        field = self._alternate if self._selected_alternate else self._primary
        self.label.setText(str(field[0]))
        self.value.setText(fmt(field[1]))

    def _toggle(self):
        if self._alternate:
            self._selected_alternate = not self._selected_alternate
            self._render()
            self.clicked.emit()

    def _preview(self):
        if self._alternate and not self._selected_alternate:
            self.label.setText(str(self._alternate[0]))
            self.value.setText(fmt(self._alternate[1]))

    def mousePressEvent(self, event):
        super().mousePressEvent(event)


class ExtremeMetricCard(CardWidget):
    """Compact extreme card whose button switches the displayed metric."""

    def __init__(self, parent=None):
        super().__init__(parent)
        attach_card_elevation(self)
        self.setObjectName("extremeCard")
        self.record = None
        self.metric_index = 0
        self.metrics = (
            ("客流", "今日客流"),
            ("班次", "当日发班数"),
            ("平均单班人次", "今日平均单班人次"),
            ("平均车公里人次", "今日平均车公里人次"),
        )
        layout = QVBoxLayout(self); layout.setContentsMargins(14, 9, 10, 8); layout.setSpacing(2)
        head = QHBoxLayout(); self.title = QLabel("-"); self.title.setObjectName("cardLabel"); head.addWidget(self.title); head.addStretch(); layout.addLayout(head)
        self.line_value = QLabel("-"); self.line_value.setObjectName("extremeLine"); layout.addWidget(self.line_value)
        self.metric_value = QLabel("-"); self.metric_value.setObjectName("extremeMetric"); layout.addWidget(self.metric_value)
        row = QHBoxLayout(); row.setContentsMargins(0, 0, 0, 0); row.addStretch(); self.toggle = HoverToggleButton(); self.toggle.setIcon(FluentIcon.SYNC.icon()); self.toggle.setIconSize(QSize(14, 14)); self.toggle.setToolTip("切换指标"); self.toggle.setFixedSize(25, 22); self.toggle.setObjectName("factToggle"); row.addWidget(self.toggle); layout.addLayout(row)
        self.toggle.clicked.connect(self.next_metric)
        self.toggle.entered.connect(self.preview_metric)
        self.toggle.left.connect(self.render)

    def set_record(self, record):
        self.record = record
        self.metric_index = 0
        self.render()

    def next_metric(self):
        if self.record:
            self.metric_index = (self.metric_index + 1) % len(self.metrics)
            self.render()

    def preview_metric(self):
        if self.record:
            label, key = self.metrics[(self.metric_index + 1) % len(self.metrics)]
            self.metric_value.setText(f"{label} {fmt(self.record.get(key, 0))}")

    def render(self):
        if not self.record:
            self.title.setText("-"); self.line_value.setText("-"); self.metric_value.setText("-"); return
        label, key = self.metrics[self.metric_index]
        self.title.setText(self.record.get("title", ""))
        self.line_value.setText(self.record.get("line", "-"))
        self.metric_value.setText(f"{label} {fmt(self.record.get(key, 0))}")


class FlowLayout(QLayout):
    """Wrapping layout used by timetable cells (vertical scrolling only)."""

    def __init__(self, parent=None, margin=0, spacing=6):
        super().__init__(parent)
        self._items = []
        self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize(0, 0)
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        return size + QSize(margins.left() + margins.right(), margins.top() + margins.bottom())

    def _do_layout(self, rect, test_only):
        margins = self.contentsMargins()
        area = rect.adjusted(margins.left(), margins.top(), -margins.right(), -margins.bottom())
        x, y, line_height = area.x(), area.y(), 0
        spacing = self.spacing()
        for item in self._items:
            hint = item.sizeHint()
            next_x = x + hint.width() + spacing
            if next_x - spacing > area.right() + 1 and line_height > 0:
                x = area.x()
                y += line_height + spacing
                next_x = x + hint.width() + spacing
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(x, y, hint.width(), hint.height()))
            x = next_x
            line_height = max(line_height, hint.height())
        return y + line_height - rect.y() + margins.bottom()


class BarCanvas(QWidget):
    """Axis-free horizontal chart with deterministic labels and hit testing."""
    clicked_mode = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.kind = "stacked"
        self.labels = []
        self.values = []
        self.colors = []
        self.unit = ""
        self.setMinimumHeight(58)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_data(self, kind, labels, values, colors, unit):
        self.kind = kind
        self.labels = list(labels)
        self.values = [float(value or 0) for value in values]
        self.colors = list(colors)
        self.unit = unit
        if kind == "stacked":
            self.setFixedHeight(46)
        else:
            # Keep ranking panels at a stable height so switching between
            # scopes does not resize the surrounding cards.
            self.setFixedHeight(330)
        self.updateGeometry()
        self.update()

    def _color(self, value):
        return QColor(value if isinstance(value, str) else "#2477D4")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#FFFFFF"))
        if not self.values:
            painter.setPen(QColor("#8796A0"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "暂无数据")
            return
        if self.kind == "stacked":
            total = sum(self.values)
            left, right = 8, max(8, self.width() - 8)
            top = max(8, (self.height() - 22) // 2)
            rect = QRect(left, top, max(1, right - left), 22)
            x = float(rect.left())
            for label, value, color in zip(self.labels, self.values, self.colors):
                width = rect.width() * value / total if total else 0
                segment = QRect(round(x), rect.top(), max(1, round(width)), rect.height())
                painter.fillRect(segment, self._color(color))
                if width >= 58:
                    painter.setPen(Qt.GlobalColor.white)
                    painter.setFont(self.font())
                    painter.drawText(segment, Qt.AlignmentFlag.AlignCenter, f"{value:,.2f}")
                x += width
            return
        # Ranking bars are deliberately rendered in descending order so the
        # largest bar is visually at the top, independent of QtCharts axis
        # category ordering.
        max_value = max(self.values, default=0) or 1
        label_width = min(115, max(58, self.width() // 4))
        value_width = 86
        bar_left = label_width + 8
        bar_right = max(bar_left + 12, self.width() - value_width)
        row_height = max(24, self.height() // max(len(self.values), 1))
        for index, (label, value) in enumerate(zip(self.labels, self.values)):
            y = index * row_height + 3
            painter.setPen(QColor("#52636D"))
            painter.setFont(self.font())
            painter.drawText(QRect(4, y, label_width, row_height), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, str(label))
            bar_width = max(2, round((bar_right - bar_left) * value / max_value))
            painter.fillRect(QRect(bar_left, y + 5, bar_width, max(12, row_height - 10)), self._color(self.colors[0] if self.colors else "#2477D4"))
            painter.setPen(QColor("#263A45"))
            painter.drawText(QRect(bar_left + bar_width + 6, y, value_width - 6, row_height), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, f"{value:,.0f} {self.unit}")

    def mousePressEvent(self, event):
        if self.kind != "stacked" or event.button() != Qt.MouseButton.LeftButton or not self.values:
            return super().mousePressEvent(event)
        total = sum(self.values)
        left, right = 8, max(8, self.width() - 8)
        position = max(0, min(right - left, event.position().x() - left))
        cursor = 0.0
        for label, value in zip(self.labels, self.values):
            cursor += (right - left) * value / total if total else 0
            if position <= cursor:
                self.clicked_mode.emit(label)
                break
        super().mousePressEvent(event)


class PieView(QChartView):
    clicked = Signal()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class ChartPanel(CardWidget):
    clicked_mode = Signal(str)
    pie_clicked = Signal()
    pie_mode_clicked = Signal(str)

    def __init__(self, title: str, hint: str, parent=None):
        super().__init__(parent); self.setObjectName("panel")
        self.setMaximumHeight(720)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        root = QVBoxLayout(self); root.setContentsMargins(16, 16, 16, 16); root.setSpacing(6)
        head = QHBoxLayout(); self.title = QLabel(title); self.title.setObjectName("panelTitle"); self.total_label = QLabel(""); self.total_label.setObjectName("chartTotal"); self.toggle = PushButton("综合排行"); self.toggle.setObjectName("subtleButton"); head.addWidget(self.title); head.addWidget(self.total_label); head.addStretch(); head.addWidget(self.toggle); root.addLayout(head)
        self.hint = QLabel(hint); self.hint.setObjectName("hint"); self.hint.setVisible(False)
        self.chart = BarCanvas(); root.addWidget(self.chart, 1)
        self.pie = PieView(); self.pie.setFrameShape(QFrame.Shape.NoFrame); self.pie.setStyleSheet("background: transparent; border: 0;"); self.pie.setRenderHint(QPainter.RenderHint.Antialiasing); self.pie.setMinimumHeight(210); self.pie.setMaximumHeight(430); self.pie.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding); self.pie.setVisible(False); root.addWidget(self.pie)
        self.mode_rows_host = QWidget(); self.mode_rows = QVBoxLayout(self.mode_rows_host); self.mode_rows.setContentsMargins(0, 0, 0, 0); self.mode_rows.setSpacing(2); root.addWidget(self.mode_rows_host)
        self.legend = QLabel(""); self.legend.setObjectName("legend"); self.legend.setWordWrap(True); root.addWidget(self.legend); self.legend.hide()
        self.chart.clicked_mode.connect(self.clicked_mode)
        self.pie.clicked.connect(self._schedule_pie_click)
        self.pie_details = None
        self.aggregate_pie = None
        self.pie_expanded = False
        self._pie_segment_pending = False

    def _on_pie_segment(self, slice_):
        self._pie_segment_pending = True
        self.pie_mode_clicked.emit(slice_.label())

    def _schedule_pie_click(self):
        # QChartView emits its mouse signal before the series click signal.
        # Defer the generic pie action one event turn so a clicked transport
        # mode can take precedence over the aggregate-pie expansion.
        QTimer.singleShot(0, self._finish_pie_click)

    def _finish_pie_click(self):
        if self._pie_segment_pending:
            self._pie_segment_pending = False
            return
        self.pie_clicked.emit()

    def clear(self):
        self.chart.set_data("stacked", [], [], [], "")
        self.pie.setChart(QChart()); self.pie.setVisible(False); self.total_label.clear(); self.legend.clear()
        self.pie_details = None; self.aggregate_pie = None; self.pie_expanded = False
        while self.mode_rows.count():
            item = self.mode_rows.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()

    def show_stacked(self, labels, values, colors, unit):
        self.aggregate_pie = (list(labels), list(values), list(colors), unit)
        self.pie_expanded = False
        self.pie.setFixedHeight(210)
        self.chart.set_data("stacked", labels, values, colors, unit)
        total = sum(values)
        self.total_label.setText(f"{total:,.2f} {unit}")
        # A percentage view sits below the raw-value stacked bar.
        pie = QChart(); pie.setBackgroundVisible(False); pie.legend().setVisible(False); pie.setMargins(QMargins(4, 0, 4, 0)); pie_series = QPieSeries()
        for label, value, color in zip(labels, values, colors):
            if value <= 0:
                continue
            slice_ = pie_series.append(label, value); slice_.setColor(color); slice_.setLabelVisible(True); slice_.setLabelFont(QApplication.font()); slice_.setLabel(f"{label} {value / total * 100:.1f}%" if total else label)
        pie.addSeries(pie_series); self.pie.setChart(pie); self.pie.setVisible(bool(values))
        # Selecting a segment drills directly into that transport mode.
        pie_series.clicked.connect(lambda slice_: (not self.pie_expanded) and self._on_pie_segment(slice_))
        while self.mode_rows.count():
            item = self.mode_rows.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()
        for label, value, color in zip(labels, values, colors):
            row = QFrame(); row.setObjectName("chartModeRow"); row.setFixedHeight(30); layout = QHBoxLayout(row); layout.setContentsMargins(4, 1, 4, 1); layout.setSpacing(7)
            dot = QLabel("●"); dot.setStyleSheet(f"color:{color};font-size:15px"); name = QLabel(str(label)); value_label = QLabel(f"{value:,.2f} {unit}"); value_label.setObjectName("chartRowValue"); arrow = FluentToolButton(); arrow.setText("›"); arrow.setFixedSize(28, 24); arrow.clicked.connect(lambda _=False, mode=label: self.clicked_mode.emit(mode)); layout.addWidget(dot); layout.addWidget(name); layout.addStretch(); layout.addWidget(value_label); layout.addWidget(arrow); self.mode_rows.addWidget(row)
        self.mode_rows_host.setVisible(bool(labels))
        self.legend.setText("堆积条显示原始总量；下方按制式列出实际数值")

    def set_pie_details(self, labels, values, colors, unit):
        self.pie_details = (list(labels), list(values), list(colors), unit)

    def show_pie_details(self):
        if not self.pie_details:
            return
        labels, values, colors, unit = self.pie_details
        self.pie_expanded = True
        self.chart.setVisible(False)
        self.mode_rows_host.setVisible(False)
        self.pie.setMinimumHeight(400); self.pie.setMaximumHeight(520); self.pie.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        chart = QChart(); chart.setBackgroundVisible(False); chart.legend().setVisible(True); chart.legend().setFont(QApplication.font()); chart.legend().setAlignment(Qt.AlignmentFlag.AlignRight); chart.setMargins(QMargins(8, 4, 8, 4)); series = QPieSeries()
        total = sum(values)
        for label, value, color in zip(labels, values, colors):
            if value <= 0:
                continue
            slice_ = series.append(label, value); slice_.setColor(color); slice_.setLabelFont(QApplication.font()); slice_.setLabelVisible(False); slice_.setLabel(f"{label} {value:,.0f} {unit} ({value / total * 100:.1f}%)" if total else label)
        chart.addSeries(series); self.pie.setChart(chart); self.pie.setVisible(True); self.legend.setText("Top10 + 其他占比（右侧图例显示数量与占比）")
        self.toggle.setText("综合图")

    def restore_aggregate_pie(self):
        if not self.aggregate_pie:
            return
        labels, values, colors, unit = self.aggregate_pie
        self.pie_expanded = False
        self.chart.setVisible(True)
        self.pie.setFixedHeight(210)
        self.show_stacked(labels, values, colors, unit)

    def show_ranking(self, labels, values, color, unit):
        self.chart.setVisible(True)
        self.pie_expanded = False
        self.pie.setVisible(False)
        self.chart.set_data("ranking", labels, values, [color] * len(labels), unit)
        self.total_label.setText("排行 Top 10")
        self.pie.setVisible(False); self.mode_rows_host.setVisible(False); self.legend.setText(f"条形右端显示实际数值（{unit}）")


class ParseWorker(QThread):
    progress = Signal(int, str)
    log = Signal(str)
    completed = Signal(dict)
    failed = Signal(str)

    def __init__(self, save_path: Path, managed: Path, parent=None):
        super().__init__(parent)
        attach_card_elevation(self)
        self.save_path = save_path
        self.managed = managed
        self.job_dir = JOBS / uuid.uuid4().hex
        self.cancel_requested = False
        self.process: subprocess.Popen | None = None

    def cancel(self):
        self.cancel_requested = True
        process = self.process
        if process and process.poll() is None:
            try:
                process.terminate()
            except ProcessLookupError:
                pass

    def run_command(self, command: list[str], env: dict[str, str], stage: int, label: str):
        if self.cancel_requested:
            raise RuntimeError("已取消解析")
        self.progress.emit(stage, label)
        log_path = self.job_dir / "backend.log"
        output_lines: list[str] = []
        self.process = subprocess.Popen(command, cwd=PROJECT, env=env, text=True,
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        encoding="utf-8", errors="replace", bufsize=1)
        # Cancellation may arrive while Popen is starting, before self.process exists.
        if self.cancel_requested:
            self.process.terminate()
            self.process.wait()
            self.process = None
            raise RuntimeError("已取消解析")
        assert self.process.stdout is not None
        with log_path.open("a", encoding="utf-8") as log_file:
            for line in self.process.stdout:
                if self.cancel_requested:
                    self.process.terminate()
                    self.process.wait()
                    self.process = None
                    raise RuntimeError("已取消解析")
                line = line.rstrip()
                if line:
                    output_lines.append(line)
                    log_file.write(line + "\n")
                    log_file.flush()
                    self.log.emit(line)
        code = self.process.wait()
        self.process = None
        if code != 0:
            tail = "\n".join(output_lines[-12:])
            detail = f"\n\n{tail}" if tail else ""
            raise RuntimeError(f"{label}失败（退出码 {code}）{detail}\n\n完整日志：{log_path}")

    def run(self):
        try:
            if self.save_path.suffix.lower() != ".save":
                raise ValueError("请选择 .save 存档文件")
            if not self.save_path.exists():
                raise FileNotFoundError(f"存档不存在：{self.save_path}")
            if not (self.managed / "Assembly-CSharp.dll").exists():
                raise FileNotFoundError("安装包缺少内置的 CIM2 v1.6.3 程序集，请重新下载完整 EXE")
            self.job_dir.mkdir(parents=True, exist_ok=True)
            env = os.environ.copy()
            env.update({
                "CIM2_EXPORT_DIR": str(self.job_dir),
                "CIM2_PAYLOAD_DIR": str(self.job_dir),
                "CIM2_RUNTIME_DATA_DIR": str(RUNTIME_DATA),
                "CIM2_MANAGED_ROOT": str(self.managed),
                "PYTHONIOENCODING": "utf-8",
            })
            tag = "运行时" if self.save_path.stem == "望春市6" else f"{self.save_path.stem}_运行时"
            if getattr(sys, "frozen", False):
                # The parser is embedded in this same one-file executable.
                command = [str(sys.executable), "--backend", str(self.save_path), tag]
                self.run_command(command, env, 10, "读取存档对象并生成报表")
            else:
                python = sys.executable
                self.run_command([python, str(SRC / "extract_runtime_data.py"), str(self.save_path)], env, 10, "读取存档对象")
                self.run_command([python, str(SRC / "build_line_workbook.py"), tag], env, 70, "生成线路工作簿")
                self.run_command([python, str(SRC / "build_company_workbook.py"), tag], env, 82, "生成公司工作簿")
            self.progress.emit(92, "校验并建立查询索引")
            data = load_session(self.job_dir, tag, CATALOG_DIR)
            line_xlsx = self.job_dir / f"CIM2_线路发班整理_{tag}.xlsx"
            company_xlsx = self.job_dir / f"CIM2_公司信息整理_{tag}.xlsx"
            expected_sheets = ((line_xlsx, {"线路信息", "公司概览"}), (company_xlsx, {"表1_公司信息", "表2_人员表", "表3_票价表", "表4_周收支表"}))
            self.log.emit('CIM2_PROGRESS ' + json.dumps(dict(event='progress', phase='validation', done=0, total=len(expected_sheets))))
            for workbook_index, (workbook_path, required) in enumerate(expected_sheets, 1):
                if not workbook_path.exists():
                    raise RuntimeError(f"未生成工作簿：{workbook_path.name}")
                workbook = load_workbook(workbook_path, read_only=True, data_only=True)
                missing = required - set(workbook.sheetnames)
                if missing:
                    raise RuntimeError(f"工作簿缺少工作表：{', '.join(sorted(missing))}")
                for sheet in workbook.worksheets:
                    for row in sheet.iter_rows():
                        for cell in row:
                            if isinstance(cell.value, str) and cell.value.startswith("#"):
                                raise RuntimeError(f"工作簿存在错误值：{sheet.title}!{cell.coordinate}")
                workbook.close()
                self.log.emit('CIM2_PROGRESS ' + json.dumps(dict(event='progress', phase='validation', done=workbook_index, total=len(expected_sheets))))
            manifest = {
                "job_id": self.job_dir.name,
                "save_path": str(self.save_path),
                "save_type": data["save_type"],
                "simulation_date": data["metadata"].get("当前日期", ""),
                "simulation_time": data["metadata"].get("当前时间", ""),
                "company_count": data["counts"].get("companies", 0),
                "line_count": data["counts"].get("lines", 0),
                "vehicle_count": data["counts"].get("vehicles", 0),
                "timetable_count": data["counts"].get("timetables", 0),
                "departure_count": data["counts"].get("departures", 0),
                "output_files": {
                    "line_workbook": str(self.job_dir / f"CIM2_线路发班整理_{tag}.xlsx"),
                    "company_workbook": str(self.job_dir / f"CIM2_公司信息整理_{tag}.xlsx"),
                },
                "validation_status": "通过",
                "warnings": [],
            }
            (self.job_dir / "manifest.json").write_text(__import__("json").dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            data["manifest"] = manifest
            data["outputs"] = {
                "line_workbook": self.job_dir / f"CIM2_线路发班整理_{tag}.xlsx",
                "company_workbook": self.job_dir / f"CIM2_公司信息整理_{tag}.xlsx",
            }
            data["save_path"] = str(self.save_path)
            data["save_key"] = save_fingerprint(self.save_path)
            data["managed_root"] = str(self.managed)
            data["validation_status"] = "通过"
            if self.cancel_requested:
                raise RuntimeError("已取消解析")
            self.progress.emit(100, "完成")
            self.completed.emit(data)
        except Exception as exc:
            if self.cancel_requested:
                self.failed.emit("已取消解析")
            else:
                self.failed.emit(str(exc))


class ChartWidget(QChartView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(260, 160)
        self.setMaximumHeight(280)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)

    def show_bar(self, title: str, labels: list[str], values: list[float], color="#0b6e69"):
        chart = QChart(); chart.setTitle(title); chart.legend().setVisible(False)
        series = QBarSeries(); bars = QBarSet(title); bars.setColor(color)
        bars.append(values); series.append(bars); chart.addSeries(series)
        axis = QBarCategoryAxis(); axis.append(labels); chart.addAxis(axis, Qt.AlignmentFlag.AlignBottom)
        y_axis = QValueAxis(); y_axis.setRange(0, max(max(values, default=0) * 1.2, 1)); chart.addAxis(y_axis, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis); series.attachAxis(y_axis); chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)
        self.setChart(chart)

    def show_grouped_bar(self, title: str, labels: list[str], series_data: list[tuple[str, list[float], str]]):
        chart = QChart(); chart.setTitle(title)
        series = QBarSeries()
        maximum = 0
        for name, values, color in series_data:
            bars = QBarSet(name); bars.append(values); bars.setColor(color); series.append(bars)
            maximum = max(maximum, max(values, default=0))
        chart.addSeries(series)
        axis = QBarCategoryAxis(); axis.append(labels); chart.addAxis(axis, Qt.AlignmentFlag.AlignBottom)
        y_axis = QValueAxis(); y_axis.setRange(0, max(maximum * 1.2, 1)); chart.addAxis(y_axis, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis); series.attachAxis(y_axis); chart.legend().setVisible(True)
        self.setChart(chart)

    def show_pie(self, title: str, labels: list[str], values: list[float]):
        chart = QChart(); chart.setTitle(title); series = QPieSeries()
        for label, value in zip(labels, values):
            if value:
                series.append(label, value)
        chart.addSeries(series); chart.legend().setVisible(True); self.setChart(chart)

    def show_lines(self, title: str, points: list[tuple[str, float]], color="#0b6e69"):
        chart = QChart(); chart.setTitle(title); chart.legend().setVisible(False)
        series = QLineSeries(); series.setColor(color)
        for index, (_, value) in enumerate(points):
            series.append(index, value)
        chart.addSeries(series); chart.createDefaultAxes(); self.setChart(chart)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        initialize_theme(QApplication.instance())
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.resize(1800, 1080)
        self.setMinimumSize(920, 680)
        self.setAcceptDrops(True)
        self.settings = QSettings("CIM2SaveStats", "Desktop")
        self.data: dict = {}
        self.worker: ParseWorker | None = None
        self.selected_key = ""
        self.build_ui()
        self._enable_mica()
        self.check_install()

    def _enable_mica(self):
        self.setProperty('nativeMicaEnabled', False)
        if (sys.platform != 'win32' or sys.getwindowsversion().build < 22000 or
                QApplication.platformName() == 'offscreen'):
            return
        from qframelesswindow import WindowEffect
        self.setObjectName('micaMainWindow')
        self.setStyleSheet('QMainWindow#micaMainWindow { background: transparent; }')
        if not hasattr(self, '_mica_effect'):
            self._mica_effect = WindowEffect(self)
        self._mica_effect.setMicaEffect(self.winId(), isDarkMode=False, isAlt=False)
        self.setProperty('nativeMicaEnabled', True)

    def showEvent(self, event):
        super().showEvent(event)
        # The native HWND/backing surface is finalized on show. Apply again,
        # as FluentWidget does, so transparent client pixels reach the backdrop.
        self._enable_mica()

    def build_ui(self):
        shell = QWidget(); self.setCentralWidget(shell); outer = QHBoxLayout(shell); outer.setContentsMargins(0, 0, 0, 0); outer.setSpacing(0)
        sidebar = NavigationInterface(shell); self.sidebar = sidebar; sidebar.setExpandWidth(NAV_WIDTH_EXPANDED); sidebar.setMinimumExpandWidth(750)
        sidebar.displayModeChanged.connect(self._navigation_mode_changed)
        self.nav_buttons = []
        for text, index, icon, route in (("最新信息", 0, FluentIcon.HOME, 'overview'),
                                         ("线路查询", 1, FluentIcon.SEARCH, 'lines'),
                                         ("统计数据", 2, FluentIcon.PIE_SINGLE, 'statistics')):
            button = sidebar.addItem(route, icon, text, onClick=lambda checked=False, i=index: self.navigate(i), tooltip=text)
            self.nav_buttons.append(button)
        from about_dialog import show_about_dialog
        self.about_button = sidebar.addItem(
            'about', FluentIcon.INFO, '关于', position=NavigationItemPosition.BOTTOM,
            onClick=lambda checked=False: show_about_dialog(self, root=BUNDLE_ROOT),
            selectable=False, tooltip='关于')
        outer.addWidget(sidebar)
        self._sidebar_collapsed = False
        self.set_sidebar_collapsed(str(self.settings.value('shell/sidebar_collapsed', 'false')).lower() == 'true')
        content = QWidget(); self.content_host = content; content_lay = QVBoxLayout(content); self.content_layout = content_lay; content_lay.setContentsMargins(20, 20, 20, 20); content_lay.setSpacing(8); head = QHBoxLayout(); self.page_title = QLabel("最新信息"); self.page_title.setObjectName("pageTitle"); head.addWidget(self.page_title); head.addStretch(); self.current_save = ElidedLabel(""); self.current_save.setObjectName("muted"); self.current_save.setMaximumWidth(210); head.addWidget(self.current_save); self.export_line_button = PushButton("导出线路 XLSX"); self.export_line_button.setEnabled(False); self.export_line_button.clicked.connect(lambda: self.export_file("line_workbook")); head.addWidget(self.export_line_button); self.export_company_button = PushButton("导出公司 XLSX"); self.export_company_button.setEnabled(False); self.export_company_button.clicked.connect(lambda: self.export_file("company_workbook")); head.addWidget(self.export_company_button); open_btn = PrimaryPushButton("打开存档"); open_btn.setIcon(FluentIcon.FOLDER); open_btn.clicked.connect(self.open_dialog); head.addWidget(open_btn); self.cancel_action = PushButton("取消解析"); self.cancel_action.setEnabled(False); self.cancel_action.clicked.connect(self.cancel_parse); head.addWidget(self.cancel_action); self.legacy_header = QWidget(content); self.legacy_header.setLayout(head); content_lay.addWidget(self.legacy_header)
        self._build_stats_header(content)
        content_lay.addWidget(self.stats_header)
        self.stats_header.hide()
        self.pages = QStackedWidget(); content_lay.addWidget(self.pages, 1); outer.addWidget(content, 1)
        self.build_overview(); self.build_lines()
        self.statistics_page = StatisticsPage(self.settings)
        self.pages.addWidget(self.statistics_page)
        self._place_stats_tabs()
        self.statistics_page.stats_integration.export_failed.connect(lambda _error: self.status_label.setText("导出失败"))
        self.sidebar.setCurrentItem('overview')
        self.status_label = ElidedLabel('', content)
        self.status_label.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: 12px;')
        self.status_label.hide()
        self.progress = FluentProgressBar(content)
        self.progress.hide()
        self.context_label = ElidedLabel("未载入存档", content)
        self.context_label.hide()
        self.statusBar().hide()
        self.line_footer = QWidget(content)
        self.line_footer.setFixedHeight(18)
        footer_row = QHBoxLayout(self.line_footer); footer_row.setContentsMargins(0,0,0,0)
        self.context_label.setParent(self.line_footer); self.context_label.show()
        self.context_label.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: 11px;')
        footer_row.addWidget(self.context_label, 1)
        self.line_size_label = QLabel('')
        self.line_size_label.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: 11px;')
        self.line_size_label.hide()
        content_lay.addWidget(self.line_footer)
        self.line_footer.hide()
        self.loading_overlay = LoadingOverlay(content, self.cancel_parse)
        self._progress_predictor = None
        self._parse_stage = 0
        self._parse_stage_text = ''
        self._parse_started = 0.0
        self._progress_timer = QTimer(self)
        self._progress_timer.setInterval(250)
        self._progress_timer.timeout.connect(self._update_estimated_progress)
        self._awaiting_dashboards = False
        self._ready_timer = QTimer(self)
        self._ready_timer.setInterval(30)
        self._ready_timer.timeout.connect(self._check_dashboard_ready)
        self.statistics_page.query_failed.connect(self._dashboard_failed)
        self._connect_latest_info()
        self.navigate(0)

    def _build_stats_header(self, parent):
        header = QWidget(parent)
        header.setObjectName('statsHeader')
        header.setMinimumHeight(48)
        row = QHBoxLayout(header)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(12)
        icon_base = QFrame(header)
        icon_base.setFixedSize(40, 40)
        icon_base.setStyleSheet(f'QFrame {{ background: {ACCENT_SOFT}; border: 0; border-radius: 9px; }}')
        icon_row = QHBoxLayout(icon_base)
        icon_row.setContentsMargins(9, 9, 9, 9)
        icon = IconWidget(icon_base)
        icon.setIcon(FluentIcon.PIE_SINGLE.icon(color=QColor(ACCENT)))
        icon.setFixedSize(22, 22)
        icon_row.addWidget(icon)
        row.addWidget(icon_base)
        title_column = QVBoxLayout()
        title_column.setSpacing(2)
        title = QLabel('统计数据', header)
        title.setObjectName('statsTitle')
        title.setStyleSheet(f'font-size: {FONT_SIZE_PAGE_TITLE}px; font-weight: 600; color: {TEXT_PRIMARY};')
        self.stats_title = title
        self.stats_icon_base = icon_base
        self.stats_icon = icon
        self.stats_icon_row = icon_row
        title_column.addWidget(title)
        row.addLayout(title_column)
        row.addStretch()
        file_panel = QFrame(header)
        file_panel.setObjectName('statsFilePanel')
        file_panel.setStyleSheet(f'QFrame#statsFilePanel {{ background: {CARD_BG}; '
                                 f'border: 1px solid {BORDER}; border-radius: 8px; }}')
        file_row = QHBoxLayout(file_panel)
        file_row.setContentsMargins(10, 6, 10, 6)
        file_row.setSpacing(8)
        file_icon = IconWidget(file_panel)
        file_icon.setIcon(FluentIcon.SAVE.icon(color=QColor(TEXT_PRIMARY)))
        file_icon.setFixedSize(16, 16)
        file_row.addWidget(file_icon)
        file_text = QVBoxLayout()
        file_text.setSpacing(0)
        self.stats_file_name = ElidedLabel('未载入存档', file_panel)
        self.stats_file_name.setMaximumWidth(260)
        self.stats_file_name.setStyleSheet(f'color: {TEXT_PRIMARY}; font-size: 14px;')
        self.stats_file_time = ElidedLabel('', file_panel)
        self.stats_file_time.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: 12px;')
        file_text.addWidget(self.stats_file_name)
        file_text.addWidget(self.stats_file_time)
        file_row.addLayout(file_text, 1)
        file_panel.setMaximumWidth(330)
        file_panel.setMinimumWidth(240)
        row.addWidget(file_panel)
        self.stats_open_button = PrimaryPushButton('打开存档', header)
        self.stats_open_button.setIcon(FluentIcon.FOLDER)
        self.stats_open_button.setMinimumHeight(36)
        self.stats_open_button.setFixedWidth(ACTION_BUTTON_WIDTH)
        self.stats_open_button.clicked.connect(self.open_dialog)
        row.addWidget(self.stats_open_button)
        self.stats_more_button = TransparentToolButton(header)
        self.stats_more_button.setIcon(FluentIcon.MORE)
        self.stats_more_button.setToolTip('更多操作')
        self.stats_more_button.setAccessibleName('更多操作')
        self.stats_more_button.setFixedSize(36, 36)
        self.stats_more_menu = RoundMenu(parent=self.stats_more_button)
        for title, kind in (('导出线路 XLSX', 'line_workbook'), ('导出公司 XLSX', 'company_workbook')):
            action = Action(title, self.stats_more_menu)
            action.triggered.connect(lambda checked=False, selected=kind: self.export_file(selected))
            self.stats_more_menu.addAction(action)
        self.stats_more_button.clicked.connect(
            lambda: self.stats_more_menu.exec(self.stats_more_button.mapToGlobal(
                QPoint(0, self.stats_more_button.height()))))
        row.addWidget(self.stats_more_button)
        self.stats_header = header

    def _place_stats_tabs(self):
        if not hasattr(self, 'statistics_page'):
            return
        wide = self.width() >= 1200
        tab = self.statistics_page.tab_bar
        if wide and tab.parentWidget() is not self.stats_header:
            self.statistics_page.layout().removeWidget(tab)
            tab.setParent(self.stats_header)
            self.stats_header.layout().insertWidget(2, tab)
            tab.show()
        elif not wide and tab.parentWidget() is not self.statistics_page:
            self.stats_header.layout().removeWidget(tab)
            tab.setParent(self.statistics_page)
            self.statistics_page.layout().insertWidget(0, tab)
            tab.show()
        if self.width() >= 2200:
            title_size, icon_size, glyph_size, header_height = 28, 44, 24, 60
            tab_size, tab_width = 15, 132
        elif self.width() >= 1600:
            title_size, icon_size, glyph_size, header_height = 25, 38, 22, 52
            tab_size, tab_width = 14, 124
        else:
            title_size, icon_size, glyph_size, header_height = 23, 36, 20, 48
            tab_size, tab_width = 13, 116
        self.stats_header.setMinimumHeight(header_height)
        self.stats_title.setStyleSheet(
            f'font-size: {title_size}px; font-weight: 600; color: {TEXT_PRIMARY};')
        self.stats_icon_base.setFixedSize(icon_size, icon_size)
        self.stats_icon.setFixedSize(glyph_size, glyph_size)
        inset = (icon_size - glyph_size) // 2
        self.stats_icon_row.setContentsMargins(inset, inset, inset, inset)
        tab.setItemFontSize(tab_size)
        tab.setFixedWidth(3 * tab_width)
        tab.setFixedHeight(36 if wide else 40)
        for item in tab.items.values():
            item.setFixedWidth(tab_width)
            item.setFixedHeight(36 if wide else 40)
            item.setIconSize(QSize(16 if wide else 18, 16 if wide else 18))

    def toggle_sidebar(self):
        self.set_sidebar_collapsed(not self._sidebar_collapsed)

    def _navigation_mode_changed(self, mode):
        collapsed = mode not in (NavigationDisplayMode.EXPAND, NavigationDisplayMode.MENU)
        self._sidebar_collapsed = collapsed
        self.settings.setValue('shell/sidebar_collapsed', collapsed)
        QTimer.singleShot(0, self._fit_overview_metric_height)

    def set_sidebar_collapsed(self, collapsed):
        self._sidebar_collapsed = bool(collapsed)
        if collapsed:
            panel = self.sidebar.panel
            panel.collapse()
            panel.expandAni.stop()
            panel.resize(48, panel.height())
            panel._onExpandAniFinished()
            self.sidebar.setFixedWidth(48)
        else:
            self.sidebar.expand(False)
        self.settings.setValue('shell/sidebar_collapsed', bool(collapsed))
        QTimer.singleShot(0, self._fit_overview_metric_height)

    def navigate(self, index):
        from stats_motion import SurfaceMotion
        previous_page = self.pages.currentWidget()
        changed = self.pages.currentIndex() != index
        if changed and previous_page is not None:
            previous_motion = getattr(previous_page, 'motion', getattr(previous_page, '_navigation_motion', None))
            if previous_motion is not None:
                previous_motion.finish()
        self.pages.setCurrentIndex(index)
        self.page_title.setText(("最新信息", "线路查询", "统计数据")[index])
        self._fit_page_margins(index)
        self.content_layout.setSpacing(6 if index == 1 else 8)
        self.page_title.setStyleSheet(f'font-family:"Microsoft YaHei UI";font-size:{FONT_SIZE_PAGE_TITLE}px;font-weight:600;color:{TEXT_PRIMARY};')
        self.export_line_button.setVisible(index != 2)
        self.export_company_button.setVisible(index != 2)
        self.legacy_header.setVisible(index == 1)
        self.legacy_header.setFixedHeight(44 if index == 1 else 48)
        self.legacy_header.layout().setContentsMargins(0,0,0,0)
        for action_button in (self.export_line_button, self.export_company_button, self.cancel_action):
            action_button.setFixedHeight(36)
        if index == 1:
            self.legacy_header.setStyleSheet('QLabel, QPushButton {font-family: "Microsoft YaHei UI";}')
        self.stats_header.setVisible(index == 2)
        self.line_footer.hide()
        self.content_host.setAutoFillBackground(index == 1)
        if index == 1:
            palette = self.content_host.palette()
            palette.setColor(QPalette.ColorRole.Window, QColor(PAGE_BG))
            self.content_host.setPalette(palette)
        self.sidebar.setCurrentItem(('overview', 'lines', 'statistics')[index])
        if index == 1:
            self.set_sidebar_collapsed(True)
            self.sidebar.setFixedWidth(56)
        elif self._sidebar_collapsed:
            self.sidebar.setFixedWidth(48)
        if changed:
            page = self.pages.currentWidget()
            motion = getattr(page, 'motion', getattr(page, '_navigation_motion', None))
            if motion is None:
                motion = SurfaceMotion(page)
                page._navigation_motion = motion
            motion.reveal(float_in=True)

    def _fit_page_margins(self, index):
        if index == 1:
            self.content_layout.setContentsMargins(16, 4, 16, 4)
        else:
            margin = 12 if self.width() < 1000 else 20
            self.content_layout.setContentsMargins(margin, 12 if index == 2 else margin,
                                                   margin, 0 if index == 2 else margin)

    def closeEvent(self, event):
        self._closing_app = True
        self._ready_timer.stop()
        self._progress_timer.stop()
        self.loading_overlay.finish()
        self.statistics_page.stop_workers()
        if not self.latest_info_controller.stop_workers():
            event.ignore()
            for task in self.latest_info_controller.workers:
                if task.isRunning():
                    task.finished.connect(self.close)
            return
        worker = self.worker
        if worker and worker.isRunning():
            worker.cancel()
            if not worker.wait(3000):
                # Keep the thread's parent alive until CPU-side parsing has stopped.
                event.ignore()
                if not getattr(self, '_close_waiting', False):
                    self._close_waiting = True
                    worker.finished.connect(self.close)
                return
        super().closeEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._place_stats_tabs()
        if hasattr(self, 'content_layout'):
            self._fit_page_margins(self.pages.currentIndex() if hasattr(self, 'pages') else 0)
        if hasattr(self, 'sidebar') and self.width() < 1000 and not self._sidebar_collapsed:
            self.set_sidebar_collapsed(True)
        if hasattr(self, 'facts_grid'):
            QTimer.singleShot(0, self._fit_fact_height)
        if hasattr(self, 'line_size_label'):
            frame = self.frameGeometry().size()
            self.line_size_label.setText(f'{frame.width()} × {frame.height()} 整窗')

    def eventFilter(self, watched, event):
        if (hasattr(self, 'fact_scroll') and isValid(self.fact_scroll)
                and watched is self.fact_scroll.viewport()
                and event.type() == QEvent.Type.Resize):
            QTimer.singleShot(0, self._fit_fact_height)
        return super().eventFilter(watched, event)

    def _fit_fact_height(self):
        if isValid(self) and hasattr(self, 'facts_grid'):
            self.facts_grid.activate()

    def build_overview(self):
        from latest_info_page import LatestInfoPage
        from latest_info_controller import LatestInfoController
        self.latest_info_page = LatestInfoPage(self.settings)
        self.overview_tab = self.latest_info_page
        self.company_combo = self.latest_info_page.company_combo
        self.mode_combo = self.latest_info_page.mode_combo
        self.latest_info_controller = LatestInfoController(self.latest_info_page, self.settings, self)
        self.pages.addWidget(self.latest_info_page)

    def _connect_latest_info(self):
        page, controller = self.latest_info_page, self.latest_info_controller
        page.open_save_requested.connect(lambda: self.open_dialog())
        page.line_export_requested.connect(lambda: self.export_file('line_workbook'))
        page.company_export_requested.connect(lambda: self.export_file('company_workbook'))
        page.line_requested.connect(self._open_latest_line)
        controller.thresholds_changed.connect(self.statistics_page.set_thresholds)
        self.statistics_page.set_thresholds(controller.thresholds)
        controller.snapshot_changed.connect(self._latest_info_ready)
        controller.query_failed.connect(lambda error: self._dashboard_failed(str(error)))
        controller.export_failed.connect(self._latest_export_failed)

    def _latest_info_ready(self, snapshot):
        if snapshot is None or self.data is not self.latest_info_controller.data:
            return
        if snapshot.simulation_time is not None and self.statistics_page.store is None:
            # A has already validated/combined the simulated clock. Statistics keeps
            # its existing model and filters but receives a normalized clock.
            data = dict(self.data, simulation_time=snapshot.simulation_time.isoformat(sep=' '))
            self.statistics_page.set_session(data)
        if self._awaiting_dashboards:
            self._check_dashboard_ready()

    def _latest_export_failed(self, error):
        self.status_label.setText('导出失败')
        QMessageBox.critical(self, '导出失败', str(error))

    def _open_latest_line(self, key):
        line = next((row for row in self.data.get('lines', []) if row.get('key') == key), None)
        if line is None:
            return
        self.navigate(1)
        self.query.clear()
        self.line_company.setCurrentIndex(max(0, self.line_company.findData(str(line.get('公司标识') or ''))))
        self.line_mode.setCurrentIndex(max(0, self.line_mode.findData(line.get('运输制式') or '')))
        self.selected_key = key
        self.refresh_lines()

    def _fit_overview_metric_height(self):
        if isValid(self) and hasattr(self, 'latest_info_page') and isValid(self.latest_info_page):
            self.latest_info_page.updateGeometry()

    def build_lines(self):
        from line_query_page import LinesPage
        from line_schedule_view import SchedulePanel
        self.lines_page = LinesPage(self, SchedulePanel)
        self.lines_tab = self.lines_page
        for name in ('query', 'line_company', 'line_mode', 'line_columns_button',
                     'line_columns_menu', 'line_count', 'line_table', 'detail_title',
                     'fact_menu_button', 'fact_menu', 'facts_host', 'facts_grid',
                     'schedule_panel'):
            setattr(self, name, getattr(self.lines_page, name))
        self.fact_cards = []
        self.pages.addWidget(self.lines_page)

    def build_catalog_page(self):
        page = QWidget(); layout = QVBoxLayout(page); layout.addWidget(QLabel("车型参数", objectName="sectionTitle")); self.catalog_table = FluentTableWidget(); self.catalog_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); layout.addWidget(self.catalog_table); self.pages.addWidget(page)

    def build_export_page(self):
        page = QWidget(); layout = QVBoxLayout(page); layout.addWidget(QLabel("导出工作簿", objectName="sectionTitle")); self.export_line_button = PushButton("导出线路 XLSX"); self.export_line_button.setEnabled(False); self.export_line_button.clicked.connect(lambda: self.export_file("line_workbook")); self.export_company_button = PushButton("导出公司 XLSX"); self.export_company_button.setEnabled(False); self.export_company_button.clicked.connect(lambda: self.export_file("company_workbook")); layout.addWidget(self.export_line_button); layout.addWidget(self.export_company_button); layout.addStretch(); self.pages.addWidget(page)

    def check_install(self):
        managed = locate_managed(self.settings.value("managed_root", ""))
        if managed is None:
            self.status_label.setText("安装包缺少内置的 CIM2 v1.6.3 程序集")
        else:
            self.status_label.setText("等待导入 .save 存档")

    def choose_managed(self):
        selected = QFileDialog.getExistingDirectory(self, "选择 CIM2_Data 或 Managed 目录")
        if not selected:
            return
        managed = locate_managed(selected)
        if managed is None:
            QMessageBox.warning(self, "程序集不可用", "所选目录中没有 Assembly-CSharp.dll")
            return
        self.settings.setValue("managed_root", str(managed)); self.status_label.setText(f"已设置程序集目录：{managed}")

    def open_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "打开 Cities in Motion 2 存档", "", "Cities in Motion 2 存档 (*.save)")
        if path:
            self.start_parse(Path(path))

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls() and any(url.toLocalFile().lower().endswith(".save") for url in event.mimeData().urls()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            if path.suffix.lower() == ".save":
                self.start_parse(path); event.acceptProposedAction(); return
        event.ignore()

    def start_parse(self, path: Path):
        # Normalize Unicode paths before crossing the Qt/subprocess boundary.
        # ``os.fsdecode`` keeps non-ASCII filenames intact on Windows and
        # avoids the short-name conversion that caused repeat imports to fail.
        path = Path(os.fsdecode(str(path))).expanduser().resolve()
        running = False
        if self.worker:
            try:
                running = self.worker.isRunning()
            except RuntimeError:
                # The C++ QThread may already be deleted while the queued
                # finished signal is being delivered.
                self.worker = None
        if running:
            QMessageBox.information(self, "正在解析", "当前任务尚未完成，请先取消或等待完成")
            return
        managed = locate_managed(self.settings.value("managed_root", ""))
        if managed is None:
            if getattr(sys, "frozen", False):
                QMessageBox.critical(self, "安装包不完整", "当前 EXE 缺少内置的 CIM2 v1.6.3 程序集，请重新下载完整 EXE。")
            else:
                result = QMessageBox.warning(self, "缺少游戏程序集", "未找到 v1.6.3 程序集。现在选择安装目录？", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if result == QMessageBox.StandardButton.Yes:
                    self.choose_managed(); managed = locate_managed(self.settings.value("managed_root", ""))
            if managed is None:
                return
        self._ready_timer.stop()
        self._awaiting_dashboards = False
        self.latest_info_controller.clear_session()
        self.data = {}; self.statistics_page.clear_session(); self.current_save.setText(""); self.selected_key = ""; self.passenger_view = "stacked"; self.departure_view = "stacked"; self.passenger_mode = ""; self.departure_mode = ""
        # Clear the previous session immediately so a replacement import
        # cannot leave stale rows, charts, or export actions on screen.
        self.line_company.clear(); self.line_mode.clear()
        self.line_table.setRowCount(0); self.clear_fact_cards(); self.clear_schedule_tabs()
        self._selected_line=None
        self.lines_page.list_footer.setText('从列表选择线路')
        self.export_line_button.setEnabled(False); self.export_company_button.setEnabled(False); self.progress.hide(); self.progress.setValue(0); self.cancel_action.setEnabled(True); self.status_label.setText(f"准备解析：{path.name}")
        self.stats_file_name.setText(path.name)
        self.stats_file_name.setToolTip(str(path))
        self.stats_file_time.setText("正在读取存档")
        self._progress_predictor = ParseProgressEstimator(path.stat().st_size if path.exists() else 0)
        self._parse_started = time.monotonic()
        self._parse_stage, self._parse_stage_text = 0, '准备读取存档'
        self.loading_overlay.begin("准备读取存档")
        self._progress_timer.start()
        worker = ParseWorker(path, managed, self)
        self.worker = worker
        def current():
            return self.worker is worker and not getattr(self, '_closing_app', False)
        worker.progress.connect(lambda value, text: self.on_progress(value, text) if current() else None)
        worker.log.connect(lambda text: self.on_parse_log(text) if current() else None)
        worker.completed.connect(lambda data: self.on_completed(data) if current() else None)
        worker.failed.connect(lambda message: self.on_failed(message) if current() else None)
        worker.finished.connect(lambda: self.worker_finished(worker))
        worker.start()

    def worker_finished(self, worker=None):
        # Drop the finished thread before the next import.  Keeping a Python
        # reference to a deleted QThread can make ``isRunning`` raise and
        # leave the second import button apparently unresponsive.
        worker = worker if worker is not None else self.worker
        if self.worker is worker:
            self.worker = None
            if not self._awaiting_dashboards:
                self.loading_overlay.finish()
                self._progress_timer.stop()
        if worker:
            worker.deleteLater()

    def cancel_parse(self):
        if self._awaiting_dashboards:
            if self.worker:
                self.worker.cancel()
            self.on_failed('已取消解析')
        elif self.worker:
            self.worker.cancel(); self.status_label.setText("正在取消…")
            self.loading_overlay.cancel_button.setEnabled(False)
            self.loading_overlay.update_progress("正在取消…")

    def on_progress(self, value, label):
        self.progress.setValue(value); self.status_label.setText(label)
        # Existing values are stage weights, not measured object percentages.
        self._parse_stage = min(value, 99)
        self._parse_stage_text = '准备图表' if value == 100 else label
        self._update_estimated_progress()

    def _update_estimated_progress(self):
        predictor = self._progress_predictor
        percent = None
        worker = self.worker
        cancelling = worker is not None and worker.cancel_requested
        if predictor is not None and not cancelling:
            rss = 0
            process = worker.process if worker is not None else None
            if process is not None:
                try:
                    root = psutil.Process(process.pid)
                    rss = sum(p.memory_info().rss for p in [root, *root.children(recursive=True)])
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            percent = predictor.update(time.monotonic() - self._parse_started, rss, self._parse_stage)
        estimated = percent is not None and percent < 100 and not getattr(predictor, 'actual_progress', False)
        self.loading_overlay.update_progress(self._parse_stage_text, percent, estimated=estimated)

    def on_parse_log(self, text):
        if text.startswith('CIM2_PROGRESS '):
            try:
                details = json.loads(text.removeprefix('CIM2_PROGRESS '))
            except (ValueError, TypeError):
                return
            if isinstance(details, dict) and self._progress_predictor is not None:
                if details.get('event') == 'progress':
                    done, total = details.get('done'), details.get('total')
                    if type(done) is not int or type(total) is not int or total <= 0 or not 0 <= done <= total:
                        return
                    phase = {'lines': '提取线路', 'history': '读取历史记录',
                             'line_workbook': '生成线路报表', 'company_workbook': '生成公司报表',
                             'validation': '校验输出'}.get(details.get('phase'))
                    if phase:
                        self._parse_stage_text = f'{phase}：{done}/{total}'
                observer = getattr(self._progress_predictor, 'observe', None)
                if callable(observer):
                    observer(time.monotonic() - self._parse_started, details)
                self._update_estimated_progress()
            return
        self.status_label.setText(text)
        self.status_label.setToolTip(text)
        self._parse_stage_text = text
        self._update_estimated_progress()

    def on_failed(self, message):
        self.latest_info_controller.clear_session()
        self.statistics_page.clear_session()
        self.data = {}
        self.export_line_button.setEnabled(False)
        self.export_company_button.setEnabled(False)
        self._awaiting_dashboards = False
        self._ready_timer.stop()
        self.loading_overlay.finish()
        self._progress_timer.stop()
        self.cancel_action.setEnabled(False); self.progress.hide()
        self.status_label.setText(message)
        self.status_label.setToolTip(message)
        self.stats_file_time.setText('已取消读取' if message == '已取消解析' else '读取失败')
        if message != '已取消解析':
            QMessageBox.critical(self, "解析失败", message)

    def on_completed(self, data):
        self.selected_key=''; self._selected_line=None
        self.clear_fact_cards(); self.clear_schedule_tabs()
        self.detail_title.setText('选择线路查看详情')
        self.lines_page.list_footer.setText('从列表选择线路')
        self._awaiting_dashboards = True
        self._ready_started = time.monotonic()
        self._ready_data = data
        self._parse_stage, self._parse_stage_text = 99, '准备图表'
        self.loading_overlay.update_progress('准备图表')
        self._ready_timer.start()
        self.data = data; self.progress.setVisible(False)
        self.statistics_page.clear_session()
        self.latest_info_controller.set_session(data)
        self.export_line_button.setEnabled(self.latest_info_controller.workbook_source("line_workbook") is not None)
        self.export_company_button.setEnabled(self.latest_info_controller.workbook_source("company_workbook") is not None)
        counts = data.get("counts", {})
        kind = "多人" if data.get("save_type") == "multiplayer" else "单人"
        meta = data.get("metadata", {})
        save_name = Path(data["save_path"]).name
        self.current_save.setText(save_name)
        self.current_save.setToolTip(save_name)
        self.stats_file_name.setText(save_name)
        self.stats_file_name.setToolTip(save_name)
        self.stats_file_name.setAccessibleName(save_name)
        try:
            simulation = parse_time(data.get('simulation_time'))
        except (TypeError, ValueError, AttributeError):
            simulation = None
        total_companies = counts.get('companies', len(data.get('companies', ())))
        clock = f'{simulation:%Y-%m-%d %H:%M:%S}' if simulation else '模拟时间未提供'
        info = f'{clock} · {kind} · {total_companies}个公司'
        self.stats_file_time.setText(info)
        self.stats_file_time.setToolTip(info)
        self.stats_file_time.setAccessibleName(self.stats_file_time.toolTip())
        self.status_label.clear()
        self.context_label.setText(f"{kind} · {save_name} · {meta.get('当前日期', '')} {meta.get('当前时间', '')} · 人口 {int(meta.get('当前人口数', 0)):,}")
        self.line_company.blockSignals(True); self.line_company.clear(); self.line_company.addItem("全部公司", userData="")
        names = [str(x.get('公司名称', '')) for x in data.get('companies', [])]
        for company in data.get('companies', []):
            name = str(company.get('公司名称', ''))
            company_id = str(company.get('公司标识') or name)
            display_name = f'{name} [{company_id}]' if names.count(name) > 1 else name
            self.line_company.addItem(display_name, userData=company_id)
        self.line_company.blockSignals(False)
        self.line_mode.blockSignals(True); self.line_mode.clear(); self.line_mode.addItem("全部制式", userData=""); [self.line_mode.addItem(mode, userData=mode) for mode in MODES if any(x["运输制式"] == mode for x in data.get("lines", []))]; self.line_mode.blockSignals(False)
        self.refresh_lines(); self.navigate(0)

    def _dashboard_failed(self, message):
        if self._awaiting_dashboards:
            self.on_failed(f'准备图表失败：{message}')

    def _check_dashboard_ready(self):
        if not self._awaiting_dashboards or self.data is not self._ready_data:
            self._ready_timer.stop()
            return
        page, home = self.statistics_page, self.latest_info_controller
        snapshot = home.snapshot
        home_ready = (snapshot is not None and not home.query_timer.isActive()
                      and not any(worker.isRunning() for worker in home.workers)
                      and (not home.enabled or snapshot.simulation_time is None or home.alerts_snapshot is not None))
        stats_ready = (snapshot is not None and (snapshot.simulation_time is None or
                       (page.snapshot is not None and page.network_snapshot is not None
                        and not page.query_timer.isActive()
                        and not any(worker.isRunning() for worker in (*page.workers, *page.network_workers)))))
        if home_ready and stats_ready:
            self._awaiting_dashboards = False
            self._ready_timer.stop()
            self._progress_timer.stop()
            self.cancel_action.setEnabled(False)
            finish = getattr(self._progress_predictor, 'finish', None)
            if callable(finish):
                finish()
            self.loading_overlay.finish()
        elif time.monotonic() - self._ready_started > 60:
            self.on_failed('准备图表超时，请重新导入存档')

    def company_changed(self):
        self.refresh_company()

    def _company_matches(self, row, selected):
        if not selected:
            return True
        owner = str(row.get('公司标识') or '')
        if owner:
            return owner == selected
        selected_name = next((str(c.get('公司名称', '')) for c in self.data.get('companies', [])
                              if str(c.get('公司标识') or c.get('公司名称') or '') == selected), '')
        if not selected_name:
            return False
        same_name = [c for c in self.data.get('companies', []) if str(c.get('公司名称', '')) == selected_name]
        return len(same_name) == 1 and str(row.get('公司名称', '')) == selected_name

    def refresh_company(self):
        self.latest_info_controller.schedule_query()
        # The compact overview intentionally keeps only four core cards.


    def filtered_lines(self):
        query = self.query.text().strip().lower(); company = self.line_company.currentData() or ""; mode = self.line_mode.currentData() or ""; rows = self.data.get("lines", [])
        return [x for x in rows if self._company_matches(x, company) and (not mode or x["运输制式"] == mode) and (not query or query in " ".join(str(v) for v in x.values() if not isinstance(v, dict)).lower())]

    def refresh_lines(self):
        if not hasattr(self, 'line_table'):
            return
        rows = self.filtered_lines()
        self.line_count.setText(f"{len(rows)} / {len(self.data.get('lines', []))} 条")
        sorting = self.line_table.isSortingEnabled()
        self.line_table.blockSignals(True)
        self.line_table.setSortingEnabled(False); self.line_table.setRowCount(len(rows))
        from line_query_page import line_display_value
        body_font = QFont(FONT_FAMILY); body_font.setPixelSize(FONT_SIZE_BODY)
        for ri, row in enumerate(rows):
            values = [line_display_value(row, name) for name in ("公司名称", "运输制式", "线路名称", "地图里程", "折算里程", "单程时间", "核定速度", "今日客流", "当日发班数", "理论最大车辆需求数", "每周收入", "每周支出", "今日平均单班人次", "今日平均车公里人次")]
            for ci, value in enumerate(values):
                cell = item(value if value is not None else "—"); cell.setToolTip(cell.text())
                cell.setFont(body_font); cell.setForeground(QColor(TEXT_PRIMARY))
                if ci == 2:
                    font = cell.font(); font.setWeight(QFont.Weight.Medium); cell.setFont(font)
                self.line_table.setItem(ri, ci, cell)
            self.line_table.item(ri, 0).setData(Qt.ItemDataRole.UserRole, row["key"])
        self.line_table.setSortingEnabled(sorting)
        # Sorting changes row indices. Resolve the stable key from actual sorted items.
        selected = next((r for r in rows if r['key'] == self.selected_key), None)
        if selected:
            for ri in range(self.line_table.rowCount()):
                if self.line_table.item(ri, 0).data(Qt.ItemDataRole.UserRole) == self.selected_key:
                    self.line_table.selectRow(ri); break
        else:
            self.line_table.clearSelection()
        self.line_table.blockSignals(False)
        if selected:
            self.show_line(selected)
        elif self.selected_key:
            self.selected_key = ''; self._selected_line = None
            self.clear_fact_cards(); self.clear_schedule_tabs()
            self.detail_title.setText('筛选结果中没有已选线路')
            self.lines_page.list_footer.setText('从列表选择线路')

    def line_selection_changed(self):
        row = self.line_table.currentRow()
        if row >= 0 and self.line_table.selectedItems():
            self.line_clicked(row, 0)

    def line_clicked(self, row, _column):
        key_item = self.line_table.item(row, 0)
        key = key_item.data(Qt.ItemDataRole.UserRole) if key_item else ""
        line = next((x for x in self.data.get("lines", []) if x["key"] == key), None)
        if line:
            if self.selected_key == key and getattr(self, '_selected_line', None) is line:
                return
            self.selected_key = key; self.show_line(line)

    def show_line(self, line):
        from line_query_page import CompactFactCard, shown, line_display_value
        self._selected_line = line
        display_name = line.get('线路名称') or f"{line['线路号']}路"
        self.detail_title.setText(f"{display_name} · {line['公司名称']}")
        facts = [
            (("线路车库", line.get("线路车库")), None),
            (("开线日期", line.get("开线日期")), ("最近改线日期", line.get("最近改线日期"))),
            (("地图里程", shown(line_display_value(line, "地图里程"), "km")), ("站点数", shown(line_display_value(line, "站点数"), "站"))),
            (("单程时间", shown(line.get("单程时间"), "min")), ("核定速度", shown(line_display_value(line, "核定速度"), "km/h"))),
            (("当日发班数", shown(line_display_value(line, "当日发班数"), "班")), ("平均间隔", line.get("平均间隔"))),
            (("理论最大车辆需求数", shown(line.get("理论最大车辆需求数"), "辆")), ("平均车辆需求数", shown(line.get("平均车辆需求数"), "辆"))),
            (("今日客流", shown(line.get("今日客流"), "人次")), ("平均客流", shown(line.get("平均客流"), "人次"))),
            (("今日平均单班人次", line_display_value(line, "今日平均单班人次")), ("今日平均车公里人次", line_display_value(line, "今日平均车公里人次"))),
            (("每周收入", line.get("每周收入")), ("每周支出", line.get("每周支出"))),
        ]
        self.fact_specs = facts
        self.clear_fact_cards(); self.fact_menu.clear()
        for index, (primary, alternate) in enumerate(facts):
            tooltip = ''
            if index == 4:
                tooltip = line.get('平均间隔Tooltip', '模拟当日真实班次的有效相邻间隔；不随星期选择改变。')
            elif index == 5:
                tooltip = line.get('平均车辆需求数Tooltip', '按原游戏七天五分钟槽位计算的平均车辆需求。')
            elif index == 6:
                tooltip = '今日客流来自模拟当日；平均客流沿用累计客流除以开线日至模拟当前时间的天数。'
            card = CompactFactCard(primary, alternate, tooltip=tooltip)
            if index == 4 and line.get('当日发班数Tooltip'):
                card.label.setToolTip(line['当日发班数Tooltip'])
                card.value.setToolTip(line['当日发班数Tooltip'])
            self.fact_cards.append(card); self.facts_grid.addWidget(card, index // 3, index % 3)
            title = primary[0] + (' / ' + alternate[0] if alternate else '')
            action = QAction(title, self.fact_menu); action.setCheckable(True); action.setChecked(True)
            action.toggled.connect(card.setVisible); self.fact_menu.addAction(action)
        self.schedule_panel.set_line(line)
        self.lines_page.list_footer.setText(f"共 {len(self.data.get('lines', []))} 条线路    选中：{display_name}")
        self.lines_page.list_footer.setToolTip(self.lines_page.list_footer.text())

    def clear_schedule_tabs(self):
        self.schedule_panel.clear()

    def clear_fact_cards(self):
        for card in getattr(self, "fact_cards", []):
            self.facts_grid.removeWidget(card); card.hide(); card.deleteLater()
        self.fact_cards = []

    def export_file(self, kind):
        data, controller = self.data, self.latest_info_controller
        token = controller.token
        session_key = str(data.get('save_key') or data.get('session_key') or '')
        source = data.get('outputs', {}).get(kind)
        if not source or not Path(source).is_file():
            QMessageBox.warning(self, '无法导出', '当前存档尚未生成该工作簿')
            return
        target, _ = QFileDialog.getSaveFileName(self, '保存 XLSX', Path(source).name, 'Excel 工作簿 (*.xlsx)')
        if (not target or self.data is not data or controller.token != token
                or str(self.data.get('save_key') or self.data.get('session_key') or '') != session_key
                or self.data.get('outputs', {}).get(kind) != source or not Path(source).is_file()):
            return
        try:
            shutil.copy2(source, target)
            self.status_label.setText(f'已导出：{Path(target).name}')
        except OSError as exc:
            QMessageBox.critical(self, '导出失败', str(exc))


def main():
    from startup_bootstrap import main as bootstrap_main
    return bootstrap_main(PROJECT / 'CIM2_SaveStats.py')


if __name__ == "__main__":
    main()
