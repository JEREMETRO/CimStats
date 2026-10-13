"""Latest-only, bounded background work with cancellation and detached lifetimes."""
from __future__ import annotations
from dataclasses import dataclass
import threading

from PySide6.QtCore import QObject,QRunnable,QThreadPool,Signal,Slot,Qt
from background_work import CooperativeCancellation
from route_export_model import ExportError,ExportCancelled
from route_export_render import preview,render_export


class _Token:
    def __init__(self):
        self.event=threading.Event();self.lock=threading.Lock()
        self.check=CooperativeCancellation(self.event.is_set)

    def __call__(self):return self.check()

    def cancel(self):
        with self.lock:self.event.set()

    def commit(self,action):
        # A cancellation before the atomic rename always wins.
        with self.lock:
            if self.event.is_set():raise ExportCancelled('已取消导出')
            action()


class _Signals(QObject):
    finished=Signal(int,object,object)


@dataclass(frozen=True)
class _Job:
    generation: int
    request: object
    destination: object = None
    target_size: tuple = (900,600)


class _Task(QRunnable):
    def __init__(self,job,token):
        super().__init__();self.job=job;self.token=token;self.signals=_Signals()

    def run(self):
        result=error=None
        try:
            result=(preview(self.job.request,self.job.target_size,self.token) if self.job.destination is None
                else render_export(self.job.request,self.job.destination,self.token))
        except Exception as exc:error=exc
        self.signals.finished.emit(self.job.generation,result,error)


class RouteExportController(QObject):
    """Use on the GUI thread; one active job and one replaceable pending job."""
    ready=Signal(int,object)
    failed=Signal(int,str)
    cancelled=Signal(int)
    busyChanged=Signal(bool)

    def __init__(self,parent=None,*,pool=None):
        super().__init__(parent)
        self._pool=pool or QThreadPool.globalInstance()
        self._generation=0;self._closed=False;self._active=None;self._pending=None
        self._token=None;self._busy=False
        # Tasks own signals independently; receiver destruction disconnects them.
        self._lifetime={'token':None}
        lifetime=self._lifetime
        self.destroyed.connect(lambda *_:lifetime['token'].cancel() if lifetime['token'] is not None else None)

    @property
    def is_busy(self):return self._busy

    @property
    def generation(self):return self._generation

    def _busy_state(self,state):
        if self._busy!=state:self._busy=state;self.busyChanged.emit(state)

    def submit_preview(self,request,target_size=(900,600)):
        size=(target_size.width(),target_size.height()) if hasattr(target_size,'width') else tuple(target_size)
        return self._submit(request,None,size)

    def submit_export(self,request,destination):return self._submit(request,destination,(900,600))

    def _submit(self,request,destination,size):
        if self._closed:raise ExportError('导出窗口已关闭')
        self._generation+=1
        job=_Job(self._generation,request,destination,size)
        self._busy_state(True)
        if self._active is not None:
            self._token.cancel();self._pending=job
        else:self._start(job)
        return job.generation

    def _start(self,job):
        token=_Token();task=_Task(job,token)
        self._active=task;self._token=token
        self._lifetime['token']=token
        task.signals.finished.connect(self._finished,Qt.ConnectionType.QueuedConnection)
        self._pool.start(task)

    @Slot(int,object,object)
    def _finished(self,generation,result,error):
        self._active=None;self._token=None;self._lifetime['token']=None
        pending=self._pending;self._pending=None
        if pending is not None and not self._closed:self._start(pending)
        else:self._busy_state(False)
        if not self._closed and generation==self._generation:
            if isinstance(error,ExportCancelled):self.cancelled.emit(generation)
            elif error is not None:self.failed.emit(generation,str(error))
            else:self.ready.emit(generation,result)

    def cancel(self):
        generation=self._generation;self._generation+=1;self._pending=None
        if self._token is not None:self._token.cancel()
        if not self._closed:self.cancelled.emit(generation)
        if self._active is None:self._busy_state(False)

    def close(self):
        self._closed=True;self.cancel()
