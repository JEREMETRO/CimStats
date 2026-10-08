"""Opt-in normal-open timing; never imported by normal startup."""
import hashlib
import json
import sys
import time

def profile_loading(win, args):
    """Measure the normal cold-open path inside the exact delivered process."""
    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    from package_smoke import _resize_for_workarea, _window_workarea_evidence
    _resize_for_workarea(win, 1440, 960)
    win.set_sidebar_collapsed(True)
    assert abs(win.devicePixelRatioF()-args.expected_dpr) < .001
    page, canvas = win.map_page, win.map_page.canvas
    digest = hashlib.sha256(args.save.read_bytes()).hexdigest()
    import psutil
    process = psutil.Process()
    peak_rss, child_count, cpu_samples = [0], [0], {}
    def resources():
        children = process.children(recursive=True)
        child_count[0] = max(child_count[0], len(children))
        rss = 0
        for item in (process, *children):
            try:
                rss += item.memory_info().rss
                cpu = item.cpu_times()
                cpu_samples[item.pid] = cpu.user+cpu.system
            except psutil.NoSuchProcess:
                pass
        peak_rss[0] = max(peak_rss[0], rss)
    ticks, gaps, marks, inputs, errors = [], [], {}, [], []
    started = time.monotonic()
    def tick():
        now = time.monotonic()-started
        if ticks and now-ticks[-1] > .1:
            gaps.append({'start':ticks[-1], 'end':now, 'seconds':now-ticks[-1]})
        ticks.append(now)
    def navigate(reason):
        before = time.monotonic()
        win.navigate(1)
        inputs.append({'requested':reason, 'processed':before-started,
                       'seconds':time.monotonic()-before})
    def settle():
        loop = QEventLoop(); QTimer.singleShot(20, loop.quit); loop.exec()
    def ready():
        return (win.worker is None and bool(win.data) and not win._awaiting_dashboards
                and page.result is not None and canvas._frame_job is None
                and canvas._frame_key == canvas._render_key()
                and canvas._frame_view == (*canvas.center, canvas.zoom))
    page.ready.connect(lambda: marks.setdefault('map_snapshot', time.monotonic()-started))
    statistics=[]
    page.statistics_preparation_started.connect(lambda: marks.setdefault('map_statistics_start',time.monotonic()-started))
    def statistics_ready(timing):
        marks.setdefault('map_statistics_ready',time.monotonic()-started)
        statistics.append(timing)
    page.statistics_preparation_finished.connect(statistics_ready)
    canvas.frame_ready.connect(lambda: marks.setdefault('first_frame', time.monotonic()-started)
                               if page.result is not None else None)
    page.failed.connect(errors.append)
    timer = QTimer(); timer.timeout.connect(tick); timer.start(10)
    monitor = QTimer(); monitor.timeout.connect(resources); monitor.start(250)
    early = QTimer(); early.setSingleShot(True); early.timeout.connect(lambda: navigate(8))
    win.start_parse(args.save)
    win.worker.failed.connect(errors.append)
    early.start(8000)
    while not ready() and not errors and time.monotonic()-started < 360:
        settle()
        if win.data and not win._awaiting_dashboards and 'stats_ready' not in marks:
            marks['stats_ready'] = time.monotonic()-started
            navigate('stats_ready')
    timer.stop(); early.stop(); monitor.stop(); resources()
    assert not errors and ready(), errors
    marks['all_ready'] = time.monotonic()-started
    prepared = time.monotonic(); win.navigate(0); win.navigate(1); app.processEvents()
    marks['prepared_menu_open'] = time.monotonic()-prepared
    unchanged = hashlib.sha256(args.save.read_bytes()).hexdigest() == digest
    cache_created = (args.output/'parsed-jobs/map-cache').exists()
    assert unchanged and not cache_created
    assert win.grab().save(str(args.output/'normal-open-map.png'))
    record = {'marks':marks, 'gaps':gaps, 'inputs':inputs,'map_statistics_preparation':statistics,
              'max_gap':max((b-a for a,b in zip(ticks,ticks[1:])), default=0),
              'save_sha256':digest, 'save_unchanged':unchanged,
              'persistent_cache_created':cache_created,
              'frozen':bool(getattr(sys,'frozen',False)), 'executable':sys.executable,
              'platform':app.platformName(), 'dpr':win.devicePixelRatioF(),
              'size':[win.width(),win.height()], 'schema':page._snapshot.schema_version,
              'workarea':_window_workarea_evidence(win),
              'process_id':process.pid, 'peak_rss_mib':peak_rss[0]/2**20,
              'max_child_processes':child_count[0], 'sampled_cpu_seconds':sum(cpu_samples.values()),
              'child_processes_after_ready':[child.pid for child in process.children(recursive=True)]}
    (args.output/'loading-metrics.json').write_text(json.dumps(record,indent=2), encoding='utf-8')
