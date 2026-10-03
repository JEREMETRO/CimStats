"""Shared WinUI-style chrome on the existing Qt Windows windowing layer."""
from pathlib import Path
import sys

from PySide6.QtCore import QEvent, QPoint, QRect, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QKeySequence, QPalette, QPixmap, QShortcut
from PySide6.QtWidgets import (QApplication, QDialog, QFileDialog, QLabel, QSizePolicy,
                               QStyle, QStyleOptionFocusRect)
from qframelesswindow import FramelessMainWindow, FramelessWindow, TitleBar
from qframelesswindow.titlebar import CloseButton, MaximizeButton, MinimizeButton
from qframelesswindow.windows import WindowsFramelessWindowBase
from stats_tokens import FONT_FAMILY, TEXT_PRIMARY, TEXT_DISABLED

TITLE_BAR_HEIGHT = 32


def clear_secondary_window_icon(window):
    # A null QIcon falls back to the application/parent icon. A non-null empty
    # bitmap explicitly suppresses that inheritance, including the system menu.
    image = QPixmap(16, 16)
    image.fill(Qt.GlobalColor.transparent)
    window.setWindowIcon(QIcon(image))


def _start_system_move(window, point):
    if QApplication.platformName() != 'offscreen':
        from qframelesswindow.utils import startSystemMove
        startSystemMove(window, point)


def _show_system_menu(window, point):
    if sys.platform != 'win32' or QApplication.platformName() == 'offscreen':
        return
    import win32con
    import win32gui
    handle = int(window.winId())
    menu = win32gui.GetSystemMenu(handle, False)
    origin = window.mapToGlobal(QPoint(0, 0))
    native_origin = win32gui.ClientToScreen(handle, (0, 0))
    ratio = window.devicePixelRatioF()
    native_point = (native_origin[0] + round((point.x() - origin.x()) * ratio),
                    native_origin[1] + round((point.y() - origin.y()) * ratio))
    for command, enabled in ((win32con.SC_RESTORE, window.isMaximized() or window.isMinimized()),
                             (win32con.SC_MINIMIZE, bool(window.windowFlags() & Qt.WindowType.WindowMinimizeButtonHint)),
                             (win32con.SC_MAXIMIZE, not window.isMaximized() and
                              bool(window.windowFlags() & Qt.WindowType.WindowMaximizeButtonHint)),
                             (win32con.SC_SIZE, not window.isMaximized()),
                             (win32con.SC_MOVE, not window.isMaximized())):
        win32gui.EnableMenuItem(menu, command, win32con.MF_BYCOMMAND |
                               (win32con.MF_ENABLED if enabled else win32con.MF_GRAYED))
    command = win32gui.TrackPopupMenu(menu, win32con.TPM_RETURNCMD | win32con.TPM_RIGHTBUTTON,
                                     *native_point, 0, handle, None)
    if command:
        win32gui.PostMessage(handle, win32con.WM_SYSCOMMAND, command, 0)


class _CaptionFocus:
    def paintEvent(self, event):
        super().paintEvent(event)
        if self.hasFocus():
            from PySide6.QtGui import QPainter
            option = QStyleOptionFocusRect()
            option.initFrom(self)
            option.rect = self.rect().adjusted(3, 3, -3, -3)
            painter = QPainter(self)
            self.style().drawPrimitive(QStyle.PrimitiveElement.PE_FrameFocusRect, option, painter, self)


class _MinimizeButton(_CaptionFocus, MinimizeButton):
    pass


class _MaximizeButton(_CaptionFocus, MaximizeButton):
    pass


class _CloseButton(_CaptionFocus, CloseButton):
    pass


class _TitleText(QLabel):
    def setText(self, text):
        self._full_title = str(text)
        self.setAccessibleName(self._full_title)
        self._elide()

    def _elide(self):
        super().setText(self.fontMetrics().elidedText(getattr(self, '_full_title', ''),
                       Qt.TextElideMode.ElideRight, max(0, self.width())))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._elide()


