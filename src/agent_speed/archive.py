from contextlib import contextmanager
import os
from pathlib import Path
import re
import stat


MAX_ARCHIVE_BYTES = 4 * 1024 * 1024


def _check_id(raw_id: str) -> None:
    if not re.fullmatch(r"[0-9a-f]{64}", raw_id):
        raise ValueError("invalid raw result id")


def _check_posix_file(fd: int) -> None:
    info = os.fstat(fd)
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_uid != os.geteuid()
        or info.st_mode & 0o077
        or info.st_nlink != 1
    ):
        raise ValueError("unsafe archive file")


@contextmanager
def _posix_directory(root: Path, create: bool):
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    fd = os.open(root.anchor, flags)
    try:
        for part in root.parts[1:]:
            try:
                child = os.open(part, flags, dir_fd=fd)
            except FileNotFoundError:
                if not create:
                    raise
                try:
                    os.mkdir(part, 0o700, dir_fd=fd)
                except FileExistsError:
                    pass  # A concurrent creator still has to pass the no-follow open.
                child = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = child
        info = os.fstat(fd)
        if info.st_uid != os.geteuid() or info.st_mode & 0o077:
            raise ValueError("archive directory must be owned by the current user and private")
        yield fd
    finally:
        os.close(fd)


@contextmanager
def _posix_file(root: Path, raw_id: str, create: bool):
    with _posix_directory(root, create) as directory:
        common = os.O_NOFOLLOW | os.O_NONBLOCK
        new = False
        if create:
            try:
                fd = os.open(raw_id, os.O_RDWR | os.O_CREAT | os.O_EXCL | common, 0o600, dir_fd=directory)
                new = True
            except FileExistsError:
                fd = os.open(raw_id, os.O_RDONLY | common, dir_fd=directory)
        else:
            fd = os.open(raw_id, os.O_RDONLY | common, dir_fd=directory)
        try:
            _check_posix_file(fd)
            yield fd, new
        finally:
            os.close(fd)


