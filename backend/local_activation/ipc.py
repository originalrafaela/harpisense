"""Authenticated local handoff. No HTTP endpoint can create first-use sessions."""
import json
import os
import socket
import struct
import threading
from pathlib import Path

from .envelopes import LIMIT, parse


def _reply(adapter, user, raw):
    request = parse(raw)
    if request != {'version': 1, 'action': 'open-first-use'} or type(request.get('version')) is not int:
        raise ValueError('INVALID_IPC_REQUEST')
    return json.dumps(adapter._new_session(user, adapter._seal), separators=(',', ':')).encode('ascii')


def _read(sock, count):
    data = bytearray()
    while len(data) < count:
        part = sock.recv(count - len(data))
        if not part:
            raise ValueError('IPC_CLOSED')
        data.extend(part)
    return bytes(data)


class UnixHandoff:
    """Linux only. Private directory and socket; SO_PEERCRED gates every client."""
    def __init__(self, path, adapter, allowed_uids):
        self.path, self.adapter = Path(path), adapter
        self.allowed_uids = set(allowed_uids)
        self.socket = None
        self.thread = None
        self.stopping = threading.Event()

    def start(self):
        if os.name != 'posix' or not hasattr(socket, 'SO_PEERCRED'):
            raise RuntimeError('LINUX_PEER_CREDENTIALS_REQUIRED')
        parent = self.path.parent
        info = parent.stat()
        if parent.is_symlink() or info.st_mode & 0o077 or info.st_uid != os.geteuid():
            raise RuntimeError('PRIVATE_IPC_DIRECTORY_REQUIRED')
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.bind(str(self.path))  # Never unlink a preexisting endpoint.
            os.chmod(self.path, 0o600)
            sock.listen(4)
            sock.settimeout(0.5)
        except Exception:
            sock.close()
            raise
        self.socket = sock
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()
        return self

    def _serve(self):
        while not self.stopping.is_set():
            try:
                peer, _ = self.socket.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            with peer:
                peer.settimeout(3)
                try:
                    _, uid, _ = struct.unpack('3i', peer.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                    if uid not in self.allowed_uids:
                        continue
                    size = struct.unpack('!I', _read(peer, 4))[0]
                    if size > LIMIT:
                        continue
                    reply = _reply(self.adapter, 'uid:' + str(uid), _read(peer, size))
                    peer.sendall(struct.pack('!I', len(reply)) + reply)
                except Exception:
                    # Stable refusal, no exception/body logging.
                    continue

    def close(self):
        self.stopping.set()
        if self.socket:
            self.socket.close()
            if self.thread:
                self.thread.join(timeout=4)
            self.path.unlink(missing_ok=True)


class WindowsHandoff:
    """Named pipe with explicit SID ACL, local-only clients and impersonated SID check.

    Requires pywin32 in the Windows package. Installer SID is configured by trusted
    service composition, never taken from a request. Service creates endpoint first.
    """
    def __init__(self, name, adapter, service_sid, installer_sids):
        if not name.startswith('\\\\.\\pipe\\HarpiSense-'):
            raise ValueError('INVALID_PIPE_NAME')
        self.name, self.adapter = name, adapter
        self.sids = set(installer_sids)
        self.service_sid = service_sid
        self.stopping = threading.Event()
        self.thread = None
        self.handle = None

    def start(self):
        if os.name != 'nt':
            raise RuntimeError('WINDOWS_REQUIRED')
        import win32security
        import win32pipe
        import win32file
        import pywintypes
        # Convert first: no unvalidated text interpolation into SDDL.
        allowed = self.sids | {self.service_sid, 'S-1-5-18'}
        allowed = {win32security.ConvertSidToStringSid(win32security.ConvertStringSidToSid(s)) for s in allowed}
        sd = win32security.ConvertStringSecurityDescriptorToSecurityDescriptor(
            'D:P' + ''.join('(A;;GA;;;' + sid + ')' for sid in sorted(allowed)), 1)
        attributes = pywintypes.SECURITY_ATTRIBUTES()
        attributes.SECURITY_DESCRIPTOR = sd
        self.handle = win32pipe.CreateNamedPipe(self.name,
            win32pipe.PIPE_ACCESS_DUPLEX | 0x00080000,  # FILE_FLAG_FIRST_PIPE_INSTANCE
            win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_READMODE_MESSAGE |
            win32pipe.PIPE_WAIT | 0x8,  # PIPE_REJECT_REMOTE_CLIENTS
            1, LIMIT, LIMIT, 3000, attributes)
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()
        return self

    def _serve(self):
        import win32api
        import win32file
        import win32pipe
        import win32security
        while not self.stopping.is_set():
            try:
                try:
                    win32pipe.ConnectNamedPipe(self.handle, None)
                except Exception as exc:
                    if getattr(exc, 'winerror', None) != 535:  # ERROR_PIPE_CONNECTED
                        raise
                _, raw = win32file.ReadFile(self.handle, LIMIT + 1)
                win32pipe.ImpersonateNamedPipeClient(self.handle)
                token = None
                try:
                    token = win32security.OpenThreadToken(win32api.GetCurrentThread(),
                                                         win32security.TOKEN_QUERY, True)
                    sid = win32security.ConvertSidToStringSid(
                        win32security.GetTokenInformation(token, win32security.TokenUser)[0])
                finally:
                    if token:
                        token.Close()
                    win32security.RevertToSelf()
                if sid not in self.sids:
                    continue
                reply = _reply(self.adapter, 'sid:' + sid, raw)
                win32file.WriteFile(self.handle, reply)
            except Exception:
                pass
            finally:
                try:
                    win32pipe.DisconnectNamedPipe(self.handle)
                except Exception:
                    pass

    def close(self):
        self.stopping.set()
        if self.handle:
            import win32file
            win32file.CloseHandle(self.handle)
            if self.thread:
                self.thread.join(timeout=4)


def launch_first_use(handoff, *, chromium_executable):
    """Installer calls after authenticated IPC, in the interactive user's session.

    Packaged Playwright and Chromium are mandatory, with no download at runtime.
    Cookie travels through browser automation pipe, never URL, argv or profile disk.
    Blocks until user closes the isolated browser; caller may run a UI thread.
    """
    from playwright.sync_api import sync_playwright
    from urllib.parse import urlsplit
    origin = handoff['origin']
    url = urlsplit(origin)
    if url.hostname not in ('127.0.0.1', '::1') or url.scheme not in ('http', 'https'):
        raise ValueError('INVALID_NATIVE_ORIGIN')
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=str(chromium_executable), headless=False)
        try:
            context = browser.new_context()
            context.add_cookies([dict(name=handoff['cookie_name'], value=handoff['cookie_value'],
                domain=url.hostname, path=handoff['cookie_path'], httpOnly=True,
                secure=url.scheme == 'https', sameSite='Strict', expires=handoff['expires_at'])])
            page = context.new_page()
            page.goto(origin + '/')
            while context.pages:
                page.wait_for_timeout(250)
        finally:
            browser.close()


