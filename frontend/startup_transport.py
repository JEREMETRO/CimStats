"""Own the icon-only helper process without importing Qt or business modules.

Loopback IPC also works with PyInstaller's windowed stdin/stdout=None. Threads
handle byte messages only; all widgets stay in their process's main Qt thread.
"""
from __future__ import annotations

import json
import secrets
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path


class SplashProcess:
    def __init__(self):
        self.token = secrets.token_hex(32)
        self.port = None
        self.process = None
        self.exit_code = None
        self.listener = None
        self.peer = None
        self.events = []
        self.connected = threading.Event()
        self.first_paint = threading.Event()
        self.stopped = threading.Event()
        self._thread = None
        self._lock = threading.Lock()

    def listen(self):
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener.bind(('127.0.0.1', 0))
        self.port = self.listener.getsockname()[1]
        self.listener.listen(2)
        self.listener.settimeout(.25)
        self._thread = threading.Thread(target=self._receive, daemon=True)
        self._thread.start()

    def start(self, launcher: Path, symbol: Path):
        self.listen()
        command = [sys.executable]
        if not getattr(sys, 'frozen', False):
            command.append(str(launcher))
        command.extend(['--startup-splash', str(self.port), self.token, str(symbol)])
        options = {'stdin': subprocess.DEVNULL, 'stdout': subprocess.DEVNULL,
                   'stderr': subprocess.DEVNULL, 'close_fds': True}
        if sys.platform == 'win32':
            options['creationflags'] = subprocess.CREATE_NO_WINDOW
        try:
            self.process = subprocess.Popen(command, **options)
        except BaseException:
            self.close()
            raise

    def wait_for_first_paint(self, timeout=5.0):
        """A real painted-frame handshake, bounded if the helper cannot start."""
        deadline = time.monotonic() + timeout
        while not self.first_paint.is_set():
            if self.process is not None and self.process.poll() is not None:
                return False
            remaining = deadline - time.monotonic()
            if remaining <= 0 or self.stopped.is_set():
                return False
            self.first_paint.wait(min(.05, remaining))
        return True

    def _receive(self):
        while not self.stopped.is_set():
            try:
                peer, _address = self.listener.accept()
            except socket.timeout:
                continue
            except (OSError, AttributeError):
                return
            peer.settimeout(2)
            stream = peer.makefile('rb')
            try:
                if stream.readline(256).decode('ascii').strip() != self.token:
                    continue
                with self._lock:
                    if self.stopped.is_set():
                        return
                    self.peer = peer
                self.connected.set()
                peer.settimeout(None)
                while not self.stopped.is_set():
                    raw = stream.readline(4096)
                    if not raw:
                        return
                    event = json.loads(raw)
                    self.events.append(event)
                    if event.get('event') == 'splash_first_paint':
                        self.first_paint.set()
                return
            except (OSError, ValueError, UnicodeError):
                if self.connected.is_set():
                    return
            finally:
                stream.close()
                peer.close()

    def dismiss(self):
        """Nonblocking on first main-window paint; no added display duration."""
        self.stopped.set()
        with self._lock:
            if self.peer is not None:
                try:
                    self.peer.sendall(b'close\n')
                    self.peer.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                self.peer.close()
                self.peer = None
        if self.listener is not None:
            self.listener.close()
            self.listener = None

    def close(self):
        """Also reap the child on success, exception, or app shutdown."""
        self.dismiss()
        if self.process is not None:
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                try:
                    self.process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=1)
            self.exit_code = self.process.returncode
            self.process = None
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=.5)
