"""Brand identity, shader transparency and export-safe color regressions."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
from pathlib import Path
import csv
import os

import pytest
from PySide6.QtGui import QImage


def api():
    import company_branding
    return company_branding


def company(identity='one', **values):
    return {'公司标识': identity, '公司名称': '相同名称', '公司标志': 'arrow',
            '颜色1': 0xFFFF0000, '颜色2': 0xFFFFFFFF, **values}


class Masks:
    def load_logo_mask(self, key):
        b = api()
        # Native shader basis: primary / secondary / black / white / clear.
        masks = {'arrow': bytes((0,128,128,255, 128,0,128,255,
                                128,128,0,255, 128,128,255,255, 127,128,128,255)),
                 'other': bytes((128,0,128,255))}
        value = masks.get(key)
        return b.RasterImage(len(value)//4, 1, value) if value else None


def test_company_identity_and_argb_are_preserved_without_name_matching():
    b = api()
    first = b.resolve_company_branding(company(), Masks())
    second = b.resolve_company_branding(company('two', 公司标志='other', 颜色1=0, 颜色2=None), Masks())
    assert (first.company_id, first.logo_key, first.color1_argb) == ('one','arrow',0xFFFF0000)
    assert (second.company_id, second.logo_key, second.color1_argb, second.color2_argb) == ('two','other',0,None)
    assert second.logo_image is None and second.logo_status == 'missing_colors'
    with pytest.raises(FrozenInstanceError):
        first.color1_argb = 0


def test_shader_uses_both_colors_black_white_and_transparency_not_argb_alpha():
    b = api()
    brand = b.resolve_company_branding(company(颜色1=0x00FF0000), Masks())
    pixels = brand.logo_image.rgba
    assert [tuple(pixels[i:i+4]) for i in range(0,20,4)] == [
        (255,0,0,255), (255,255,255,255), (0,0,0,255), (255,255,255,255), (0,0,0,0)]
    assert brand.logo_status == 'available'


@pytest.mark.parametrize('values,status', [({'公司标志':'unknown'},'missing_asset'),
    ({'公司标志':''},'no_logo'), ({'颜色1':None},'missing_colors')])
def test_missing_brand_data_preserves_real_name_without_a_fabricated_logo(values,status):
    brand = api().resolve_company_branding(company(**values), Masks())
    assert brand.logo_image is None and brand.logo_status == status
    assert brand.company_name == '相同名称'


@pytest.mark.parametrize('color', ['#440000','#000044','#000000','#FF0000','#07130A'])
@pytest.mark.parametrize('background', ['#07192B','#172435','#354256'])
def test_night_colors_reach_text_and_symbol_contrast_and_keep_original(color,background):
    b = api()
    raw = 0xFF000000 | int(color[1:],16)
    brand = b.resolve_company_branding(company(颜色1=raw,颜色2=raw), Masks())
    result = b.derive_brand_colors(brand,'night',background)
    assert b.contrast_ratio(result.color1,background) >= 4.5
    assert b.contrast_ratio(result.color2,background) >= 4.5
    assert brand.color1_argb == brand.color2_argb == raw
    if color != '#000000':
        import colorsys
        original = colorsys.rgb_to_hls(*[int(color[i:i+2],16)/255 for i in (1,3,5)])[0]
        derived = colorsys.rgb_to_hls(*[int(result.color1[i:i+2],16)/255 for i in (1,3,5)])[0]
        delta = min(abs(original-derived), 1-abs(original-derived))
        assert delta < .02


def test_night_red_uses_target_and_recolors_mask_without_changing_alpha():
    b = api()
    brand = b.resolve_company_branding(company(),Masks())
    colors = b.derive_brand_colors(brand,'night','#07192B')
    assert colors.color1 == '#FF626B'
    night = b.render_brand_logo(brand,colors)
    assert night.rgba[:3] == bytes.fromhex('FF626B')
    assert night.rgba[3::4] == brand.logo_image.rgba[3::4]
    assert b.derive_brand_colors(brand,'day','#FAFCFF').color1 == '#FF0000'


def test_override_and_custom_image_remain_independent_from_saved_brand(tmp_path):
    b = api()
    image = QImage(2,3,QImage.Format.Format_RGBA8888)
    image.fill(0x7F112233)
    path = tmp_path/'custom.png'
    assert image.save(str(path))
    brand = b.resolve_company_branding(company(),Masks(),logo_source='custom',custom_logo=path,
                                      brand_override=('#000000','#000033'))
    assert brand.logo_status == 'custom' and brand.logo_image.width == 2 and brand.logo_image.height == 3
    colors = b.derive_brand_colors(brand,'night','#07192B')
    assert b.contrast_ratio(colors.color1,'#07192B') >= 4.5
    assert b.render_brand_logo(brand,colors) == brand.logo_image
    assert (brand.color1_argb,brand.color2_argb) == (0xFFFF0000,0xFFFFFFFF)
    assert b.resolve_company_branding(company(),Masks(),logo_source='none').logo_status == 'hidden'
    assert b.resolve_company_branding(company(),Masks(),logo_source='custom',custom_logo=tmp_path/'missing.png').logo_status == 'invalid_custom'


def test_worker_can_render_and_copy_qimage_without_shared_mutation():
    b = api()
    brand = b.resolve_company_branding(company(),Masks())
    def render(_):
        colors = b.derive_brand_colors(brand,'night','#07192B')
        raster = b.render_brand_logo(brand,colors)
        image = raster.to_qimage()
        image.fill(0)
        return raster.to_qimage().pixelColor(0,0).name()
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert list(pool.map(render,range(12))) == ['#ff626b']*12


def test_gui_freeze_defers_assets_until_worker_and_custom_bytes_are_supported(tmp_path):
    b = api()
    class NoGuiReads:
        def load_logo_mask(self,key):
            raise AssertionError('GUI must not read installed assets')
    frozen = b.resolve_company_branding(company(),NoGuiReads(),resolve_assets=False)
    assert frozen.logo_status == 'pending_asset' and frozen.logo_mask is None
    ready = b.resolve_brand_assets(frozen,Masks())
    assert ready.logo_status == 'available' and ready.logo_image
    assert frozen.logo_status == 'pending_asset'
    path = tmp_path/'rgba.png'
    ready.logo_image.to_qimage().save(str(path))
    custom = b.resolve_company_branding(company(),logo_source='custom',custom_logo=path.read_bytes())
    assert custom.logo_image == ready.logo_image


def test_missing_or_corrupt_installed_bundle_is_a_missing_asset_not_an_export_crash(tmp_path):
    b = api()
    provider = b.GameLogoAssetProvider(tmp_path)
    assert b.resolve_company_branding(company(),provider).logo_status == 'missing_asset'
    (tmp_path/'Global').mkdir()
    (tmp_path/'Global'/'Logos.bundle').write_bytes(b'UnityFS\0invalid')
    assert b.resolve_company_branding(company(),provider).logo_status == 'missing_asset'


def test_csv_brand_fields_pass_through_by_company_identity_and_keep_zero(tmp_path):
    from report_model import load_session
    records = [company('one'), company('two',颜色1=0,颜色2=None,公司标志='other')]
    with (tmp_path/'CIM2_公司信息_brand.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer = csv.DictWriter(f,fieldnames=list(records[0]))
        writer.writeheader(); writer.writerows(records)
    result = load_session(tmp_path,'brand')['companies']
    assert [(x['公司标识'],x['公司标志'],x['颜色1'],x['颜色2']) for x in result] == [
        ('one','arrow',0xFFFF0000,0xFFFFFFFF),('two','other',0,None)]


def test_extractor_preserves_missing_color_instead_of_fabricating_zero():
    # Isolate the pure function from the extractor's CLI/runtime initialization.
    import ast
    source = Path(__file__).with_name('extract_runtime_data.py').read_text(encoding='utf-8-sig')
    tree = ast.parse(source)
    function = next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='company_rows')
    scope = {'field':lambda obj,key: obj.get(key) if obj else None,
             'array_values':lambda value:value or [], 'as_items':lambda value:[],
             'fixed':lambda value:int(value or 0)}
    exec(compile(ast.Module(body=[function],type_ignores=[]),'<company_rows>','exec'),scope)
    raw = {'m_players':[{'m_id':'one','m_companyData':{'m_name':'name','m_logo':'arrow','m_color1':0}}]}
    _,rows,_ = scope['company_rows'](raw)
    assert (rows[0]['颜色1'],rows[0]['颜色2']) == (0,None)


def test_real_bundle_maps_menu_key_and_matches_verified_shader(monkeypatch):
    root = os.environ.get('CIM2_BRAND_TEST_BUNDLE_ROOT')
    audit = os.environ.get('CIM2_BRAND_TEST_AUDIT')
    if not root or not audit:
        pytest.skip('Optional locally installed logo bundle and audit reference not configured')
    b = api()
    provider = b.GameLogoAssetProvider(root)
    brand = b.resolve_company_branding(company(),provider)
    expected = QImage(str(Path(audit)/'arrow-original-shader-local-preview.png'))
    assert brand.logo_image.width == brand.logo_image.height == 128
    assert brand.logo_image.to_qimage() == expected.convertToFormat(QImage.Format.Format_RGBA8888)
    monkeypatch.setenv('CIM2_BUNDLE_ROOT',root)
    assert b.resolve_company_branding(company()).logo_image == brand.logo_image
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert all(x == brand.logo_mask for x in pool.map(provider.load_logo_mask,['arrow']*12))
