"""Statistics-only hover policy; chart inspection keeps its own tooltips."""
from PySide6.QtCore import QObject, QEvent, Qt, QTimer
from weakref import WeakKeyDictionary
from PySide6.QtWidgets import QApplication, QWidget
from qfluentwidgets import ToolTipFilter
from shiboken6 import isValid


class StatisticsHoverPolicy(QObject):
    def __init__(self, page):
        super().__init__(page)
        self.page = page
        self._header_tips = WeakKeyDictionary()
        self._restoring = False
        QApplication.instance().installEventFilter(self)
        self.clear_tree(page)

    def owns(self, widget):
        from stats_charts import ChartPanel
        from chart_canvas import ChartCanvas
        node = widget
        while isinstance(node, QWidget):
            if isinstance(node, (ChartPanel, ChartCanvas)):
                return False
            if node is self.page:
                return True
            node = node.parentWidget()
        window = self.page.window()
        header = getattr(window, 'header', None)
        pages = getattr(window, 'pages', None)
        return (header is not None and pages is not None and
                pages.currentWidget() is self.page and
                (widget is header or header.isAncestorOf(widget)))

    def clear_widget(self, widget):
        text = widget.toolTip()
        filters = widget.findChildren(ToolTipFilter, options=Qt.FindChildOption.FindDirectChildrenOnly)
        if not (widget is self.page or self.page.isAncestorOf(widget)) and text:
            self._header_tips[widget] = (text, filters)
        if text:
            if not widget.accessibleDescription():
                widget.setAccessibleDescription(text)
            widget.setToolTip('')
        for tip in filters:
            tip.hideToolTip()
            widget.removeEventFilter(tip)

    def clear_tree(self, root):
        for widget in (root, *root.findChildren(QWidget)):
            if self.owns(widget):
                self.clear_widget(widget)

    def eventFilter(self, watched, event):
        kind = event.type()
        if self._restoring:
            return False
        if watched is self.page and kind == QEvent.Type.Hide:
            self._restoring = True
            try:
                for widget,(text,filters) in list(self._header_tips.items()):
                    if isValid(widget):
                        widget.setToolTip(text)
                        for tip in filters:
                            if isValid(tip):widget.installEventFilter(tip)
                self._header_tips.clear()
            finally:
                self._restoring = False
            return False
        if watched is self.page and kind == QEvent.Type.Show:
            QTimer.singleShot(0, self._clear_header)
        if kind not in (QEvent.Type.ToolTip, QEvent.Type.ToolTipChange,
                        QEvent.Type.Enter, QEvent.Type.Polish, QEvent.Type.Show):
            return False
        if not isValid(self.page) or not isinstance(watched, QWidget) or not self.owns(watched):
            return False
        self.clear_widget(watched)
        return kind == QEvent.Type.ToolTip

    def _clear_header(self):
        if isValid(self.page) and self.page.isVisible():
            header = getattr(self.page.window(), 'header', None)
            if header is not None:
                self.clear_tree(header)
