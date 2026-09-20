from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import subprocess

import pytest

from agent_speed import archive
from agent_speed.filtering import filter_output


TEXT = "same\n" * 100
CONTENT = TEXT.encode()
DIGEST = hashlib.sha256(CONTENT).hexdigest()


def test_hardlinked_leaf_is_rejected_without_touching_target(tmp_path: Path) -> None:
    store = tmp_path / "store"
    store.mkdir(mode=0o700)
    outside = tmp_path / "outside"
    outside.write_bytes(CONTENT)
    outside.chmod(0o600)
    mode = outside.stat().st_mode
    os.link(outside, store / DIGEST)
    result = filter_output(TEXT, "git status", store)
    assert not result.changed
    assert result.raw_path is None
    with pytest.raises((OSError, ValueError)):
        archive.read_archive(store, DIGEST)
    assert outside.read_bytes() == CONTENT
    assert outside.stat().st_mode == mode


@pytest.mark.parametrize("raw_id", ["../outside", "x" * 64, "a" * 63, "A" * 64])
def test_invalid_leaf_name_never_creates_store(tmp_path: Path, raw_id: str) -> None:
    store = tmp_path / "missing"
    with pytest.raises(ValueError):
        archive.archive_bytes(store, raw_id, CONTENT)
    assert not store.exists()


if os.name == "posix":
    @pytest.mark.parametrize("position", ["store", "ancestor", "leaf"])
    def test_symlinks_are_rejected_without_chmod(tmp_path: Path, position: str) -> None:
        outside = tmp_path / "outside"
        outside.mkdir(mode=0o755)
        target = outside / DIGEST
        target.write_bytes(CONTENT)
        target.chmod(0o644)
        original_modes = outside.stat().st_mode, target.stat().st_mode
        store = tmp_path / "store"
        if position == "store":
            store.symlink_to(outside, target_is_directory=True)
        elif position == "ancestor":
            link = tmp_path / "linked-parent"
            link.symlink_to(outside, target_is_directory=True)
            store = link / "store"
        else:
            store.mkdir(mode=0o700)
            (store / DIGEST).symlink_to(target)
        result = filter_output(TEXT, "git status", store)
        assert not result.changed
        assert result.raw_path is None
        with pytest.raises((OSError, ValueError)):
            archive.read_archive(store, DIGEST)
        assert target.read_bytes() == CONTENT
        assert (outside.stat().st_mode, target.stat().st_mode) == original_modes
        assert not (outside / "store").exists()

    def test_replacing_store_after_open_cannot_redirect_write(tmp_path: Path, monkeypatch) -> None:
        store = tmp_path / "store"
        moved = tmp_path / "moved"
        outside = tmp_path / "outside"
        outside.mkdir(mode=0o700)
        real_directory = archive._posix_directory

        @contextmanager
        def replaced_directory(root, create):
            with real_directory(root, create) as fd:
                root.rename(moved)
                root.symlink_to(outside, target_is_directory=True)
                yield fd

        monkeypatch.setattr(archive, "_posix_directory", replaced_directory)
        archive.archive_bytes(store, DIGEST, CONTENT)
        assert (moved / DIGEST).read_bytes() == CONTENT
        assert not list(outside.iterdir())

    def test_replacing_leaf_after_open_does_not_redirect_read(tmp_path: Path, monkeypatch) -> None:
        store = tmp_path / "store"
        archive.archive_bytes(store, DIGEST, CONTENT)
        outside = tmp_path / "outside"
        outside.write_bytes(b"unrelated")
        real_check = archive._check_posix_file

        def replace_after_check(fd):
            real_check(fd)
            (store / DIGEST).unlink()
            (store / DIGEST).symlink_to(outside)

        monkeypatch.setattr(archive, "_check_posix_file", replace_after_check)
        assert archive.read_archive(store, DIGEST) == CONTENT
        assert outside.read_bytes() == b"unrelated"

    @pytest.mark.parametrize("kind", ["fifo", "directory", "public-file"])
    def test_unsafe_existing_leaf_fails_closed(tmp_path: Path, kind: str) -> None:
        target = tmp_path / DIGEST
        if kind == "fifo":
            os.mkfifo(target, 0o600)
        elif kind == "directory":
            target.mkdir(mode=0o700)
        else:
            target.write_bytes(CONTENT)
            target.chmod(0o644)
        result = filter_output(TEXT, "git status", tmp_path)
        assert not result.changed
        with pytest.raises((OSError, ValueError)):
            archive.read_archive(tmp_path, DIGEST)

    def test_public_store_is_rejected_not_chmodded(tmp_path: Path) -> None:
        tmp_path.chmod(0o755)
        result = filter_output(TEXT, "git status", tmp_path)
        assert not result.changed
        assert tmp_path.stat().st_mode & 0o777 == 0o755
        assert not list(tmp_path.iterdir())


