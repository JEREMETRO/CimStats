"""Small display fingerprints: never compare raw history payloads on the UI thread."""

def result_key(result):
    if result is None:
        return None
    def series_key(series):
        return tuple((owner, tuple((b.start,b.end,b.value,b.complete,b.partial_period,
                                   b.observed,b.numerator,b.denominator,b.effective_hours)
                                  for b in buckets)) for owner,buckets in series.items())
    return (result.query,result.metric,result.current_window,result.comparison_window,
            series_key(result.series),series_key(result.comparison))

def descriptor_key(descriptor, snapshot):
    return (descriptor.key,descriptor.title,descriptor.company_id,descriptor.allowed_modes,
            descriptor.reason,result_key(descriptor.result),result_key(descriptor.bar_result),
            tuple(snapshot.companies.items()),snapshot.options.mode,snapshot.options.comparison_label)
