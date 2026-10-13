"""Saved company branding, local game masks and immutable export images.

Company branding never changes the application, mode or statistical palette.
The game logo shader consumes RGB mask channels, not the texture's grey backdrop
or the saved colors' alpha. Assets are read locally and remain outside the package.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from threading import RLock
from typing import Mapping
import colorsys
import os
import re

import numpy as np
from PySide6.QtCore import QByteArray, QBuffer, QIODevice
from PySide6.QtGui import QImage, QImageReader


@dataclass(frozen=True)
class RasterImage:
    width: int
    height: int
    rgba: bytes

    def __post_init__(self):
        if self.width <= 0 or self.height <= 0 or len(self.rgba) != self.width*self.height*4:
            raise ValueError('无效的标志图像')
        if not isinstance(self.rgba, bytes):
            raise TypeError('标志像素必须为不可变字节')

    def to_qimage(self) -> QImage:
        """Copy into a privately owned QImage; no GUI-thread resource required."""
        return QImage(self.rgba, self.width, self.height, self.width*4,
                      QImage.Format.Format_RGBA8888).copy()

    @classmethod
    def from_qimage(cls, image: QImage) -> RasterImage:
        if image.isNull():
            raise ValueError('无法读取标志图像')
        rgba = image.convertToFormat(QImage.Format.Format_RGBA8888)
        return cls(rgba.width(), rgba.height(), bytes(rgba.constBits()))


@dataclass(frozen=True)
class BrandColors:
    color1: str | None
    color2: str | None


@dataclass(frozen=True)
class CompanyBranding:
    company_id: str
    company_name: str
    logo_key: str
    color1_argb: int | None
    color2_argb: int | None
    logo_image: RasterImage | None = None
    logo_status: str = 'missing_asset'
    logo_mask: RasterImage | None = None
    brand_override: tuple[str, str] | None = None


def _argb(value) -> int | None:
    if value is None or str(value).strip() == '':
        return None
    try:
        result = int(str(value).strip(), 0) if str(value).lower().startswith('0x') else int(value)
        return result if 0 <= result <= 0xFFFFFFFF else None
    except (ValueError, TypeError, OverflowError):
        return None


def _hex(value) -> str:
    if not isinstance(value,str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',value):
        raise ValueError('品牌颜色须为 #RRGGBB')
    return value.upper()


def _saved_hex(value: int | None) -> str | None:
    return f'#{value & 0xFFFFFF:06X}' if value is not None else None


def _rgb(value: str):
    value = _hex(value)
    return tuple(int(value[i:i+2],16)/255 for i in (1,3,5))


def _luminance(rgb):
    channels = tuple(v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4 for v in rgb)
    return sum(v*w for v,w in zip(channels,(.2126,.7152,.0722)))


def contrast_ratio(color: str, background: str) -> float:
    a,b = sorted((_luminance(_rgb(color)),_luminance(_rgb(background))))
    return (b+.05)/(a+.05)


def _color_hex(rgb):
    return '#' + ''.join(f'{max(0,min(255,round(v*255))):02X}' for v in rgb)


def _night_color(color, background):
    if color is None:
        return None
    if contrast_ratio(color,background) >= 4.5:
        return color
    # The approved red target is slightly cooler than pure red; other colors
    # retain HSL hue and saturation as lightness increases.
    seed = '#FF626B' if color == '#FF0000' else color
    if contrast_ratio(seed,background) >= 4.5:
        return seed
    hue,lightness,saturation = colorsys.rgb_to_hls(*_rgb(seed))
    if contrast_ratio('#FFFFFF',background) < 4.5:
        raise ValueError('夜间背景过亮，无法通过提亮达到文字对比度')
    low,high = lightness,1.
    # Check rounded output as well as the continuous color to guarantee the
    # returned 8-bit RGB satisfies the threshold at its actual background.
    for _ in range(32):
        middle = (low+high)/2
        candidate = _color_hex(colorsys.hls_to_rgb(hue,middle,saturation))
        if contrast_ratio(candidate,background) >= 4.5:
            high = middle
        else:
            low = middle
    return _color_hex(colorsys.hls_to_rgb(hue,high,saturation))


def derive_brand_colors(branding: CompanyBranding, theme: str, background: str) -> BrandColors:
    """Preserve saved ARGB; return separate colors for the actual export surface."""
    colors = branding.brand_override or (_saved_hex(branding.color1_argb),_saved_hex(branding.color2_argb))
    if theme == 'day':
        return BrandColors(*colors)
    if theme != 'night':
        raise ValueError('未知成品风格')
    _hex(background)
    return BrandColors(*(_night_color(c,background) for c in colors))


def _shade(mask: RasterImage, color1: str, color2: str) -> RasterImage:
    """CPU evaluation of the audited Custom/LogoShader D3D9 arithmetic.

    Gamma-configured game inputs remain in encoded RGB; no extra gamma pass.
    Company alpha is intentionally ignored, as in the original shader.
    """
    texture = np.frombuffer(mask.rgba,dtype=np.uint8).reshape(mask.height,mask.width,4)[:,:,:3]/255.
    u = np.clip((texture-.49000001)*-2.04081631,0,1)
    channels = u*u*(3-2*u)
    white = np.clip((texture[:,:,2]-.50999999)*2.04081631,0,1)
    white = white*white*(3-2*white)
    main,secondary,black = (channels[:,:,i] for i in range(3))
    colored,uncolored = main+secondary,black+white
    total = colored+uncolored
    c1,c2 = np.asarray(_rgb(color1)),np.asarray(_rgb(color2))
    mixed = c2+(main/np.maximum(colored,.01))[:,:,None]*(c1-c2)
    white_fraction = white/np.maximum(uncolored,.01)
    mixed -= white_fraction[:,:,None]
    result = mixed*(colored/np.maximum(total,.01))[:,:,None]+white_fraction[:,:,None]
    positive = (channels>0).sum(axis=2)+(white>0).astype(int)
    alpha = np.maximum(total,positive-1)
    rgba = np.concatenate((result,alpha[:,:,None]),axis=2)
    return RasterImage(mask.width,mask.height,np.round(np.clip(rgba,0,1)*255).astype(np.uint8).tobytes())


def render_brand_logo(branding: CompanyBranding, colors: BrandColors | None = None) -> RasterImage | None:
    if branding.logo_status == 'pending_asset':
        branding = resolve_brand_assets(branding)
    if branding.logo_mask is None:
        return branding.logo_image
    colors = colors or derive_brand_colors(branding,'day','#FFFFFF')
    if colors.color1 is None or colors.color2 is None:
        return None
    return _shade(branding.logo_mask,colors.color1,colors.color2)


def _read_custom(source) -> RasterImage | None:
    if isinstance(source,RasterImage):
        return source if source.width*source.height <= 16_000_000 else None
    buffer = None
    if isinstance(source,bytes):
        buffer = QBuffer()
        buffer.setData(QByteArray(source)); buffer.open(QIODevice.OpenModeFlag.ReadOnly)
        reader = QImageReader(buffer)
    elif isinstance(source,(str,Path)):
        reader = QImageReader(str(source))
    else:
        return None
    size = reader.size()
    if not size.isValid() or size.width()*size.height() > 16_000_000:
        return None
    reader.setAutoTransform(True)
    image = reader.read()
    return None if image.isNull() else RasterImage.from_qimage(image)


def resolve_company_branding(company: Mapping, asset_provider=None, *, logo_source='save',
                             custom_logo=None, brand_override=None, resolve_assets=True) -> CompanyBranding:
    """Resolve one actual company record by its saved identity and resource key."""
    if logo_source not in ('save','custom','none'):
        raise ValueError('未知公司标志来源')
    override = None
    if brand_override is not None:
        if len(brand_override) != 2:
            raise ValueError('公司品牌需要两种颜色')
        override = tuple(_hex(value) for value in brand_override)
    brand = CompanyBranding(str(company.get('公司标识') or company.get('玩家ID') or ''),
        str(company.get('公司名称') or ''),str(company.get('公司标志') or ''),
        _argb(company.get('颜色1')),_argb(company.get('颜色2')),brand_override=override)
    if logo_source == 'none':
        return replace(brand,logo_status='hidden')
    if logo_source == 'custom':
        image = _read_custom(custom_logo)
        return replace(brand,logo_image=image,logo_status='custom' if image else 'invalid_custom')
    if not brand.logo_key:
        return replace(brand,logo_status='no_logo')
    colors = derive_brand_colors(brand,'day','#FFFFFF')
    if colors.color1 is None or colors.color2 is None:
        return replace(brand,logo_status='missing_colors')
    if not resolve_assets:
        return replace(brand,logo_status='pending_asset')
    return resolve_brand_assets(brand,asset_provider)


def resolve_brand_assets(brand: CompanyBranding, asset_provider=None) -> CompanyBranding:
    """Complete a frozen saved-logo request on a worker, leaving it unchanged."""
    if brand.logo_status not in ('pending_asset','missing_asset') or not brand.logo_key:
        return brand
    colors = derive_brand_colors(brand,'day','#FFFFFF')
    if colors.color1 is None or colors.color2 is None:
        return replace(brand,logo_status='missing_colors')
    provider = asset_provider if asset_provider is not None else _default_provider()
    mask = provider.load_logo_mask(brand.logo_key)
    if mask is None:
        return replace(brand,logo_status='missing_asset')
    return replace(brand,logo_mask=mask,logo_image=_shade(mask,colors.color1,colors.color2),logo_status='available')


def _bundle_candidates(managed_root=None):
    """Use existing asset overrides and Steam layouts, never analysis jobs."""
    for name in ('CIM2_BUNDLE_ROOT','CIM2_BUNDLES_DIR'):
        if os.environ.get(name):
            yield Path(os.environ[name])
    managed = managed_root or os.environ.get('CIM2_MANAGED_ROOT')
    if managed:
        yield Path(managed).parent/'Data'/'Bundles'
    # Resolve installation roots rather than binding a single user's location.
    roots = [Path(os.environ.get('PROGRAMFILES(X86)',r'C:\Program Files (x86)')),
             Path(os.environ.get('PROGRAMFILES',r'C:\Program Files'))]
    drive = Path(__file__).resolve().anchor
    if drive:
        roots.extend((Path(drive)/'Program Files (x86)',Path(drive)/'SteamLibrary'))
    for root in roots:
        for steam in (root,root/'Steam',root/'SteamLibrary'):
            yield steam/'steamapps'/'common'/'Cities in Motion 2'/'CIM2_Data'/'Data'/'Bundles'


class GameLogoAssetProvider:
    """Read only the installed logo bundle; cache immutable masks in memory."""
    def __init__(self,bundle_root=None,managed_root=None):
        self.bundle_root = Path(bundle_root) if bundle_root is not None else None
        self.managed_root = managed_root
        self._lock = RLock()
        self._signature = None
        self._masks = {}

    def load_logo_mask(self,logo_key: str) -> RasterImage | None:
        candidates = (self.bundle_root,) if self.bundle_root is not None else _bundle_candidates(self.managed_root)
        path = next((root/'Global'/'Logos.bundle' for root in candidates
                     if (root/'Global'/'Logos.bundle').is_file()),None)
        if path is None:
            return None
        try:
            info = path.stat()
            signature = (str(path.resolve()),info.st_mtime_ns,info.st_size)
        except OSError:
            return None
        with self._lock:
            if self._signature != signature:
                self._masks = self._load(path)
                self._signature = signature
            return self._masks.get(logo_key)

    @staticmethod
    def _load(path):
        try:
            import UnityPy
            from UnityPy.classes import PPtr
            env = UnityPy.load(str(path))
            result = {}
            for obj in env.objects:
                if obj.type.name != 'MonoBehaviour':
                    continue
                tree = obj.read_typetree()
                for item in tree.get('m_menuItemInfo',[]):
                    if item.get('m_menu') != 'company-logo':
                        continue
                    pointer = item.get('m_texture',{})
                    # Resolve the actual PPtr, including its owning assets file.
                    texture = PPtr(m_PathID=pointer['m_PathID'],m_FileID=pointer.get('m_FileID',0),
                                   assetsfile=obj.assets_file).read()
                    image = texture.image.convert('RGBA')
                    result[str(item['m_name'])] = RasterImage(image.width,image.height,image.tobytes())
            return result
        except (OSError,ValueError,KeyError,AttributeError,ImportError,RuntimeError):
            return {}


_provider_lock = RLock()
_provider = None


def _default_provider():
    global _provider
    with _provider_lock:
        if _provider is None:
            _provider = GameLogoAssetProvider()
        return _provider