if os.name == "nt":
    @pytest.mark.parametrize("position", ["store", "ancestor", "leaf"])
    def test_windows_junctions_are_rejected(tmp_path: Path, position: str) -> None:
        outside = tmp_path / "outside"
        outside.mkdir()
        store = tmp_path / "store"
        link = store
        if position == "ancestor":
            link = tmp_path / "parent"
            store = link / "store"
        elif position == "leaf":
            store.mkdir()
            link = store / DIGEST
        env = dict(os.environ, TEST_LINK=str(link), TEST_TARGET=str(outside))
        subprocess.run([
            "powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
            "New-Item -ItemType Junction -Path $env:TEST_LINK -Target $env:TEST_TARGET -ErrorAction Stop | Out-Null",
        ], env=env, capture_output=True, check=True)
        try:
            result = filter_output(TEXT, "git status", store)
            assert not result.changed
            with pytest.raises((OSError, ValueError)):
                archive.read_archive(store, DIGEST)
            assert not list(outside.iterdir())
        finally:
            link.rmdir()

    def test_windows_directory_lock_blocks_rename_and_reparse_writer(tmp_path: Path) -> None:
        import ctypes

        store = tmp_path / "store"
        with archive._windows_directory(store, create=True):
            with pytest.raises(OSError):
                store.rename(tmp_path / "moved")
            handle = archive._kernel.CreateFileW(str(store), 0x40000000, 7, None, 3, 0x02200000, None)
            error = ctypes.get_last_error()
            if handle != ctypes.c_void_p(-1).value:
                archive._close_handle(handle)
                pytest.fail("write handle could repoint a validated directory")
            assert error == 32

    def test_windows_preexisting_directory_writer_fails_closed(tmp_path: Path) -> None:
        import ctypes

        store = tmp_path / "store"
        store.mkdir()
        handle = archive._kernel.CreateFileW(str(store), 0x40000000, 7, None, 3, 0x02200000, None)
        assert handle != ctypes.c_void_p(-1).value
        try:
            assert not filter_output(TEXT, "git status", store).changed
            assert not list(store.iterdir())
        finally:
            archive._close_handle(handle)

    def test_windows_leaf_handle_blocks_concurrent_write_and_delete(tmp_path: Path) -> None:
        archive.archive_bytes(tmp_path, DIGEST, CONTENT)
        with archive._archive_file(tmp_path, DIGEST, create=False):
            with pytest.raises(OSError):
                (tmp_path / DIGEST).unlink()
            with pytest.raises(OSError):
                (tmp_path / DIGEST).write_bytes(b"modified")
        assert archive.read_archive(tmp_path, DIGEST) == CONTENT

    def test_windows_drive_alias_result_is_rejected(monkeypatch) -> None:
        import ctypes

        def aliased_path(handle, buffer, length, flags):
            buffer.value = "\\\\?\\Volume{00000000-0000-0000-0000-000000000000}\\aliased"
            return len(buffer.value)

        monkeypatch.setattr(archive._kernel, "GetFinalPathNameByHandleW", aliased_path)
        with pytest.raises(ValueError, match="drive alias"):
            archive._volume_root(ctypes.c_void_p(1))
