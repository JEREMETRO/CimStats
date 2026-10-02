"""Connect confirmed dashboard snapshots to the existing export actions."""

from pathlib import Path

from PySide6.QtCore import QObject, QPoint, Signal
from PySide6.QtWidgets import QFileDialog
from qfluentwidgets import Action, RoundMenu

from stats_exports import export_png, export_xlsx, export_city_xlsx
from stats_text import label


class DashboardIntegration(QObject):
    export_failed = Signal(object)

    def __init__(self, page, settings=None):
        super().__init__(page)
        self.page = page
        self.last_error = None
        page.export_requested.connect(self.show_export_menu)

    def show_export_menu(self):
        if self.page.snapshot is None:
            return
        menu = RoundMenu(parent=self.page.export_button)
        for kind in ('png', 'xlsx'):
            action = Action(label('export-' + kind), menu)
            action.triggered.connect(lambda checked=False, selected=kind: self._export(selected))
            menu.addAction(action)
        button = self.page.export_button
        menu.exec(button.mapToGlobal(QPoint(0, button.height())))

    def _export(self, kind):
        snapshot = self.page.snapshot
        if snapshot is None:
            return
        route = self.page.tab_bar.currentRouteKey() if hasattr(self.page, 'tab_bar') else 'company'
        network = self.page.network_snapshot if route == 'network' else None
        city = self.page.city_snapshot if route == 'city' else None
        if route == 'city' and city is None:
            return
        if route == 'network' and network is None:
            return
        session_key = self.page.session_key
        caption = label('export-' + kind)
        suffix = '.' + kind
        suggested = str(Path.cwd() / (caption + suffix))
        file_filter = f'{kind.upper()} (*{suffix})'
        try:
            path, _ = QFileDialog.getSaveFileName(self.page, caption, suggested, file_filter)
            if not path or self.page.snapshot is not snapshot or self.page.session_key != session_key or (
                    network is not None and self.page.network_snapshot is not network) or (
                    city is not None and self.page.city_snapshot is not city):
                return
            if Path(path).suffix.lower() != suffix:
                path += suffix
            if kind == 'png':
                export_png(self.page.export_target(), path)
            elif city is not None:
                export_city_xlsx(city, path, self.page.city_dashboard.display_state())
            else:
                company_dashboard = getattr(self.page, 'company_dashboard', None)
                satisfaction_control = getattr(self.page, 'satisfaction_combo', None)
                export_xlsx(snapshot, path, self.page._names(), network,
                    company_mode=getattr(company_dashboard, '_mode', None) if route == 'company' else None,
                    satisfaction=satisfaction_control.currentData() if satisfaction_control is not None else 'satisfaction-speed')
            self.last_error = None
        except Exception as exc:
            self.last_error = exc
            self.export_failed.emit(exc)


def configure_dashboard(page, settings=None):
    """Attach the dashboard export menu once; reminders live on the home page."""
    previous = getattr(page, 'stats_integration', None)
    if previous is not None:
        return previous
    controller = DashboardIntegration(page, settings)
    page.stats_integration = controller
    return controller
