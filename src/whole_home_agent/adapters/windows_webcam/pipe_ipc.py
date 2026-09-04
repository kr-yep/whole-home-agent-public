"""Windows Named Pipe IPC server and client with AppContainer DACL and peer verification.

Specification: WHA-WIN-CAPTURE-ROI-001 (Section 15, 19, 23)
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import io
import os
import sys
import time
from typing import BinaryIO, Optional

_IS_WINDOWS = sys.platform == "win32"

# Windows Named Pipe Constants
PIPE_ACCESS_INBOUND = 0x00000001
PIPE_ACCESS_OUTBOUND = 0x00000002
PIPE_ACCESS_DUPLEX = 0x00000003
FILE_FLAG_FIRST_PIPE_INSTANCE = 0x00080000

PIPE_TYPE_BYTE = 0x00000000
PIPE_READMODE_BYTE = 0x00000000
PIPE_WAIT = 0x00000000

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
OPEN_EXISTING = 3
FILE_ATTRIBUTE_NORMAL = 0x80
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

def is_valid_handle(h: Optional[int]) -> bool:
    return h is not None and h != 0 and h != INVALID_HANDLE_VALUE and h != -1

ERROR_PIPE_CONNECTED = 535
ERROR_PIPE_BUSY = 231
ERROR_NO_DATA = 232
ERROR_BROKEN_PIPE = 109
ERROR_ACCESS_DENIED = 5

SDDL_REVISION_1 = 1

# Protected DACL:
# - Deny Anonymous (AN)
# - Deny Network (NU)
# - Allow Owner (OW) Read/Write
# - Allow All Application Packages / AppContainer (AC) Read/Write
DEFAULT_PIPE_SDDL = "D:P(D;;GA;;;AN)(D;;GA;;;NU)(A;;GRGW;;;OW)(A;;GRGW;;;AC)"


if _IS_WINDOWS:
    _kernel32 = ctypes.windll.kernel32
    _advapi32 = ctypes.windll.advapi32

    class SECURITY_ATTRIBUTES(ctypes.Structure):
        _fields_ = [
            ("nLength", wintypes.DWORD),
            ("lpSecurityDescriptor", wintypes.LPVOID),
            ("bInheritHandle", wintypes.BOOL),
        ]

    _CreateNamedPipeW = _kernel32.CreateNamedPipeW
    _CreateNamedPipeW.restype = wintypes.HANDLE
    _CreateNamedPipeW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(SECURITY_ATTRIBUTES),
    ]

    _ConnectNamedPipe = _kernel32.ConnectNamedPipe
    _ConnectNamedPipe.restype = wintypes.BOOL
    _ConnectNamedPipe.argtypes = [wintypes.HANDLE, wintypes.LPVOID]

    _DisconnectNamedPipe = _kernel32.DisconnectNamedPipe
    _DisconnectNamedPipe.restype = wintypes.BOOL
    _DisconnectNamedPipe.argtypes = [wintypes.HANDLE]

    _CreateFileW = _kernel32.CreateFileW
    _CreateFileW.restype = wintypes.HANDLE
    _CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]

    _ReadFile = _kernel32.ReadFile
    _ReadFile.restype = wintypes.BOOL
    _ReadFile.argtypes = [
        wintypes.HANDLE,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        wintypes.LPVOID,
    ]

    _WriteFile = _kernel32.WriteFile
    _WriteFile.restype = wintypes.BOOL
    _WriteFile.argtypes = [
        wintypes.HANDLE,
        wintypes.LPCVOID,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        wintypes.LPVOID,
    ]

    _CloseHandle = _kernel32.CloseHandle
    _CloseHandle.restype = wintypes.BOOL
    _CloseHandle.argtypes = [wintypes.HANDLE]

    _GetNamedPipeClientProcessId = _kernel32.GetNamedPipeClientProcessId
    _GetNamedPipeClientProcessId.restype = wintypes.BOOL
    _GetNamedPipeClientProcessId.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.ULONG)]

    _ConvertStringSecurityDescriptorToSecurityDescriptorW = (
        _advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW
    )
    _ConvertStringSecurityDescriptorToSecurityDescriptorW.restype = wintypes.BOOL
    _ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.LPVOID),
        ctypes.POINTER(wintypes.ULONG),
    ]

    _LocalFree = _kernel32.LocalFree

    _OpenProcess = _kernel32.OpenProcess
    _OpenProcess.restype = wintypes.HANDLE
    _OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]

    _OpenProcessToken = _advapi32.OpenProcessToken
    _OpenProcessToken.restype = wintypes.BOOL
    _OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]

    _GetTokenInformation = _advapi32.GetTokenInformation
    _GetTokenInformation.restype = wintypes.BOOL
    _GetTokenInformation.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]


class PipeStreamReader(io.RawIOBase):
    """File-like wrapper over a Win32 Named Pipe read handle."""

    def __init__(self, handle: int) -> None:
        self._handle = handle
        self._closed = False

    def readable(self) -> bool:
        return True

    def readinto(self, b: bytearray | memoryview) -> int:
        if self._closed or not is_valid_handle(self._handle):
            return 0
        buf_len = len(b)
        if buf_len == 0:
            return 0

        c_buf = (ctypes.c_char * buf_len).from_buffer(b)
        bytes_read = wintypes.DWORD(0)

        success = _ReadFile(
            self._handle,
            c_buf,
            buf_len,
            ctypes.byref(bytes_read),
            None,
        )
        if not success:
            err = _kernel32.GetLastError()
            if err in (ERROR_BROKEN_PIPE, ERROR_NO_DATA):
                return 0
            raise OSError(f"ReadFile over named pipe failed with Windows error: {err}")

        return bytes_read.value

    def close(self) -> None:
        if not self._closed:
            self._closed = True


class NamedPipeServer:
    """Named pipe server with restrictive DACL and single-instance limit (Section 15)."""

    def __init__(
        self,
        session_nonce: str,
        *,
        sddl: str = DEFAULT_PIPE_SDDL,
        max_instances: int = 1,
    ) -> None:
        if len(session_nonce) != 32:
            raise ValueError("session_nonce must be exactly 32 lowercase hexadecimal characters")
        self.session_nonce = session_nonce
        self.pipe_name = rf"\\.\pipe\LOCAL\wha.capture.v1.{session_nonce}"
        self.max_instances = max_instances
        self.sddl = sddl
        self._handle = INVALID_HANDLE_VALUE
        self._sd_ptr = None
        self._connected = False

        if _IS_WINDOWS:
            self._init_windows_pipe()

    def _init_windows_pipe(self) -> None:
        sa = SECURITY_ATTRIBUTES()
        sa.nLength = ctypes.sizeof(SECURITY_ATTRIBUTES)
        sa.bInheritHandle = False

        p_sd = wintypes.LPVOID()
        if self.sddl:
            ok = _ConvertStringSecurityDescriptorToSecurityDescriptorW(
                self.sddl,
                SDDL_REVISION_1,
                ctypes.byref(p_sd),
                None,
            )
            if not ok:
                raise OSError(f"ConvertStringSecurityDescriptor failed with error {_kernel32.GetLastError()}")
            self._sd_ptr = p_sd
            sa.lpSecurityDescriptor = p_sd

        open_mode = PIPE_ACCESS_DUPLEX | FILE_FLAG_FIRST_PIPE_INSTANCE
        pipe_mode = PIPE_TYPE_BYTE | PIPE_READMODE_BYTE | PIPE_WAIT

        self._handle = _CreateNamedPipeW(
            self.pipe_name,
            open_mode,
            pipe_mode,
            self.max_instances,
            65536,  # Out buffer
            65536,  # In buffer
            5000,   # Default timeout (5000 ms = 5 s)
            ctypes.byref(sa) if self.sddl else None,
        )

        if not is_valid_handle(self._handle):
            err = _kernel32.GetLastError()
            raise OSError(f"CreateNamedPipeW failed for {self.pipe_name} with error {err}")

    def wait_for_connection(self) -> None:
        """Blocks until client connects to pipe or error occurs."""
        if not _IS_WINDOWS:
            self._connected = True
            return

        ok = _ConnectNamedPipe(self._handle, None)
        if not ok:
            err = _kernel32.GetLastError()
            if err != ERROR_PIPE_CONNECTED:
                raise OSError(f"ConnectNamedPipe failed with Windows error: {err}")
        self._connected = True

    def get_client_pid(self) -> int:
        """Returns the process ID of the connected client."""
        if not _IS_WINDOWS:
            return os.getpid()
        pid = wintypes.ULONG(0)
        if not _GetNamedPipeClientProcessId(self._handle, ctypes.byref(pid)):
            err = _kernel32.GetLastError()
            raise OSError(f"GetNamedPipeClientProcessId failed with error {err}")
        return int(pid.value)

    def disconnect_client(self) -> None:
        """Disconnects current connected client without destroying pipe."""
        if _IS_WINDOWS and is_valid_handle(self._handle):
            _DisconnectNamedPipe(self._handle)
        self._connected = False

    def verify_client_identity(
        self,
        *,
        expected_pid: Optional[int] = None,
        require_app_container: bool = False,
    ) -> bool:
        """Verifies peer process ID and token / AppContainer identity (Section 15)."""
        pid = self.get_client_pid()
        if expected_pid is not None and pid != expected_pid:
            return False
        if not _IS_WINDOWS:
            return True

        if not require_app_container:
            return True

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        TOKEN_QUERY = 0x0008
        TokenIsAppContainer = 29

        h_proc = _OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not is_valid_handle(h_proc):
            return False

        h_token = wintypes.HANDLE()
        try:
            if not _OpenProcessToken(h_proc, TOKEN_QUERY, ctypes.byref(h_token)):
                return False
            try:
                is_app_container = wintypes.DWORD(0)
                ret_len = wintypes.DWORD(0)
                ok = _GetTokenInformation(
                    h_token,
                    TokenIsAppContainer,
                    ctypes.byref(is_app_container),
                    ctypes.sizeof(is_app_container),
                    ctypes.byref(ret_len),
                )
                if not ok or is_app_container.value == 0:
                    return False
            finally:
                _CloseHandle(h_token)
        finally:
            _CloseHandle(h_proc)

        return True

    def as_stream(self) -> BinaryIO:
        """Returns a binary stream wrapping the pipe for decoder consumption."""
        if not self._connected:
            raise RuntimeError("Cannot open stream before pipe is connected")
        raw = PipeStreamReader(self._handle)
        return io.BufferedReader(raw)

    def close(self) -> None:
        """Closes pipe handle and releases security descriptor."""
        if _IS_WINDOWS:
            if is_valid_handle(self._handle):
                _DisconnectNamedPipe(self._handle)
                _CloseHandle(self._handle)
                self._handle = INVALID_HANDLE_VALUE
            if self._sd_ptr:
                _LocalFree(self._sd_ptr)
                self._sd_ptr = None
        self._connected = False


class NamedPipeClient:
    """Named pipe client for CaptureHost to stream frames to SemanticHost."""

    def __init__(self, session_nonce: str) -> None:
        self.session_nonce = session_nonce
        self.pipe_name = rf"\\.\pipe\LOCAL\wha.capture.v1.{session_nonce}"
        self._handle = INVALID_HANDLE_VALUE

    def connect(self, timeout_s: float = 5.0) -> None:
        """Connects to the named pipe within timeout."""
        if not _IS_WINDOWS:
            return

        t_end = time.monotonic() + timeout_s
        while time.monotonic() < t_end:
            self._handle = _CreateFileW(
                self.pipe_name,
                GENERIC_READ | GENERIC_WRITE,
                0,
                None,
                OPEN_EXISTING,
                FILE_ATTRIBUTE_NORMAL,
                0,
            )
            if is_valid_handle(self._handle):
                return

            err = _kernel32.GetLastError()
            if err == ERROR_PIPE_BUSY:
                # Wait for pipe instance
                time.sleep(0.05)
            elif err == ERROR_ACCESS_DENIED:
                raise PermissionError(f"Access denied connecting to {self.pipe_name}")
            else:
                time.sleep(0.05)

        raise TimeoutError(f"Timed out connecting to {self.pipe_name} after {timeout_s}s")

    def write(self, data: bytes | memoryview) -> int:
        """Writes byte payload to pipe."""
        if not _IS_WINDOWS:
            return len(data)

        if not is_valid_handle(self._handle):
            raise OSError("Cannot write to closed pipe client")

        total_written = 0
        to_write = bytes(data)
        bytes_written = wintypes.DWORD(0)

        ok = _WriteFile(
            self._handle,
            to_write,
            len(to_write),
            ctypes.byref(bytes_written),
            None,
        )
        if not ok:
            err = _kernel32.GetLastError()
            raise OSError(f"WriteFile over pipe failed with Windows error: {err}")

        return bytes_written.value

    def close(self) -> None:
        """Closes pipe client handle."""
        if _IS_WINDOWS:
            if is_valid_handle(self._handle):
                _CloseHandle(self._handle)
                self._handle = INVALID_HANDLE_VALUE
