"""Cooperative CPU budget for cancellable, Python-heavy background work."""
import time


class CooperativeCancellation:
    """Release the GIL periodically without changing cancellation semantics.

    Call only in background threads. The budget uses elapsed time rather than
    item counts, so small tasks and long waits do not acquire a per-item delay.
    """
    def __init__(self, cancelled=lambda: False, *, budget=.001, pause=.001):
        self.cancelled = cancelled
        self.budget, self.pause = budget, pause
        # Python 3.12's Windows monotonic clock uses 15.6 ms ticks. The
        # performance counter is also monotonic and can enforce a 1 ms budget.
        self.deadline = time.perf_counter() + budget

    def __call__(self):
        if self.cancelled():
            return True
        if time.perf_counter() >= self.deadline:
            time.sleep(self.pause)
            self.deadline = time.perf_counter() + self.budget
        return self.cancelled()
