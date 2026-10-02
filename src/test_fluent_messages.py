import os, sys
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'frontend'))
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QWidget
from qfluentwidgets import MessageBox


def test_fluent_messages_preserve_yes_no_and_single_confirmation():
    from stats_dialogs import FluentMessageBox as Dialog
    app=QApplication.instance() or QApplication([])
    parent=QWidget();parent.resize(600,400);parent.show()
    def choose_yes():
        dialog=next(w for w in parent.findChildren(MessageBox) if w.isVisible())
        dialog.yesButton.click()
    def choose_no():
        dialog=next(w for w in parent.findChildren(MessageBox) if w.isVisible())
        dialog.cancelButton.click()
    QTimer.singleShot(100,choose_yes)
    assert Dialog.warning(parent,'标题','内容',Dialog.StandardButton.Yes|Dialog.StandardButton.No)==Dialog.StandardButton.Yes
    QTimer.singleShot(100,choose_no)
    assert Dialog.warning(parent,'标题','内容',Dialog.StandardButton.Yes|Dialog.StandardButton.No)==Dialog.StandardButton.No
    QTimer.singleShot(100,choose_yes)
    assert Dialog.critical(parent,'失败','原因')==Dialog.StandardButton.Ok
    parent.close()
