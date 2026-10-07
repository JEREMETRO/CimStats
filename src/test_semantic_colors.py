from semantic_colors import color_for, map_fill, company_palette, category_color_hex

def test_known_modes_keep_existing_semantics():
    assert color_for('mode', 'bus') == '#1976D2'
    assert color_for('mode', '公交') == color_for('mode', 'bus')
    assert color_for('mode', 'tram') == '#D32F2F'
    assert color_for('mode', 'trolley') == '#7B2CBF'
    import stats_tokens as tokens
    for key in ('bus','trolley','tram','metro','waterbus','monorail','trolleybus','ferry','单轨列车'):
        assert color_for('mode',key) == tokens.transport_color(key)
        assert category_color_hex(key) == tokens.transport_color(key)

def test_stable_category_identity_and_fill_derivation():
    import stats_tokens as tokens
    assert color_for('social', 'BlueCollar') == tokens.DATA_CATEGORY_COLORS[0]
    assert color_for('social', 'Tourist') == tokens.DATA_CATEGORY_COLORS[5]
    assert map_fill('usage', 'residential', 1) == color_for('usage', 'residential')
    assert map_fill('usage', 'residential', 0) == '#F4F2ED'
    assert color_for('profit', 'missing') != color_for('profit', 'zero')

def test_company_mapping_uses_complete_identity_set():
    assert company_palette(['b','a']) == company_palette(['a','b'])
    assert company_palette(['a','b'])['a'] == '#1677FF'

def test_chart_categories_share_the_registry():
    from stats_charts import category_color
    import stats_tokens as tokens
    for key in ('bus','tram','BlueCollar','Tourist'):
        domain = 'mode' if key in ('bus','tram') else 'social'
        assert category_color(key,tokens.DATA_CATEGORY_COLORS).name().upper() == color_for(domain,key)


def test_function_fill_preserves_shared_hues_and_emphasizes_density_contrast():
    from map_model import BuildingFunctionValues
    from semantic_colors import building_function_fill
    assert building_function_fill(BuildingFunctionValues(0,100,100,100),True)==map_fill('usage','mixed',.85)
    def contrast(a,b):
        return sum(abs(int(a[i:i+2],16)-int(b[i:i+2],16)) for i in (1,3,5))
    low=BuildingFunctionValues(10,0,0,100)
    high=BuildingFunctionValues(100,0,0,100)
    assert contrast(building_function_fill(low,True),building_function_fill(high,True)) > 4*contrast(
        building_function_fill(low,False),building_function_fill(high,False))
    assert building_function_fill(BuildingFunctionValues(None,None,None,None),True)!=building_function_fill(
        BuildingFunctionValues(0,0,0,0),True)
