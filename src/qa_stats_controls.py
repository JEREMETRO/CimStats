"""Render real Fluent segmented controls for visual comparison."""
import os
import json
import subprocess
import sys
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'frontend'))

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget
from PySide6.QtTest import QTest
from qfluentwidgets import FluentIcon, TogglePushButton

from stats_controls import FluentSegmentedControl
import stats_tokens as tokens


def main():
    app = QApplication.instance() or QApplication([])
    host = QWidget()
    host.setObjectName('qaSegmentHost')
    host.setStyleSheet(f'QWidget#qaSegmentHost {{ background: {tokens.PAGE_BG}; }}')
    layout = QVBoxLayout(host)
    layout.setContentsMargins(20, 20, 20, 20)
    layout.setSpacing(16)
    label = QLabel('演示控件 · 常规分析模式 / 紧凑图形模式')
    layout.addWidget(label)
    regular = FluentSegmentedControl()
    regular.addItem('default', '默认模式', FluentIcon.PIE_SINGLE)
    regular.addItem('companies', '多公司对比', FluentIcon.PEOPLE)
    regular.addItem('period', '同期对比', FluentIcon.CALENDAR)
    regular.setCurrentKey('companies')
    layout.addWidget(regular)
    compact = FluentSegmentedControl(compact=True)
    compact.addItem('line', '折线', FluentIcon.MARKET)
    compact.addItem('area', '面积', FluentIcon.PIE_SINGLE)
    compact.setCurrentKey('area')
    layout.addWidget(compact)
    regular.setItemEnabled('period', False)
    layout.addStretch(1)
    host.resize(680, 190)
    host.show()
    app.processEvents()
    QTest.qWait(200)  # Capture the settled state after the 160 ms selection animation.
    destination = ROOT / 'docs' / 'ui-redesign' / 'evidence' / 'controls'
    destination.mkdir(parents=True, exist_ok=True)
    host.grab().save(str(destination / 'segmented-demo.png'))
    first = regular.findChildren(TogglePushButton)[0]
    point = QPoint(first.width() // 2, first.height() // 2)
    QTest.mouseMove(first, point)
    app.processEvents()
    host.grab().save(str(destination / 'segmented-hover.png'))
    QTest.mouseMove(host, QPoint(host.width() - 2, host.height() - 2))
    regular.findChildren(TogglePushButton)[1].setFocus()
    first.setFocus(Qt.FocusReason.TabFocusReason)
    app.processEvents()
    host.grab().save(str(destination / 'segmented-focus.png'))
    QTest.mousePress(first, Qt.MouseButton.LeftButton, pos=point)
    app.processEvents()
    host.grab().save(str(destination / 'segmented-pressed.png'))
    QTest.mouseRelease(first, Qt.MouseButton.LeftButton, pos=point)
    revision = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'],
                                       cwd=ROOT, text=True).strip()
    (destination / 'README.json').write_text(json.dumps({
        'source': 'actual FluentSegmentedControl in src/qa_stats_controls.py',
        'logical_size': [680, 190],
        'dpi': app.primaryScreen().logicalDotsPerInch(),
        'states': ['selected and disabled', 'hover', 'keyboard focus', 'pressed'],
        'code_revision': revision,
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    print(destination / 'segmented-demo.png')
    host.close()


if __name__ == '__main__':
    main()
