"""Light Fluent presentation tokens shared by statistics widgets and charts.

Colors are CSS-compatible ``str`` hex values. Sizes, including font sizes,
are ``int`` Qt logical pixels (use ``QFont.setPixelSize`` or QSS ``px``).
This module intentionally has no Qt import and contains no business values.
"""

# Surfaces and text shared by the page, controls, and chart renderer.
PAGE_BG: str = '#F4F8FC'
CARD_BG: str = '#FFFFFF'
SURFACE_SUBTLE: str = '#F8FBFE'
BORDER: str = '#E3EAF3'
BORDER_STRONG: str = '#C8D6E7'
TEXT_PRIMARY: str = '#18314F'
TEXT_SECONDARY: str = '#65758B'
TEXT_DISABLED: str = '#98A8B9'
# WinUI light ToolTip: neutral primary text, regular 12 logical px.
TOOLTIP_TEXT: str = '#1B1B1B'
TOOLTIP_BG: str = '#FFFFFF'
TOOLTIP_BORDER: str = '#D6D6D6'
TOOLTIP_FONT_SIZE: int = 12
TOOLTIP_RADIUS: int = 4
ACCENT: str = '#0067C0'
ACCENT_HOVER: str = '#005BAA'
ACCENT_PRESSED: str = '#004A8C'
ACCENT_SOFT: str = '#E8F2FC'
SEGMENT_QUIET_BG: str = '#EFF3F8'
SEGMENT_QUIET_HOVER: str = '#E7EDF5'
FOCUS_RING: str = '#0067C0'
GRID_COLOR: str = '#E8EFF6'
AXIS_COLOR: str = '#BCCBDD'
ERROR_COLOR: str = '#B42318'
CHART_LINE_WIDTH: float = 2.0
CHART_GRID_WIDTH: float = 1.0
CHART_AREA_OPACITY: float = 0.10
CHART_COMPARISON_OPACITY: float = 0.45
CHART_BAR_GRADIENT_TOP_FACTOR: float = 0.96
CHART_SHADOW_OPACITY: float = 0.08

# Identity colors, assigned in stable company-ID sort order for one save.
# Every company mark, legend dot, and KPI badge uses these exact values.
COMPANY_COLORS: tuple[str, ...] = (
    '#397CC3', '#2C9B78', '#7967B7', '#B58338',
    '#B9627F', '#358EA3', '#849542', '#8071A5',
)
CHART_BLUE: str = COMPANY_COLORS[0]

# Breakdown categories have their own identity, separate from company colors.
CATEGORY_COLORS: tuple[str, ...] = (
    '#4C90A5', '#52A29F', '#7F76B8', '#BD8A55',
    '#9879AB', '#78965B', '#6C8CAD', '#A77F91',
)

# Opt-in identity palettes for company and network data.  Keep the existing
# palettes above as the city dashboard default.
DATA_COMPANY_COLORS: tuple[str, ...] = (
    '#1677FF', '#00A67A', '#8B5CEB', '#EB8A2F',
    '#DB5C87', '#15A5C4', '#7D9E32', '#AD684F',
)
DATA_CATEGORY_COLORS: tuple[str, ...] = (
    '#1677FF', '#F5A653', '#159A79', '#A477E6',
    '#C63864', '#72C7D9', '#B99027', '#6C85D8',
)
# Transport identities are independent of passenger demographics and companies.
TRANSPORT_COLORS: dict[str, str] = {
    'bus': '#1976D2', 'trolleybus': '#7B2CBF', 'tram': '#D32F2F',
    'waterbus': '#F2C230', 'monorail': '#F06A24', 'metro': '#1E9E59',
}
TRANSPORT_ALIASES: dict[str, str] = {
    '公交': 'bus', 'trolley': 'trolleybus', '无轨电车': 'trolleybus',
    '有轨电车': 'tram', 'ferry': 'waterbus', '水上巴士': 'waterbus',
    '单轨': 'monorail', '单轨列车': 'monorail', '地铁': 'metro',
}

def transport_color(group) -> str | None:
    key = str(group).strip().lower()
    return TRANSPORT_COLORS.get(TRANSPORT_ALIASES.get(key, key))

DATA_CATEGORY_GROUPS: tuple[str, ...] = (
    'BlueCollar', 'WhiteCollar', 'BusinessPeople', 'Pensioner',
    'Student', 'Tourist', 'bus', 'tram', 'trolley', 'metro',
    'waterbus', 'misc',
)

FONT_FAMILY: str = 'Microsoft YaHei UI'
FONT_FALLBACKS: tuple[str, ...] = ('Microsoft YaHei', 'Segoe UI', 'sans-serif')
FONT_SIZE_CAPTION: int = 12
FONT_SIZE_BODY: int = 14
FONT_SIZE_CHART_TITLE: int = 14
FONT_SIZE_KPI: int = 21
FONT_SIZE_PAGE_TITLE: int = 29

SPACE_XS: int = 4
SPACE_SM: int = 8
SPACE_MD: int = 12
SPACE_LG: int = 16
SPACE_XL: int = 20
PAGE_MARGIN: int = 20
NARROW_PAGE_MARGIN: int = 12
SECTION_GAP: int = 16
CARD_PADDING: int = 16
CONTROL_GAP: int = 8

RADIUS_CONTROL: int = 6
RADIUS_CHART: int = 8
RADIUS_KPI: int = 8
RADIUS_CARD: int = 12

CONTROL_HEIGHT: int = 36
ACTION_BUTTON_WIDTH: int = 144
FOCUS_RING_WIDTH: int = 2
ICON_SIZE: int = 18
CHART_ACTION_ICON_SIZE: int = 16
CHART_HEADER_GAP: int = 7
CHART_CONTENT_GAP: int = 10
NAV_WIDTH_EXPANDED: int = 192
NAV_WIDTH_COMPACT: int = 48
NAV_ITEM_HEIGHT: int = 44
PAGE_ICON_SIZE: int = 48

# These thresholds refer to content width after navigation and page margins.
CONTENT_SINGLE_COLUMN_BELOW: int = 720
CONTENT_DOUBLE_CHART_COLUMN_FROM: int = 1120
