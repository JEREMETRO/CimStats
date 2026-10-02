"""Small, throttled stdout protocol carrying only actual parser milestones."""
import json
import time

PREFIX = 'CIM2_PROGRESS '


class ProgressReporter:
    def __init__(self, emit=None, clock=time.monotonic):
        self.emit = emit or (lambda details: print(PREFIX + json.dumps(details, ensure_ascii=False), flush=True))
        self.clock = clock
        self.last_phase = None
        self.last_time = float('-inf')

    def start(self, phase):
        self.emit(dict(event='phase', phase=phase, status='start'))

    def finish(self, phase):
        self.emit(dict(event='phase', phase=phase, status='end'))

    def progress(self, phase, done, total):
        if type(done) is not int or type(total) is not int or not 0 <= done <= total:
            raise ValueError('Invalid actual progress counter')
        if total == 0:
            self.finish(phase)  # Known empty phase, not an invented denominator.
            return
        now = self.clock()
        if phase != self.last_phase or done == total or now - self.last_time >= .1:
            self.emit(dict(event='progress', phase=phase, done=done, total=total))
            self.last_phase, self.last_time = phase, now