def request_unix_handoff(path, *, expected_server_uid):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as peer:
        peer.settimeout(5)
        peer.connect(str(path))
        _, uid, _ = struct.unpack('3i', peer.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
        if uid != expected_server_uid:
            raise RuntimeError('IPC_SERVER_IDENTITY_MISMATCH')
        raw = b'{"version":1,"action":"open-first-use"}'
        peer.sendall(struct.pack('!I', len(raw)) + raw)
        size = struct.unpack('!I', _read(peer, 4))[0]
        if size > LIMIT:
            raise RuntimeError('INVALID_IPC_RESPONSE')
        return parse(_read(peer, size))


def request_windows_handoff(name, *, expected_server_sid):
    import ctypes
    import win32api
    import win32file
    import win32security
    import win32pipe
    win32pipe.WaitNamedPipe(name, 5000)
    pipe = win32file.CreateFile(name, win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                               0, None, win32file.OPEN_EXISTING, 0, None)
    try:
        pid = ctypes.c_ulong()
        function = ctypes.WinDLL('kernel32', use_last_error=True).GetNamedPipeServerProcessId
        function.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
        function.restype = ctypes.c_int
        if not function(int(pipe), ctypes.byref(pid)):
            raise RuntimeError('IPC_SERVER_IDENTITY_UNAVAILABLE')
        process = win32api.OpenProcess(0x1000, False, pid.value)
        try:
            token = win32security.OpenProcessToken(process, win32security.TOKEN_QUERY)
            try:
                sid = win32security.ConvertSidToStringSid(
                    win32security.GetTokenInformation(token, win32security.TokenUser)[0])
            finally:
                token.Close()
        finally:
            process.Close()
        if sid != expected_server_sid:
            raise RuntimeError('IPC_SERVER_IDENTITY_MISMATCH')
        win32pipe.SetNamedPipeHandleState(pipe, win32pipe.PIPE_READMODE_MESSAGE, None, None)
        win32file.WriteFile(pipe, b'{"version":1,"action":"open-first-use"}')
        _, raw = win32file.ReadFile(pipe, LIMIT + 1)
        return parse(raw)
    finally:
        pipe.Close()
