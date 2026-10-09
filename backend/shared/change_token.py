import ctypes
import os

try:
    import msvcrt as _msvcrt
except ImportError:
    _msvcrt = None

POSIX = os.name == "posix"
WINDOWS = not POSIX

_FILE_BASIC_INFO_CLASS = 0


class _FileBasicInfo(ctypes.Structure):
    _fields_ = [("CreationTime", ctypes.c_longlong),
                ("LastAccessTime", ctypes.c_longlong),
                ("LastWriteTime", ctypes.c_longlong),
                ("ChangeTime", ctypes.c_longlong),
                ("FileAttributes", ctypes.c_uint32)]


def _stat_change_token(handle):
    try:
        return os.fstat(handle).st_ctime_ns
    except (AttributeError, OSError):
        return None


_windows_query = None


def _build_windows_query():
    global _windows_query
    if _windows_query is None:
        from ctypes import wintypes
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.GetFileInformationByHandleEx.argtypes = [
            wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        kernel32.GetFileInformationByHandleEx.restype = wintypes.BOOL
        _windows_query = kernel32.GetFileInformationByHandleEx
    return _windows_query


def _windows_change_token(handle):
    if not WINDOWS or _msvcrt is None:
        return None
    from ctypes import wintypes
    query = _build_windows_query()
    try:
        os_handle = wintypes.HANDLE(_msvcrt.get_osfhandle(handle))
    except (AttributeError, OSError, ValueError):
        return None
    info = _FileBasicInfo()
    if not query(os_handle, _FILE_BASIC_INFO_CLASS, ctypes.byref(info),
                 ctypes.sizeof(info)):
        return None
    return info.ChangeTime


def change_token(handle):
    if POSIX:
        return _stat_change_token(handle)
    return _windows_change_token(handle)