if os.name == "nt":
    import ctypes
    from ctypes import wintypes
    import msvcrt

    _kernel = ctypes.WinDLL("kernel32", use_last_error=True)

    class _FileInfo(ctypes.Structure):
        _fields_ = [
            ("attributes", wintypes.DWORD),
            ("created", wintypes.FILETIME),
            ("accessed", wintypes.FILETIME),
            ("written", wintypes.FILETIME),
            ("volume", wintypes.DWORD),
            ("size_high", wintypes.DWORD),
            ("size_low", wintypes.DWORD),
            ("links", wintypes.DWORD),
            ("index_high", wintypes.DWORD),
            ("index_low", wintypes.DWORD),
        ]

    _kernel.CreateFileW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
        wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
    ]
    _kernel.CreateFileW.restype = wintypes.HANDLE
    _kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    _kernel.CloseHandle.restype = wintypes.BOOL
    _kernel.GetFileInformationByHandle.argtypes = [wintypes.HANDLE, ctypes.POINTER(_FileInfo)]
    _kernel.GetFileInformationByHandle.restype = wintypes.BOOL
    _kernel.GetFileType.argtypes = [wintypes.HANDLE]
    _kernel.GetFileType.restype = wintypes.DWORD
    _kernel.GetFinalPathNameByHandleW.argtypes = [
        wintypes.HANDLE, wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD,
    ]
    _kernel.GetFinalPathNameByHandleW.restype = wintypes.DWORD

    def _close_handle(handle) -> None:
        if not _kernel.CloseHandle(handle):
            raise ctypes.WinError(ctypes.get_last_error())

    def _open_handle(path: str, directory: bool = False, create: bool = False):
        # Deny write/delete sharing so validated objects cannot be repointed in place.
        access = 0xC0000000 if create else 0x80000000
        flags = 0x00200000 | (0x02000000 if directory else 0)
        handle = _kernel.CreateFileW(path, access, 1, None, 1 if create else 3, flags, None)
        if handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            info = _FileInfo()
            if not _kernel.GetFileInformationByHandle(handle, ctypes.byref(info)):
                raise ctypes.WinError(ctypes.get_last_error())
            if (
                _kernel.GetFileType(handle) != 1
                or info.attributes & 0x400
                or bool(info.attributes & 0x10) != directory
                or (not directory and info.links != 1)
            ):
                raise ValueError("archive path is a reparse point or unsafe file type")
            return handle
        except (OSError, ValueError):
            _close_handle(handle)
            raise

    def _volume_root(handle) -> str:
        buffer = ctypes.create_unicode_buffer(32768)
        length = _kernel.GetFinalPathNameByHandleW(handle, buffer, len(buffer), 1)
        if not length:
            raise ctypes.WinError(ctypes.get_last_error())
        if length >= len(buffer) or not re.fullmatch(r"\\\\\?\\Volume\{[0-9a-fA-F-]+\}\\", buffer.value):
            raise ValueError("archive requires a local volume, not a drive alias")
        return buffer.value

    @contextmanager
    def _windows_directory(root: Path, create: bool):
        if not re.fullmatch(r"[a-zA-Z]:", root.drive):
            raise ValueError("archive requires a local drive path")
        handles = []
        try:
            handle = _open_handle(root.anchor, directory=True)
            handles.append(handle)
            path = _volume_root(handle)
            for part in root.parts[1:]:
                if ":" in part or part.endswith((" ", ".")):
                    raise ValueError("ambiguous archive path")
                path = path.rstrip("\\") + "\\" + part
                try:
                    handle = _open_handle(path, directory=True)
                except FileNotFoundError:
                    if not create:
                        raise
                    try:
                        os.mkdir(path, 0o700)
                    except FileExistsError:
                        pass
                    handle = _open_handle(path, directory=True)
                handles.append(handle)
            yield path
        finally:
            for handle in reversed(handles):
                _close_handle(handle)

    @contextmanager
    def _windows_file(root: Path, raw_id: str, create: bool):
        with _windows_directory(root, create) as directory:
            path = directory.rstrip("\\") + "\\" + raw_id
            new = False
            if create:
                try:
                    handle = _open_handle(path, create=True)
                    new = True
                except FileExistsError:
                    handle = _open_handle(path)
            else:
                handle = _open_handle(path)
            try:
                fd = msvcrt.open_osfhandle(handle, os.O_BINARY | (os.O_RDWR if new else os.O_RDONLY))
            except OSError:
                _close_handle(handle)
                raise
            try:
                yield fd, new
            finally:
                os.close(fd)


@contextmanager
def _archive_file(store: str | Path, raw_id: str, create: bool):
    _check_id(raw_id)
    root = Path(os.path.abspath(Path(store).expanduser()))
    if os.name == "nt":
        opener = _windows_file
    elif os.name == "posix" and hasattr(os, "O_NOFOLLOW") and os.open in os.supports_dir_fd:
        opener = _posix_file
    else:
        raise OSError("safe archive access is unsupported on this platform")
    with opener(root, raw_id, create) as opened:
        yield opened


def _read(fd: int) -> bytes:
    with os.fdopen(os.dup(fd), "rb") as archive:
        content = archive.read(MAX_ARCHIVE_BYTES + 1)
    if len(content) > MAX_ARCHIVE_BYTES:
        raise ValueError("archive exceeds safety limit")
    return content


def archive_bytes(store: str | Path, raw_id: str, content: bytes) -> str:
    if len(content) > MAX_ARCHIVE_BYTES:
        raise ValueError("archive exceeds safety limit")
    with _archive_file(store, raw_id, create=True) as (fd, new):
        if new:
            with os.fdopen(os.dup(fd), "wb") as archive:
                archive.write(content)
            os.lseek(fd, 0, os.SEEK_SET)
        if _read(fd) != content:
            raise ValueError("raw archive integrity failure")
    return str(Path(store).expanduser() / raw_id)


def read_archive(store: str | Path, raw_id: str) -> bytes:
    with _archive_file(store, raw_id, create=False) as (fd, _):
        return _read(fd)
