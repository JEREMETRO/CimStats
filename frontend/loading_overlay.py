"""Content-centred progress for the existing parse worker."""
from PySide6.QtCore import Qt, QEvent
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QHBoxLayout, QWidget
from qfluentwidgets import ProgressRing, PushButton


class LoadingOverlay(QFrame):
    def __init__(self, parent, cancel):
        super().__init__(parent)
        self.setObjectName('loadingOverlay')
        self.setStyleSheet('QFrame#loadingOverlay {background: rgba(246,249,253,235);}')
        root = QVBoxLayout(self); root.addStretch()
        row = QHBoxLayout(); row.addStretch()
        card = QWidget(self); card.setMinimumWidth(520); box = QVBoxLayout(card); box.setSpacing(12)
        self.ring = ProgressRing(card); self.ring.setRange(0,100)
        self.ring.setValue(0)
        self.ring.setFixedSize(64,64); box.addWidget(self.ring,0,Qt.AlignmentFlag.AlignHCenter)
        self.read = QLabel('',card); self.read.setWordWrap(True); self.read.setMaximumWidth(480)
        self.read.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._estimated = False
        self.percent = QLabel('阶段进度：0%',card); self.percent.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box.addWidget(self.read); box.addWidget(self.percent)
        self.cancel_button = PushButton('取消读取',card); self.cancel_button.clicked.connect(cancel)
        box.addWidget(self.cancel_button,0,Qt.AlignmentFlag.AlignHCenter)
        row.addWidget(card); row.addStretch(); root.addLayout(row); root.addStretch()
        parent.installEventFilter(self); self.hide()

    def eventFilter(self, watched, event):
        if watched is self.parentWidget() and event.type() == QEvent.Type.Resize:
            self.setGeometry(watched.rect())
        return super().eventFilter(watched,event)

    def begin(self, stage):
        self.cancel_button.setEnabled(True)
        self.update_progress(stage, 0, estimated=False)
        self.setGeometry(self.parentWidget().rect()); self.show(); self.raise_()

    def update_progress(self, stage, percent=None, *, estimated=None):
        self.read.setText(f'当前阶段：{stage}')
        # Stage/log updates preserve the last estimate, including cancellation
        # and chart preparation. Only begin resets the new task to zero.
        value = self.ring.value() if percent is None else percent
        value = min(99, max(0, int(value)))
        self.ring.setValue(value)
        if percent is not None and estimated is not None:
            self._estimated = estimated
        prefix = '预计进度' if self._estimated else '阶段进度'
        self.percent.setText(f'{prefix}：{value}%')

    def finish(self):
        self.hide()
