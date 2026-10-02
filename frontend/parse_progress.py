"""Actual parser phase/count progress; elapsed time and RSS never advance it."""

# These are fixed UI phase budgets, not fractions of elapsed time or object count.
PHASES = {
    'payload': (0, 8), 'deserialize': (8, 20), 'lines': (20, 50),
    'history': (50, 65), 'csv': (65, 70), 'line_workbook': (70, 82),
    'company_workbook': (82, 90), 'validation': (90, 96), 'dashboard': (96, 99),
}


class ParseProgressEstimator:
    """Compatibility name retained for MainWindow; the engine has no prediction."""
    actual_progress = True
    def __init__(self, save_bytes=0, model=None):
        self.last = 0
        self.phase = 'payload'
        self.done = 0
        self.total = 0
        self.supported = True  # Sizes/runtime modes do not disable actual events.

    def observe(self, elapsed, details):
        if not isinstance(details, dict):
            return
        phase = details.get('phase')
        if phase not in PHASES:
            return
        if details.get('event') == 'phase':
            if details.get('status') not in ('start', 'end'):
                return
            details = dict(details, done=int(details['status'] == 'end'), total=1)
        elif details.get('event') != 'progress':
            return
        done, total = details.get('done'), details.get('total')
        if type(done) is not int or type(total) is not int or total <= 0 or done < 0 or done > total:
            return
        start, end = PHASES[phase]
        if start < PHASES[self.phase][0]:
            return
        if phase == self.phase and (done / total) < (self.done / self.total if self.total else 0):
            return
        self.phase, self.done, self.total = phase, done, total
        self.last = max(self.last, min(99, int(start + (end - start) * done / total)))

    def update(self, elapsed, rss_bytes, stage):
        # Legacy stage signals represent actual completed preceding stages.
        # Parser 100 is mapped to 99 by MainWindow, so only a UI-ready caller
        # can request 100 here.
        if stage == 100:
            return self.finish()
        floors = {70: 70, 82: 82, 92: 90, 95: 96, 99: 96}
        self.last = max(self.last, floors.get(stage, 0))
        return self.last

    def finish(self):
        self.last = 100
        return self.last
