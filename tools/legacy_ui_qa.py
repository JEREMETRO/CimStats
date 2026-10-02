"""Render both retained pages and record spacing, fonts and actual controls."""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'frontend'), str(ROOT / 'src')]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--job', type=Path, required=True)
    parser.add_argument('--tag', required=True)
    parser.add_argument('--sizes', default='1920x1080,1600x900,920x680')
    args = parser.parse_args()
    from PySide6.QtCore import QPoint, QSettings
    from PySide6.QtGui import QFontInfo
    from PySide6.QtWidgets import QApplication, QWidget, QScrollArea
    import desktop_app
    from report_model import load_session
    from stats_style import initialize_theme

    args.output.mkdir(parents=True, exist_ok=True)
    application = QApplication([])
    initialize_theme(application)
    settings = QSettings(str(args.output / 'preferences.ini'), QSettings.Format.IniFormat)
    desktop_app.QSettings = lambda *a: settings
    desktop_app.MainWindow.check_install = lambda self: None
    window = desktop_app.MainWindow()
    window.show()
    cases = []

    def settle():
        for _ in range(12):
            application.processEvents()
            time.sleep(.02)

    for loaded in (False, True):
        if loaded:
            data = load_session(args.job, args.tag)
            data['save_path'] = args.tag.removesuffix('_运行时') + '.save'
            window.on_completed(data)
        for size in args.sizes.split(','):
            window.resize(*map(int, size.split('x')))
            for tab in ((0, 1) if loaded else (0,)):
                window.navigate(tab)
                if tab == 1:
                    window.line_clicked(0, 0)
                settle()
                scroll = window.overview_scroll if tab == 0 else window.lines_scroll
                name = f'{"loaded" if loaded else "empty"}-{tab}-{size}'
                scroll.verticalScrollBar().setValue(0)
                settle()
                window.grab().save(str(args.output / f'{name}-top.png'))
                card_bottom = max(card.mapTo(window.overview_tab, QPoint()).y() + card.height()
                                  for card in (*window.metric_cards, *window.extreme_cards))
                chart_top = window.passenger_panel.mapTo(window.overview_tab, QPoint()).y()
                visible = [widget for widget in window.findChildren(QWidget) if widget.isVisible()]
                fonts = sorted({QFontInfo(widget.font()).family() for widget in visible})
                font_mismatches = [dict(control=type(widget).__name__, name=widget.objectName(),
                                        family=QFontInfo(widget.font()).family())
                                   for widget in visible
                                   if QFontInfo(widget.font()).family() != 'Microsoft YaHei UI']
                controls = {key: type(getattr(window, key)).__module__ + '.' + type(getattr(window, key)).__name__
                            for key in ('company_combo', 'mode_combo', 'query', 'line_company',
                                        'line_mode', 'line_table', 'line_columns_button',
                                        'fact_menu_button', 'schedule_tabs')}
                cases.append(dict(name=name, client=[window.width(), window.height()],
                                  dpr=window.devicePixelRatioF(), fonts=fonts,
                                  font_mismatches=font_mismatches,
                                  metrics_to_charts_gap=chart_top-card_bottom,
                                  horizontal_overflow=max(0, scroll.widget().width()-scroll.viewport().width()),
                                  controls=controls))
                scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())
                settle()
                window.grab().save(str(args.output / f'{name}-bottom.png'))
                if tab == 1:
                    reachable = []
                    for card in window.fact_cards:
                        ancestor = card.parentWidget()
                        while ancestor is not None:
                            if isinstance(ancestor, QScrollArea):
                                ancestor.ensureWidgetVisible(card, 0, 0)
                            ancestor = ancestor.parentWidget()
                        settle()
                        region = card.visibleRegion().boundingRect()
                        reachable.append(region.width() >= card.width() and region.height() >= card.height())
                    cases[-1]['fact_cards_fully_reachable'] = reachable
    # Sidebar width changes can add a row without resizing the main window.
    window.navigate(0)
    window.resize(1200, 900)
    for collapsed in (True, False, True):
        window.set_sidebar_collapsed(collapsed)
        settle()
        card_bottom = max(card.mapTo(window.overview_tab, QPoint()).y() + card.height()
                          for card in (*window.metric_cards, *window.extreme_cards))
        chart_top = window.passenger_panel.mapTo(window.overview_tab, QPoint()).y()
        cases.append(dict(name=f'sidebar-1200-{"collapsed" if collapsed else "expanded"}',
                          metrics_to_charts_gap=chart_top-card_bottom,
                          host_height=window.metric_host.height(),
                          required_height=window.metric_grid.heightForWidth(window.metric_host.width())))
    window.close()
    application.processEvents()
    (args.output / 'evidence.json').write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps({'cases': len(cases), 'output': str(args.output)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
