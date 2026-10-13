"""Exercise actual background rendering and queued GUI delivery."""
from PySide6.QtCore import QThreadPool
from PySide6.QtTest import QTest
from test_route_export_render import request


def settle(app,controller,timeout=10000):
    import time
    deadline=time.monotonic()+timeout/1000
    while controller.is_busy and time.monotonic()<deadline:
        app.processEvents();QTest.qWait(5)
    app.processEvents()
    assert not controller.is_busy


def test_latest_preview_supersedes_running_and_queued_generations(qt_application):
    from route_export_worker import RouteExportController
    controller=RouteExportController();received=[];errors=[]
    controller.ready.connect(lambda generation,result:received.append((generation,result)))
    controller.failed.connect(lambda generation,error:errors.append(error))
    controller.submit_preview(request(direction='up'),(768,512))
    controller.submit_preview(request(direction='whole'),(768,512))
    final=controller.submit_preview(request(direction='down'),(600,400))
    settle(qt_application,controller)
    assert not errors and [r[0] for r in received]==[final]
    assert received[0][1].width()==600
    controller.close()


def test_cancelled_export_does_not_publish_success_or_file(qt_application,tmp_path):
    from route_export_worker import RouteExportController
    controller=RouteExportController();received=[];cancelled=[]
    controller.ready.connect(lambda *args:received.append(args))
    controller.cancelled.connect(cancelled.append)
    generation=controller.submit_export(request(ppi=600),tmp_path/'cancelled.png')
    controller.cancel()
    settle(qt_application,controller)
    assert not received and generation in cancelled
    assert not (tmp_path/'cancelled.png').exists()
    controller.close()


def test_close_discards_late_results_and_refuses_new_jobs(qt_application):
    import pytest
    from route_export_worker import RouteExportController
    from route_export_model import ExportError
    controller=RouteExportController();received=[]
    controller.ready.connect(lambda *args:received.append(args))
    controller.submit_preview(request(),(1500,1000))
    controller.close()
    settle(qt_application,controller)
    assert not received
    with pytest.raises(ExportError):controller.submit_preview(request(),(600,400))


def test_ready_handler_can_start_a_following_job_without_false_idle(qt_application):
    from route_export_worker import RouteExportController
    controller=RouteExportController();results=[]
    def received(generation,image):
        results.append(image.width())
        if len(results)==1:controller.submit_preview(request(),(300,200))
    controller.ready.connect(received)
    controller.submit_preview(request(),(600,400))
    settle(qt_application,controller)
    assert results==[600,300]
    controller.close()
