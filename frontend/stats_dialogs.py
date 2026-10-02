"""Fluent confirmation/error surfaces with the existing QMessageBox contract."""
from PySide6.QtWidgets import QMessageBox, QDialog
from qfluentwidgets import MessageBox
from stats_motion import SurfaceMotion
import stats_motion as motion_policy


class _MessageSurface(MessageBox):
    def __init__(self, *args):
        super().__init__(*args)
        self.motion = SurfaceMotion(self)
        self._closing_surface = False

    def showEvent(self, event):
        # Own the reveal rather than overlapping the library's temporary effect
        # with a dismissal triggered while its opening animation is still running.
        QDialog.showEvent(self, event)
        self.motion.reveal()

    def done(self, code):
        if self._closing_surface:
            return
        self._closing_surface = True
        self.motion.finish()
        if motion_policy.animations_enabled():
            super().done(code)
        else:
            QDialog.done(self, code)


class FluentMessageBox:
    StandardButton = QMessageBox.StandardButton

    @staticmethod
    def _show(parent, title, text, buttons=None, defaultButton=None):
        yes_no = buttons is not None and bool(buttons & QMessageBox.StandardButton.Yes)
        dialog = _MessageSurface(title, text, parent)
        dialog.yesButton.setText('是' if yes_no else '确定')
        dialog.cancelButton.setText('否')
        dialog.cancelButton.setVisible(yes_no)
        accepted = dialog.exec()
        dialog.deleteLater()
        if yes_no:
            return QMessageBox.StandardButton.Yes if accepted else QMessageBox.StandardButton.No
        return QMessageBox.StandardButton.Ok

    warning = _show
    information = _show
    critical = _show
