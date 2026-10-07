"""Library Fluent elevation isolated from the real card's drawing effect.

Uses qfluentwidgets.DropShadowAnimation and Qt's actual blurred drop shadow.
Only its source is a lightweight rounded surface; charts are never shadow inputs.
The carrier clips out the source fill, preserving geometry and existing effects.
"""
from __future__ import annotations
import weakref
import sys
from PySide6.QtCore import QEvent, QObject, QPoint, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPainterPath
from PySide6.QtWidgets import QWidget, QGraphicsDropShadowEffect, QAbstractScrollArea, QGraphicsOpacityEffect
from qfluentwidgets import CardWidget
from qfluentwidgets.components.widgets.card_widget import DropShadowAnimation
from shiboken6 import isValid
import stats_motion as motion_policy

class _ShadowOnlyEffect(QGraphicsDropShadowEffect):
    def __init__(self, source):
        super().__init__(source)
        self.source = source

    def draw(self, painter):
        if not isValid(self.source): return
        rect = QRectF(self.source.rect())
        inner = QPainterPath()
        inner.addRoundedRect(rect,self.source.radius,self.source.radius)
        outer = QPainterPath();outer.addRect(rect.adjusted(-40,-40,40,45))
        painter.save();painter.setClipPath(outer.subtracted(inner),Qt.ClipOperation.IntersectClip)
        if self.source.visible_clip is not None:
            painter.setClipRect(self.source.visible_clip,Qt.ClipOperation.IntersectClip)
        painter.setOpacity(painter.opacity()*self.source.surface_opacity)
        super().draw(painter)
        painter.restore()

class _InputTransparentDecoration(QWidget):
    """Preserve input transparency even if Qt promotes this child to an HWND."""
    def nativeEvent(self, event_type, message):
        if sys.platform == 'win32' and event_type in (b'windows_generic_MSG', b'windows_dispatcher_MSG'):
            from ctypes.wintypes import MSG
            if MSG.from_address(int(message)).message == 0x84:  # WM_NCHITTEST
                return True, -1  # HTTRANSPARENT: continue hit testing siblings
        return super().nativeEvent(event_type, message)


class _ShadowSource(_InputTransparentDecoration):
    def __init__(self, parent, radius):
        super().__init__(parent)
        self.radius=radius
        self.visible_clip=None
        self.surface_opacity=1.
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def paintEvent(self,event):
        painter=QPainter(self);painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen);painter.setBrush(QColor('white'))
        painter.drawRoundedRect(self.rect(),self.radius,self.radius)

class _StableDropShadowAnimation(DropShadowAnimation):
    """Reuse library transition while owning one dedicated effect.

    The default re-creates effects on enter and removes any parent effect on leave.
    Here its parent is a dedicated carrier and cleanup is explicit.
    """
    def __init__(self, source):
        super().__init__(source,normalColor=QColor(0,0,0,0),hoverColor=QColor(0,0,0,20))
        self.shadowEffect.deleteLater()
        self.shadowEffect=_ShadowOnlyEffect(source)
        self.setOffset(0,5);self.setBlurRadius(38)
        self.shadowEffect.setOffset(self.offset)
        self.shadowEffect.setBlurRadius(self.blurRadius)
        self.shadowEffect.setColor(self.normalColor)
        source.setGraphicsEffect(self.shadowEffect)
        self.setTargetObject(self.shadowEffect);self.setPropertyName(b'color')

    def eventFilter(self,obj,event): return False
    def _onAniFinished(self): pass

class _ElevationLayer(_InputTransparentDecoration):
    def __init__(self,root):
        super().__init__(root)
        self.setObjectName('fluentElevationLayer')
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.controllers=weakref.WeakSet()
        self.active=weakref.WeakSet()
        self.dirty=weakref.WeakSet()
        self._pending=False
        self.setGeometry(root.rect());root.installEventFilter(self);self.show()

    def eventFilter(self,obj,event):
        if obj is self.parentWidget() and event.type()==QEvent.Type.Resize:
            self.setGeometry(obj.rect());self.refresh()
        return False

    def refresh(self):
        if not self._pending:
            self._pending=True
            QTimer.singleShot(0,self._refresh_now)

    def _refresh_now(self):
        if not isValid(self):return
        self._pending=False
        controllers=[c for c in self.active | self.dirty if isValid(c) and getattr(c,'widget',None) is not None and isValid(c.widget)]
        self.dirty.clear()
        if not controllers:return
        self.raise_()
        suppressed=set()
        for controller in controllers:
            if not controller.hovered:continue
            ancestor=controller.widget.parentWidget()
            while ancestor is not None and ancestor is not self.parentWidget():
                suppressed.add(ancestor);ancestor=ancestor.parentWidget()
        for controller in controllers:
            source=getattr(controller,'carrier',None)
            if source is None or not isValid(source): continue
            card=controller.widget
            nested=card in suppressed
            visible=card.isVisible() and controller.level>0 and not nested
            source.setVisible(visible)
            if visible:
                p=card.mapTo(self.parentWidget(),QPoint())
                ancestor=card;clip=self.rect();opacity=1.;draw_offset=0
                while ancestor and ancestor is not self.parentWidget():
                    parent=ancestor.parentWidget()
                    if isinstance(parent,QAbstractScrollArea) and parent.viewport() is ancestor:
                        q=ancestor.mapTo(self.parentWidget(),QPoint())
                        clip=clip.intersected(ancestor.rect().translated(q))
                    effect=ancestor.graphicsEffect()
                    if isinstance(effect,QGraphicsOpacityEffect):
                        opacity*=effect.opacity()
                        draw_offset+=getattr(effect,'offset',0)
                    ancestor=parent
                p+=QPoint(0,round(draw_offset))
                source.setGeometry(p.x(),p.y(),card.width(),card.height())
                source.visible_clip=QRectF(clip.translated(-p))
                source.surface_opacity=opacity
                if not clip.intersects(source.geometry()):source.hide()
                source.update()
        self.update()

