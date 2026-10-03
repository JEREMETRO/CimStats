"""Company identity wording shared by snapshots and chart summaries."""


def company_selection_name(companies, selected):
    names = dict(companies)
    identities = tuple(dict.fromkeys(selected))
    labels = []
    for identity in identities:
        name = names.get(identity)
        if not name:
            label = f'未命名公司 [{identity}]'
        elif list(names.values()).count(name) > 1:
            label = f'{name} [{identity}]'
        else:
            label = name
        labels.append(label)
    return ('、'.join(labels) + ('合计' if len(labels) > 1 else '')) if labels else '未选择公司'