class FluentTitleBar(TitleBar):
    def __init__(self, window, *, show_icon=False):
        super().__init__(window)
        self.setObjectName('fluentTitleBar')
        self.setFixedHeight(TITLE_BAR_HEIGHT)
        for name, cls, action in (('minBtn', _MinimizeButton, window.showMinimized),
                                  ('maxBtn', _MaximizeButton, self.toggle_maximized),
                                  ('closeBtn', _CloseButton, window.close)):
            old = getattr(self, name)
            button = cls(self)
            self.hBoxLayout.replaceWidget(old, button)
            old.hide()
            old.deleteLater()
            setattr(self, name, button)
            button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            button.installEventFilter(self)
            button.clicked.connect(action)
        self.minBtn.setAccessibleName('最小化')
        self.closeBtn.setAccessibleName('关闭窗口')
        flags = window.windowFlags()
        self.minBtn.setVisible(bool(flags & Qt.WindowType.WindowMinimizeButtonHint))
        self._can_maximize = bool(flags & Qt.WindowType.WindowMaximizeButtonHint)
        self.maxBtn.setVisible(self._can_maximize)
        self.setDoubleClickEnabled(self._can_maximize)
        self.iconLabel = QLabel(self)
        self.iconLabel.setFixedSize(16, 16)
        self.iconLabel.setVisible(show_icon)
        self.iconLabel.installEventFilter(self)
        self.titleLabel = _TitleText(self)
        self.titleLabel.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.titleLabel.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.titleLabel.setStyleSheet(f'background:transparent;font-family:"{FONT_FAMILY}";font-size:13px;border:0;')
        self.hBoxLayout.insertSpacing(0, 16)
        self.hBoxLayout.insertWidget(1, self.iconLabel)
        self.hBoxLayout.insertSpacing(2, 16 if show_icon else 0)
        self.hBoxLayout.insertWidget(3, self.titleLabel, 1)
        self.hBoxLayout.insertSpacing(4, 48)
        self.hBoxLayout.takeAt(5)  # Replace the base title bar's empty stretch.
        window.windowTitleChanged.connect(self.titleLabel.setText)
        window.windowIconChanged.connect(self._set_icon)
        self.titleLabel.setText(window.windowTitle())
        self._set_icon(window.windowIcon())
        self._sync_state()
        self._menu_shortcut = QShortcut(QKeySequence('Alt+Space'), window)
        self._menu_shortcut.activated.connect(
            lambda: _show_system_menu(window, self.mapToGlobal(QPoint(16, self.height()))))

    def _set_icon(self, icon):
        self.iconLabel.setPixmap(icon.pixmap(QSize(16, 16), self.devicePixelRatioF()))

    def _sync_state(self):
        active = self.window().isActiveWindow()
        color = QColor(TEXT_PRIMARY if active else TEXT_DISABLED)
        palette = self.palette()
        palette.setColor(QPalette.ColorGroup.Active, QPalette.ColorRole.WindowText, QColor(TEXT_PRIMARY))
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor(TEXT_DISABLED))
        self.titleLabel.setPalette(palette)
        self.titleLabel.setEnabled(active)
        for button in (self.minBtn, self.maxBtn, self.closeBtn):
            button.setNormalColor(color)
        self.maxBtn.setAccessibleName('还原窗口' if self.window().isMaximized() else '最大化')
        self.maxBtn.setMaxState(self.window().isMaximized())

    def toggle_maximized(self):
        if self._can_maximize:
            self.window().showNormal() if self.window().isMaximized() else self.window().showMaximized()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.canDrag(event.position().toPoint()):
            self.toggle_maximized()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton and self.canDrag(event.position().toPoint()):
            _start_system_move(self.window(), event.globalPosition().toPoint())

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            event.accept()

    def contextMenuEvent(self, event):
        if self.canDrag(event.pos()):
            _show_system_menu(self.window(), event.globalPos())
            event.accept()

    def eventFilter(self, watched, event):
        if watched is self.window() and event.type() == QEvent.Type.DevicePixelRatioChange:
            self._set_icon(self.window().windowIcon())
        if watched is self.window() and event.type() in (
                QEvent.Type.WindowStateChange, QEvent.Type.ActivationChange,
                QEvent.Type.PaletteChange, QEvent.Type.ApplicationPaletteChange):
            if hasattr(self, 'titleLabel'):
                self._sync_state()
        elif watched is getattr(self, 'iconLabel', None):
            if event.type() == QEvent.Type.MouseButtonDblClick and event.button() == Qt.MouseButton.LeftButton:
                self.window().close()
                return True
            if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                _show_system_menu(self.window(), self.mapToGlobal(QPoint(16, self.height())))
                return True
        elif watched in (self.minBtn, self.maxBtn, self.closeBtn):
            if event.type() == QEvent.Type.KeyPress and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                watched.click()
                return True
        return super().eventFilter(watched, event)