class CardElevation(QObject):
    def __init__(self,widget,radius=8):
        super().__init__(widget)
        self.widget,self.radius=widget,radius
        self.level,self.hovered=0.,False
        self.layer=self.carrier=self.animation=None
        self.ancestors=weakref.WeakSet()
        widget.installEventFilter(self)

    def _ensure_layer(self):
        root=self.widget.window()
        layer=getattr(root,'_fluent_elevation_layer',None)
        if layer is None or not isValid(layer):
            layer=_ElevationLayer(root);root._fluent_elevation_layer=layer
        if self.layer is not layer:
            if self.layer is not None and isValid(self.layer):
                self.layer.controllers.discard(self)
                self.layer.active.discard(self)
                self.layer.dirty.discard(self)
            self.layer=layer;layer.controllers.add(self)
            if self.carrier is not None and isValid(self.carrier):self.carrier.deleteLater()
            self.carrier=_ShadowSource(layer,self.radius)
            self.animation=_StableDropShadowAnimation(self.carrier)
            self.animation.valueChanged.connect(self._advance)
            self.widget.destroyed.connect(self.carrier.deleteLater)
        ancestor=self.widget.parentWidget()
        while ancestor:
            if ancestor not in self.ancestors:
                ancestor.installEventFilter(self);self.ancestors.add(ancestor)
            ancestor=ancestor.parentWidget()
        return layer

    def _advance(self,color):
        self.level=color.alphaF()/self.animation.hoverColor.alphaF() if self.animation else 0.
        if self.layer is not None and isValid(self.layer):
            if self.level:self.layer.active.add(self)
            else:self.layer.active.discard(self)
            self.layer.dirty.add(self);self.layer.refresh()

    def set_hovered(self,hovered):
        self.hovered=bool(hovered and self.widget.isEnabled() and self.widget.isVisible())
        if not self.hovered and self.animation is None:return
        self._ensure_layer()
        animation=self.animation;animation.stop()
        target=animation.hoverColor if self.hovered else animation.normalColor
        if not motion_policy.animations_enabled() or not self.widget.isVisible():
            animation.shadowEffect.setColor(target);self._advance(target);return
        animation.setDuration(150)
        animation.setStartValue(animation.shadowEffect.color())
        animation.setEndValue(target);animation.start()

    def _clear(self):
        self.hovered=False;self.level=0.
        if self.animation is not None and isValid(self.animation):
            self.animation.stop();self.animation.shadowEffect.setColor(self.animation.normalColor)
        if self.layer is not None and isValid(self.layer):
            self.layer.active.discard(self);self.layer.dirty.add(self);self.layer.refresh()

    def eventFilter(self,obj,event):
        widget=getattr(self,'widget',None)
        if widget is None or not isValid(widget):return False
        kind=event.type()
        if obj is not widget:
            if not isValid(obj) or not obj.isAncestorOf(widget):return False
            if kind==QEvent.Type.Hide:self._clear()
            elif kind in (QEvent.Type.Move,QEvent.Type.Resize,QEvent.Type.LayoutRequest):
                if self.layer is not None and isValid(self.layer) and self.level:self.layer.refresh()
            return False
        if kind==QEvent.Type.Enter:self.set_hovered(True)
        elif kind==QEvent.Type.Leave:self.set_hovered(False)
        elif kind in (QEvent.Type.Hide,QEvent.Type.EnabledChange):
            if not widget.isVisible() or not widget.isEnabled():self._clear()
        elif kind in (QEvent.Type.Move,QEvent.Type.Resize,QEvent.Type.Show,QEvent.Type.ParentChange):
            if widget.isVisible() and self.level:self._ensure_layer().refresh()
        return False

def attach_card_elevation(widget,radius=8):
    """Idempotent; library shadow never changes the real card's geometry/effect."""
    controller=getattr(widget,'_card_elevation',None)
    if controller is None:
        controller=CardElevation(widget,radius);widget._card_elevation=controller
    return controller

def refresh_elevation(widget):
    layer=getattr(widget.window(),'_fluent_elevation_layer',None)
    if layer is not None and isValid(layer):layer.refresh()

class FluentSurfaceCard(CardWidget):
    def __init__(self,parent=None):
        super().__init__(parent);self.setBorderRadius(8);attach_card_elevation(self)
