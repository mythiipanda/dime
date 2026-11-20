import errno
import os
import time

try:
    import fcntl as _fcntl
except ImportError:
    _fcntl = None

try:
    import msvcrt as _msvcrt
except ImportError:
    _msvcrt = None

POSIX = os.name == "posix" and _fcntl is not None
WINDOWS = not POSIX

if not POSIX and _msvcrt is None:
    raise ImportError("shared.file_lock requires fcntl or msvcrt")

_REGION_BYTES = 1
POLL_INTERVAL_S = 0.05

if POSIX:
    _CONTENDED_ERRNOS = frozenset({errno.EAGAIN, errno.EWOULDBLOCK})
else:
    _CONTENDED_ERRNOS = frozenset({
        errno.EACCES,
        errno.EAGAIN,
        errno.EWOULDBLOCK,
        getattr(errno, "EDEADLK", errno.EACCES),
        getattr(errno, "EDEADLOCK", errno.EACCES),
    })


def is_contention(exc: BaseException) -> bool:
    if isinstance(exc, BlockingIOError):
        return True
    code = getattr(exc, "errno", None)
    return code is not None and code in _CONTENDED_ERRNOS


def _seek_region(handle) -> None:
    handle.flush()
    os.lseek(handle.fileno(), 0, os.SEEK_SET)


def _try_lock_windows(handle) -> bool:
    _seek_region(handle)
    try:
        _msvcrt.locking(handle.fileno(), _msvcrt.LK_NBLCK, _REGION_BYTES)
    except OSError as exc:
        if not is_contention(exc):
            raise
        return False
    return True


def try_lock_exclusive(handle) -> None:
    if POSIX:
        _fcntl.flock(handle.fileno(), _fcntl.LOCK_EX | _fcntl.LOCK_NB)
        return
    if _try_lock_windows(handle):
        return
    raise BlockingIOError(
        errno.EACCES, "lock is held by another process", getattr(handle, "name", None)
    )


def lock_exclusive(handle, timeout_s: float | None = None) -> None:
    if POSIX and timeout_s is None:
        _fcntl.flock(handle.fileno(), _fcntl.LOCK_EX)
        return
    deadline = None if timeout_s is None else time.monotonic() + timeout_s
    while True:
        try:
            try_lock_exclusive(handle)
            return
        except OSError as exc:
            if not is_contention(exc):
                raise
        if deadline is not None and time.monotonic() >= deadline:
            raise TimeoutError(f"exclusive lock timed out after {timeout_s}s")
        time.sleep(POLL_INTERVAL_S)


def unlock(handle) -> None:
    if POSIX:
        _fcntl.flock(handle.fileno(), _fcntl.LOCK_UN)
        return
    try:
        _seek_region(handle)
        _msvcrt.locking(handle.fileno(), _msvcrt.LK_UNLCK, _REGION_BYTES)
    except OSError as exc:
        if not is_contention(exc):
            raise