class _ChromeMixin:
    def __init__(self, parent=None, *, show_icon=False):
        super().__init__(parent)
        if not hasattr(self, 'titleBar'):
            self._initFrameless()
        self.setTitleBar(FluentTitleBar(self, show_icon=show_icon))
        self.setContentsMargins(0, TITLE_BAR_HEIGHT, 0, 0)
        self.titleBar.resize(self.width(), TITLE_BAR_HEIGHT)
        if not show_icon:
            clear_secondary_window_icon(self)

    def _initFrameless(self):
        if QApplication.platformName() == 'offscreen':
            self.setWindowFlag(Qt.WindowType.FramelessWindowHint)
            self._isResizeEnabled = True
            self.titleBar = TitleBar(self)
        else:
            super()._initFrameless()

    def nativeEvent(self, event_type, message):
        if QApplication.platformName() == 'offscreen':
            return False, 0
        return super().nativeEvent(event_type, message)


class FluentMainWindow(_ChromeMixin, FramelessMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent, show_icon=True)


class FluentWindow(_ChromeMixin, FramelessWindow):
    pass


class FluentDialog(_ChromeMixin, WindowsFramelessWindowBase, QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._initial_content_sized = False
        if QApplication.platformName() != 'offscreen':
            self.windowEffect.disableMaximizeButton(self.winId())

    def showEvent(self, event):
        if not self._initial_content_sized:
            self._initial_content_sized = True
            self.adjustSize()
            screen = self.screen()
            available = screen.availableGeometry() if screen is not None else self.geometry()
            parent = self.parentWidget()
            if parent is not None:
                visible = QRect(parent.mapToGlobal(QPoint()), parent.size()).intersected(available)
                if not visible.isEmpty():
                    available = visible
            self.resize(min(self.width(), max(1, available.width() - 32)),
                        min(self.height(), max(1, available.height() - 32)))
            self.move(available.center() - self.rect().center())
        super().showEvent(event)


class FluentFileDialog(_ChromeMixin, WindowsFramelessWindowBase, QFileDialog):
    def __init__(self, parent=None, caption='', directory='', file_filter=''):
        super().__init__(parent)
        self.setOption(QFileDialog.Option.DontUseNativeDialog)
        self.setOption(QFileDialog.Option.DontConfirmOverwrite)
        self.setWindowTitle(caption)
        if directory:
            if Path(directory).is_dir():
                self.setDirectory(directory)
            else:
                self.setDirectory(str(Path(directory).parent))
                self.selectFile(directory)
        if file_filter:
            self.setNameFilter(file_filter)
        self.resize(760, 520)

    @classmethod
    def _choose(cls, parent, caption, directory, file_filter, selected_filter, options, mode, accept):
        dialog = cls(parent, caption, directory, file_filter)
        dialog.setOptions(options | QFileDialog.Option.DontUseNativeDialog | QFileDialog.Option.DontConfirmOverwrite)
        dialog.setFileMode(mode)
        dialog.setAcceptMode(accept)
        if selected_filter:
            dialog.selectNameFilter(selected_filter)
        try:
            while dialog.exec() == QFileDialog.DialogCode.Accepted:
                files = dialog.selectedFiles()
                if not files:
                    return '', ''
                if accept == QFileDialog.AcceptMode.AcceptSave and Path(files[0]).exists():
                    from stats_dialogs import FluentMessageBox
                    buttons = FluentMessageBox.StandardButton
                    if FluentMessageBox.warning(dialog, '确认替换文件', '目标文件已存在，是否替换？',
                                                buttons.Yes | buttons.No) != buttons.Yes:
                        continue
                return files[0], dialog.selectedNameFilter()
            return '', ''
        finally:
            dialog.deleteLater()

    @classmethod
    def getOpenFileName(cls, parent=None, caption='', directory='', filter='', selectedFilter='', options=QFileDialog.Option(0)):
        return cls._choose(parent, caption, directory, filter, selectedFilter, options,
                           QFileDialog.FileMode.ExistingFile, QFileDialog.AcceptMode.AcceptOpen)

    @classmethod
    def getSaveFileName(cls, parent=None, caption='', directory='', filter='', selectedFilter='', options=QFileDialog.Option(0)):
        return cls._choose(parent, caption, directory, filter, selectedFilter, options,
                           QFileDialog.FileMode.AnyFile, QFileDialog.AcceptMode.AcceptSave)

    @classmethod
    def getExistingDirectory(cls, parent=None, caption='', directory='', options=QFileDialog.Option.ShowDirsOnly):
        return cls._choose(parent, caption, directory, '', '', options,
                           QFileDialog.FileMode.Directory, QFileDialog.AcceptMode.AcceptOpen)[0]
