"""Fluent settings for the immutable single-route export request."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import Qt, QSize, QTimer, Signal, QByteArray, QBuffer, QIODevice, QRegularExpression
from PySide6.QtGui import QPainter, QImage, QColor, QRegularExpressionValidator
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QStackedWidget, QSizePolicy
from qfluentwidgets import (Pivot, CheckBox, PushButton, PrimaryPushButton, DoubleSpinBox,
                            ColorDialog, ColorPickerButton, LineEdit)
from window_chrome import FluentDialog, FluentFileDialog
from stats_controls import FluentSegmentedControl, StatisticsScrollArea, configure_navigation_pivot
from stats_typography import ui_font
import stats_tokens as tokens


class _Preview(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.image = QImage()
        self.message = '正在生成预览'
        self.setMinimumSize(0, 0)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAccessibleName('线路图预览')

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        if self.image.isNull():
            painter.setFont(ui_font(12))
            painter.setPen(QColor(tokens.TEXT_SECONDARY))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.message)
        else:
            size = self.image.size().scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
            rect = self.rect()
            rect.setSize(size)
            rect.moveCenter(self.rect().center())
            painter.drawImage(rect, self.image)
        painter.end()


class RouteExportDialog(FluentDialog):
    exported = Signal(object)

    def __init__(self, request, parent=None, *, request_builder, start_preview=True):
        owner = None
        if parent is not None and QApplication.platformName() == 'windows':
            owner = parent.window().windowHandle()
        super().__init__(None if owner is not None else parent)
        from route_export_model import FIELD_SECTIONS, measure_output
        self._request = request
        self._builder = request_builder
        self._options = request.options
        self._measure = measure_output
        self._controller = None
        self._generation = None
        self._exporting = False
        self._closed = False
        self._valid = True
        self._logo_status = None
        self._color_dialog = None
        self._updating = True
        self.setWindowTitle('导出单线线路图')
        self.setObjectName('routeExportDialog')
        self.setStyleSheet(f'QDialog#routeExportDialog {{ background:{tokens.CARD_BG}; }}')
        self.setMinimumSize(0, 0)
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 20)
        root.setSpacing(16)
        body = QHBoxLayout()
        body.setSpacing(20)
        left = QWidget(self)
        left.setMinimumWidth(0)
        column = QVBoxLayout(left)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(8)
        column.addWidget(self._label('预览', bold=True))
        self.preview = _Preview(left)
        column.addWidget(self.preview, 1)
        body.addWidget(left, 1)
        self.settings_host = QWidget(self)
        self.settings_host.setFixedWidth(344)
        right = QVBoxLayout(self.settings_host)
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(8)
        self.tabs = Pivot(self.settings_host)
        self.pages = QStackedWidget(self.settings_host)
        self.pages.setMinimumSize(0, 0)
        for key, title in (('settings', '导出设置'), ('data', '导出数据')):
            self.tabs.addItem(key, title, onClick=lambda checked=False, k=key: self._set_page(k))
        configure_navigation_pivot(self.tabs)
        # These tabs have no icons, so they need no reserved icon padding.
        for item in self.tabs.items.values():
            item.setStyleSheet(item.styleSheet() + '\nQPushButton { padding: 7px 12px; }')
        self.tabs.setItemFontSize(14)
        self.tabs.setCurrentItem('settings')
        right.addWidget(self.tabs)
        right.addWidget(self.pages, 1)
        settings, layout = self._scroll_page()
        self.pages.addWidget(settings)
        self.format_control = self._segments(layout, '文件格式', [('PNG', 'PNG'), ('JPG', 'JPG'), ('PDF', 'PDF')], self._options.format)
        self.aspect_control = self._segments(layout, '画幅', [(v, v) for v in ('16:9', '16:10', '3:2', 'A4')], self._options.aspect)
        self.orientation_control = self._segments(layout, '画幅方向', [('landscape', '横向'), ('portrait', '纵向')], self._options.orientation)
        layout.addWidget(self._label('成品尺寸（毫米）', bold=True))
        sizes = QHBoxLayout()
        sizes.setSpacing(8)
        self.width_edit = self._dimension('宽')
        self.height_edit = self._dimension('高')
        for label, edit in (('宽', self.width_edit), ('高', self.height_edit)):
            sizes.addWidget(self._label(label))
            sizes.addWidget(edit, 1)
        layout.addLayout(sizes)
        self.ppi_control = self._segments(layout, '输出精度（ppi）', [(str(v), str(v)) for v in (80, 150, 300, 600)], str(self._options.ppi))
        self.pixel_label = self._label('', caption=True)
        layout.addWidget(self.pixel_label)
        self.direction_control = self._segments(layout, '绘制方向', [('up', '上行'), ('down', '下行'), ('whole', '全线')], self._options.direction)
        if self._request.metrics.effective_direction == 'whole' and self._request.route.direction.kind != 'roundtrip':
            self.direction_control.setCurrentKey('whole')
            self.direction_control.setItemEnabled('up', False)
            self.direction_control.setItemEnabled('down', False)
            self._options = replace(self._options, direction='whole')
        switches = QGridLayout()
        switches.setSpacing(8)
        self.stops_check = self._check('标出站点', self._options.show_stops)
        self.depots_check = self._check('绘制车库名称', self._options.show_depot_names)
        self.deadhead_check = self._check('计入空放里程', self._options.include_deadhead)
        for i, item in enumerate((self.stops_check, self.depots_check, self.deadhead_check)):
            switches.addWidget(item, i // 2, i % 2)
        layout.addLayout(switches)
        self.theme_control = self._segments(layout, '成品风格', [('day', '日间'), ('night', '夜间')], self._options.theme)
        self.logo_control = self._segments(layout, '公司 Logo', [('save', '存档标志'), ('custom', '自选图片'), ('none', '不显示')], self._options.logo_source)
        self.logo_status = self._label('', caption=True)
        self.logo_status.setWordWrap(True)
        layout.addWidget(self.logo_status)
        self.choose_logo = PushButton('选择图片', self)
        self.choose_logo.clicked.connect(self._choose_logo)
        layout.addWidget(self.choose_logo)
        layout.addWidget(self._label('公司品牌配色', bold=True))
        colors = QGridLayout()
        colors.setHorizontalSpacing(8)
        colors.setVerticalSpacing(8)
        self.color_buttons = []
        self.color_edits = []
        for index, name in enumerate(('主色', '辅色')):
            colors.addWidget(self._label(name), index, 0)
            button = ColorPickerButton(QColor('#FFFFFF'), name, self)
            button.setFixedSize(32, 32)
            button.setAccessibleName(f'选择公司品牌{name}')
            button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            button.clicked.disconnect()
            button.clicked.connect(lambda checked=False, i=index: self._choose_color(i))
            self.color_buttons.append(button)
            colors.addWidget(button, index, 1)
            edit = LineEdit(self)
            edit.setFixedHeight(36)
            edit.setMaxLength(7)
            edit.setMinimumWidth(0)
            edit.setAccessibleName(f'公司品牌{name} HEX')
            edit.setValidator(QRegularExpressionValidator(QRegularExpression('#[0-9A-Fa-f]{6}'), edit))
            edit.textEdited.connect(lambda text, i=index: self._hex_edited(i, text))
            edit.editingFinished.connect(self._sync_colors)
            self.color_edits.append(edit)
            colors.addWidget(edit, index, 2)
        colors.setColumnStretch(2, 1)
        self.reset_colors = PushButton('存档两色', self)
        self.reset_colors.clicked.connect(self._reset_colors)
        colors.addWidget(self.reset_colors, 0, 3, 2, 1)
        layout.addLayout(colors)
        layout.addStretch()
        data, fields = self._scroll_page()
        self.pages.addWidget(data)
        selection = QHBoxLayout()
        selection.setSpacing(8)
        for title, keys in (('全选', 'all'), ('全不选', 'none'), ('恢复默认', 'default')):
            button = PushButton(title, self)
            button.clicked.connect(lambda checked=False, value=keys: self._select_fields(value))
            selection.addWidget(button)
        fields.addLayout(selection)
        self.field_checks = {}
        for section, title, entries in FIELD_SECTIONS:
            fields.addSpacing(8)
            fields.addWidget(self._label(title, bold=True))
            grid = QGridLayout()
            grid.setHorizontalSpacing(8)
            grid.setVerticalSpacing(8)
            for index, (key, label) in enumerate(entries):
                check = self._check(label.removesuffix('（全线）'), key in self._options.selected_fields)
                self.field_checks[key] = check
                # Long labels need the full row, preserving readable typography.
                if section == 'passenger_data':
                    grid.addWidget(check, index, 0, 1, 2)
                else:
                    grid.addWidget(check, index // 2, index % 2)
            fields.addLayout(grid)
        fields.addStretch()
        body.addWidget(self.settings_host)
        root.addLayout(body, 1)
        self.error_label = self._label('', caption=True)
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet(f'color:{tokens.ERROR_COLOR};')
        self.error_label.hide()
        root.addWidget(self.error_label)
        self.action_bar = QWidget(self)
        actions = QHBoxLayout(self.action_bar)
        actions.setContentsMargins(0, 12, 0, 0)
        actions.setSpacing(8)
        actions.addStretch()
        self.cancel_button = PushButton('取消', self)
        self.export_button = PrimaryPushButton('导出', self)
        for button in (self.cancel_button, self.export_button):
            button.setFixedSize(110, 36)
            actions.addWidget(button)
        root.addWidget(self.action_bar)
        self.cancel_button.clicked.connect(self.reject)
        self.export_button.clicked.connect(self._export)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(180)
        self._timer.timeout.connect(self._submit_preview)
        self.width_edit.valueChanged.connect(lambda: self._dimension_changed('width'))
        self.height_edit.valueChanged.connect(lambda: self._dimension_changed('height'))
        for control in (self.format_control, self.aspect_control, self.orientation_control, self.ppi_control,
                        self.direction_control, self.theme_control, self.logo_control):
            control.currentKeyChanged.connect(self._changed)
        self._sync_dimensions()
        self._updating = False
        self._sync_logo()
        self._sync_colors()
        if owner is not None:
            # Creating a QWidget-owned native dialog can clear the owner's
            # composited frame. Attach the completed window instead.
            self.windowHandle().setTransientParent(owner)
        if start_preview:
            self._timer.start()

    def sizeHint(self):
        # Settings scroll independently; their full height must not size the window.
        return QSize(880, 720)

    def showEvent(self, event):
        if not self._initial_content_sized:
            self._initial_content_sized = True
            available = self._dialog_placement_bounds()
            wanted = self.sizeHint()
            self.resize(min(wanted.width(), max(1, available.width() - 80)),
                        min(wanted.height(), max(1, available.height() - 32)))
            self.move(available.center() - self.rect().center())
        super().showEvent(event)

    def _label(self, text, *, bold=False, caption=False):
        label = QLabel(text, self)
        label.setFont(ui_font(12 if caption else 14, 600 if bold else 400))
        label.setStyleSheet(f'color:{tokens.TEXT_SECONDARY if caption else tokens.TEXT_PRIMARY};background:transparent;')
        return label

    def _scroll_page(self):
        area = StatisticsScrollArea(self)
        area.setWidgetResizable(True)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 8, 12, 8)
        layout.setSpacing(8)
        area.setWidget(widget)
        return area, layout

    def _segments(self, layout, title, entries, value):
        if title:
            if layout.count():
                layout.addSpacing(8)
            layout.addWidget(self._label(title, bold=True))
        control = FluentSegmentedControl(self)
        for key, text in entries:
            control.addItem(key, text)
        control.setCurrentKey(value)
        layout.addWidget(control)
        return control

    def _dimension(self, name):
        edit = DoubleSpinBox(self)
        edit.setRange(1, 1000)
        edit.setDecimals(2)
        edit.setSingleStep(1)
        edit.setSymbolVisible(False)
        edit.setFixedHeight(36)
        edit.setMinimumWidth(0)
        edit.setFixedWidth(132)
        edit.setAccessibleName(f'成品{name}（毫米）')
        return edit

    def _check(self, text, checked):
        check = CheckBox(text, self)
        check.setFont(ui_font(14))
        check.setChecked(checked)
        check.setAccessibleName(text)
        check.toggled.connect(self._changed)
        return check

    def _set_page(self, key):
        self.pages.setCurrentIndex(0 if key == 'settings' else 1)
        self.tabs.setCurrentItem(key)

    def _sync_dimensions(self):
        size = self._measure(self._options)
        self._options = replace(self._options, width_mm=size.width_mm, height_mm=None)
        self._updating = True
        self.width_edit.setValue(size.width_mm)
        self.height_edit.setValue(size.height_mm)
        self._updating = False
        a4 = self._options.aspect == 'A4'
        self.width_edit.setEnabled(not a4)
        self.height_edit.setEnabled(not a4)
        self.pixel_label.setText(f'{size.width_px} × {size.height_px} 像素')

    def _dimension_changed(self, dimension):
        if self._updating:
            return
        self._options = replace(self._options, width_mm=self.width_edit.value(),
                                height_mm=self.height_edit.value() if dimension == 'height' else None)
        self._changed()

    def options(self):
        return self._options

    def _changed(self, *_):
        if self._updating or self._closed:
            return
        self._options = replace(self._options, format=self.format_control.currentKey(),
            aspect=self.aspect_control.currentKey(), orientation=self.orientation_control.currentKey(),
            ppi=int(self.ppi_control.currentKey()), direction=self.direction_control.currentKey(),
            show_stops=self.stops_check.isChecked(), show_depot_names=self.depots_check.isChecked(),
            include_deadhead=self.deadhead_check.isChecked(), theme=self.theme_control.currentKey(),
            logo_source=self.logo_control.currentKey(),
            selected_fields=tuple(key for key, check in self.field_checks.items() if check.isChecked()))
        try:
            self._sync_dimensions()
            self._valid = True
            self.error_label.hide()
        except ValueError as error:
            self._valid = False
            self._error(str(error))
            self._timer.stop()
            if self._controller is not None:self._controller.cancel()
            self._generation = None
            self.preview.image = QImage()
            self.preview.message = '请调整成品尺寸或精度'
            self.preview.update()
        self._sync_logo()
        if self._valid:self._invalidate_preview()

    def _select_fields(self, selection):
        from route_export_model import DEFAULT_FIELDS
        self._updating = True
        for key, check in self.field_checks.items():
            check.setChecked(selection == 'all' or (selection == 'default' and key in DEFAULT_FIELDS))
        self._updating = False
        self._changed()

    def _sync_logo(self):
        custom = self._options.logo_source == 'custom'
        self.choose_logo.setVisible(custom)
        text = ''
        if custom and not self._options.custom_logo_png:
            text = '请选择公司 Logo 图片'
        elif self._options.logo_source == 'save' and (self._logo_status in ('missing_asset', 'missing_colors', 'no_logo')
                or not (getattr(self._request.branding, 'logo_key', None)
                        or dict(getattr(self._request, 'company', ())).get('公司标志'))):
            text = '存档标志不可用，保留公司名称'
        self.logo_status.setText(text)
        self.logo_status.setVisible(bool(text))
        self.export_button.setEnabled(self._valid and not self._exporting and not (custom and not self._options.custom_logo_png))

    def _choose_logo(self):
        path, _ = FluentFileDialog.getOpenFileName(self, '选择公司 Logo', '', '图片 (*.png *.jpg *.jpeg *.webp *.bmp)')
        if not path or self._closed:
            return
        image = QImage(path)
        if image.isNull():
            self._error('无法读取该图片')
            return
        data = QByteArray()
        buffer = QBuffer(data)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        image.save(buffer, 'PNG')
        self._options = replace(self._options, custom_logo_png=bytes(data))
        self._changed()

    def _brand_colors(self):
        if self._options.brand_override:
            return self._options.brand_override
        brand = self._request.branding
        company = dict(getattr(self._request, 'company', ()))
        values = (getattr(brand, 'color1_argb', company.get('颜色1')),
                  getattr(brand, 'color2_argb', company.get('颜色2')))
        return tuple(f'#{value & 0xFFFFFF:06X}' if isinstance(value, int) else fallback
                     for value, fallback in zip(values, ('#0067C0', '#FFFFFF')))

    def _sync_colors(self):
        for button, edit, value in zip(self.color_buttons, self.color_edits, self._brand_colors()):
            color = QColor(value)
            button.setColor(color)
            edit.setText(color.name().upper())
            button.setAccessibleDescription(color.name().upper())

    def _hex_edited(self, index, text):
        if not self.color_edits[index].hasAcceptableInput():return
        colors = list(self._brand_colors())
        colors[index] = QColor(text).name().upper()
        self._options = replace(self._options, brand_override=tuple(colors))
        self.color_buttons[index].setColor(QColor(text))
        self.color_buttons[index].setAccessibleDescription(colors[index])
        self._changed()

    def _choose_color(self, index):
        colors = list(self._brand_colors())
        dialog = ColorDialog(QColor(colors[index]), '公司品牌配色', self, enableAlpha=False)
        self._color_dialog = dialog
        for widget, text in ((dialog.yesButton, '确定'), (dialog.cancelButton, '取消'),
                             (dialog.editLabel, '编辑颜色'), (dialog.redLabel, '红'),
                             (dialog.greenLabel, '绿'), (dialog.blueLabel, '蓝')):
            widget.setText(text)
        def apply(color):
            if self._closed:return
            colors[index] = color.name().upper()
            self._options = replace(self._options, brand_override=tuple(colors))
            self._sync_colors()
            self._changed()
        dialog.colorChanged.connect(apply)
        dialog.exec()
        self._color_dialog = None
        dialog.deleteLater()

    def _reset_colors(self):
        self._options = replace(self._options, brand_override=None)
        self._sync_colors()
        self._changed()

    def _invalidate_preview(self):
        self._logo_status = None
        self._generation = None
        if self._controller is not None:
            self._controller.cancel()
        self.preview.image = QImage()
        self.preview.message = '正在生成预览'
        self.preview.update()
        self._timer.start()

    def _current_request(self):
        return self._builder(self._options)

    def _ensure_controller(self):
        if self._controller is None:
            from route_export_worker import RouteExportController
            self._controller = RouteExportController(self)
            self._controller.ready.connect(self._ready)
            self._controller.failed.connect(self._failed)

    def _submit_preview(self):
        if self._closed or self._exporting:
            return
        try:
            self._ensure_controller()
            self._generation = self._controller.submit_preview(self._current_request(),
                (max(1, self.preview.width()), max(1, self.preview.height())))
        except Exception as error:
            self._error(str(error))

    def _ready(self, generation, result):
        if self._closed or generation != self._generation:
            return
        self.error_label.hide()
        if isinstance(result, QImage):
            self._logo_status = result.text('logo_status')
            self._sync_logo()
            self.preview.image = result
            self.preview.update()
        else:
            self.exported.emit(result)
            self.accept()

    def _failed(self, generation, message):
        if self._closed or generation != self._generation:
            return
        if not self._exporting:
            self._valid = False
            self.preview.message = '无法生成预览'
            self.preview.update()
        self._exporting = False
        self.export_button.setText('导出')
        self.settings_host.setEnabled(True)
        self._sync_logo()
        self._error(message)

    def _error(self, message):
        self.error_label.setText(message)
        self.error_label.show()

    def _export(self):
        if self._closed or self._exporting:
            return
        self._timer.stop()
        fmt = self._options.format
        path, _ = FluentFileDialog.getSaveFileName(self, '导出单线线路图', f'{self._request.information.route_name}.{fmt.lower()}', f'{fmt} 文件 (*.{fmt.lower()})')
        if not path or self._closed:
            return
        try:
            self._ensure_controller()
            self._exporting = True
            self.settings_host.setEnabled(False)
            self.export_button.setEnabled(False)
            self.export_button.setText('正在导出')
            self._generation = self._controller.submit_export(self._current_request(), Path(path))
        except Exception as error:
            self._failed(self._generation, str(error))

    def done(self, result):
        self._closed = True
        if self._color_dialog is not None:self._color_dialog.reject()
        for child in self.findChildren(QDialog):
            if child is not self._color_dialog and child.isVisible():child.reject()
        self._timer.stop()
        self._generation = None
        if self._controller is not None:
            self._controller.close()
        super().done(result)

    def closeEvent(self, event):
        self.reject()
        event.accept()
