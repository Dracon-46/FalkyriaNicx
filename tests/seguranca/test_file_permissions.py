"""Tests for secure file creation helpers (Section 4)."""

from __future__ import annotations

import os
import stat
import sys
import tempfile
from pathlib import Path

import pytest

posix_modes = pytest.mark.skipif(
    sys.platform == "win32",
    reason=(
        "Windows não tem bits de permissão POSIX (o chmod só liga o somente "
        "leitura); a proteção vem da ACL herdada do perfil do usuário"
    ),
)


class TestSecureMkdir:
    """secure_mkdir should create directories with 0o700."""

    @posix_modes
    def test_creates_directory_with_700(self) -> None:
        from nicx.seguranca.file_utils import secure_mkdir

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "secure_dir"
            result = secure_mkdir(target)
            assert result.is_dir()
            mode = stat.S_IMODE(os.stat(target).st_mode)
            assert mode == 0o700

    def test_creates_parent_directories(self) -> None:
        from nicx.seguranca.file_utils import secure_mkdir

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "a" / "b" / "c"
            result = secure_mkdir(target)
            assert result.is_dir()

    @posix_modes
    def test_existing_directory_gets_permission_fix(self) -> None:
        from nicx.seguranca.file_utils import secure_mkdir

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "existing"
            target.mkdir(mode=0o755)
            secure_mkdir(target)
            mode = stat.S_IMODE(os.stat(target).st_mode)
            assert mode == 0o700


class TestSecureCreate:
    """secure_create should create files with 0o600."""

    @posix_modes
    def test_creates_file_with_600(self) -> None:
        from nicx.seguranca.file_utils import secure_create

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "secure_file.db"
            result = secure_create(target)
            assert result.exists()
            mode = stat.S_IMODE(os.stat(target).st_mode)
            assert mode == 0o600

    @posix_modes
    def test_existing_file_gets_permission_fix(self) -> None:
        from nicx.seguranca.file_utils import secure_create

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "existing.db"
            target.write_text("data", encoding="utf-8")
            os.chmod(target, 0o644)
            secure_create(target)
            mode = stat.S_IMODE(os.stat(target).st_mode)
            assert mode == 0o600

    @posix_modes
    def test_creates_parent_directory_with_700(self) -> None:
        from nicx.seguranca.file_utils import secure_create

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "sub" / "file.db"
            secure_create(target)
            parent_mode = stat.S_IMODE(os.stat(target.parent).st_mode)
            assert parent_mode == 0o700


@pytest.mark.skipif(sys.platform != "win32", reason="comportamento do Windows")
def test_windows_secure_files_stay_writable_and_replaceable() -> None:
    from nicx.seguranca.file_utils import secure_create, secure_write_text

    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "sub" / "state.json"
        secure_create(target)
        secure_write_text(target, "um")
        # Rewriting must still work: a read-only file would break os.replace.
        secure_write_text(target, "dois")
        assert target.read_text(encoding="utf-8") == "dois"
        assert os.stat(target).st_mode & stat.S_IWRITE
        assert os.stat(target.parent).st_mode & stat.S_IWRITE
