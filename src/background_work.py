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
        self.deadline = time.monotonic() + budget

    def __call__(self):
        if self.cancelled():
            return True
        if time.monotonic() >= self.deadline:
            time.sleep(self.pause)
            self.deadline = time.monotonic() + self.budget
        return self.cancelled()
