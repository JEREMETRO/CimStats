from company_labels import company_selection_name


def test_selection_uses_actual_names_and_distinguishes_aggregate():
    names = {'a': '八连交通集团', 'b': '城东公交'}
    assert company_selection_name(names, ('a',)) == '八连交通集团'
    assert company_selection_name(names, ('b', 'a')) == '城东公交、八连交通集团合计'
    assert company_selection_name(names, ()) == '未选择公司'


def test_duplicate_company_names_keep_real_identity():
    assert company_selection_name({'a': '公交公司', 'b': '公交公司'}, ('a',)) == '公交公司 [a]'


def test_unknown_company_is_not_replaced_with_another_company():
    assert company_selection_name({'a': '八连交通集团'}, ('missing',)) == '未命名公司 [missing]'
