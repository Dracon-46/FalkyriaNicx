"""Tests for ``nicx scan`` privacy scanner CLI command."""

from __future__ import annotations

import json
import sys
from subprocess import CompletedProcess
from unittest.mock import MagicMock, patch

import pytest

from nicx.comandos.instalacao.scan import PrivacyScanner, ScanResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_proc(
    stdout: str = "",
    stderr: str = "",
    returncode: int = 0,
) -> CompletedProcess:
    return CompletedProcess(
        args=[], returncode=returncode, stdout=stdout, stderr=stderr
    )


@pytest.fixture
def posix_platform():
    """Process checks use pgrep on POSIX; Windows reads tasklist instead."""
    with patch("sys.platform", "linux"):
        yield


# ---------------------------------------------------------------------------
# TestScanResultDataclass
# ---------------------------------------------------------------------------


class TestScanResultDataclass:
    def test_fields_exist(self) -> None:
        r = ScanResult(name="test", status="ok", message="all good", platform="all")
        assert r.name == "test"
        assert r.status == "ok"
        assert r.message == "all good"
        assert r.platform == "all"

    def test_status_values(self) -> None:
        for status in ("ok", "warn", "fail", "skip"):
            r = ScanResult(name="x", status=status, message="", platform="all")
            assert r.status == status

    def test_platform_values(self) -> None:
        for plat in ("darwin", "linux", "all"):
            r = ScanResult(name="x", status="ok", message="", platform=plat)
            assert r.platform == plat


# ---------------------------------------------------------------------------
# TestFileVault
# ---------------------------------------------------------------------------


class TestFileVault:
    def test_filevault_enabled(self) -> None:
        scanner = PrivacyScanner()
        proc = _make_proc(stdout="FileVault is On.")
        with patch("subprocess.run", return_value=proc):
            result = scanner.check_filevault()
        assert result.status == "ok"

    def test_filevault_disabled(self) -> None:
        scanner = PrivacyScanner()
        proc = _make_proc(stdout="FileVault is Off.")
        with patch("subprocess.run", return_value=proc):
            result = scanner.check_filevault()
        assert result.status == "fail"

    def test_command_not_found(self) -> None:
        scanner = PrivacyScanner()
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = scanner.check_filevault()
        assert result.status == "skip"


# ---------------------------------------------------------------------------
# TestMDM
# ---------------------------------------------------------------------------


class TestMDM:
    def test_not_enrolled(self) -> None:
        scanner = PrivacyScanner()
        stdout = "Enrolled via DEP: No\nMDM enrollment: not enrolled"
        with patch(
            "subprocess.run",
            return_value=_make_proc(stdout=stdout),
        ):
            result = scanner.check_mdm()
        assert result.status == "ok"

    def test_enrolled(self) -> None:
        scanner = PrivacyScanner()
        stdout = "MDM enrollment: Yes\nEnrolled via DEP: Yes"
        with patch(
            "subprocess.run",
            return_value=_make_proc(stdout=stdout),
        ):
            result = scanner.check_mdm()
        assert result.status == "warn"


# ---------------------------------------------------------------------------
# TestCloudSync
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("posix_platform")
class TestCloudSync:
    def test_no_agents(self) -> None:
        """pgrep returns non-zero → no sync agents running."""
        scanner = PrivacyScanner()
        with patch(
            "subprocess.run",
            return_value=_make_proc(returncode=1, stdout=""),
        ):
            result = scanner.check_cloud_sync_agents()
        assert result.status == "ok"

    def test_dropbox_running(self) -> None:
        """pgrep returns 0 when Dropbox is in the command."""
        scanner = PrivacyScanner()

        def _pgrep_side_effect(cmd, **kwargs):
            if "Dropbox" in cmd:
                return _make_proc(returncode=0, stdout="1234")
            return _make_proc(returncode=1, stdout="")

        with patch("subprocess.run", side_effect=_pgrep_side_effect):
            result = scanner.check_cloud_sync_agents()
        assert result.status == "warn"


# ---------------------------------------------------------------------------
# TestNetworkExposure
# ---------------------------------------------------------------------------


class TestNetworkExposure:
    def test_no_exposed_ports(self) -> None:
        """Only localhost bindings -> ok."""
        scanner = PrivacyScanner()
        lsof_out = "ollama 1234 user IPv4 TCP 127.0.0.1:11434 (LISTEN)\n"
        with patch("subprocess.run", return_value=_make_proc(stdout=lsof_out)):
            result = scanner.check_network_exposure()
        assert result.status == "ok"

    def test_exposed_port(self) -> None:
        """A port bound to * -> warn with port in message."""
        scanner = PrivacyScanner()
        lsof_out = "ollama 1234 user IPv4 TCP *:11434 (LISTEN)\n"
        with patch("subprocess.run", return_value=_make_proc(stdout=lsof_out)):
            result = scanner.check_network_exposure()
        assert result.status == "warn"
        assert "11434" in result.message


# ---------------------------------------------------------------------------
# TestLUKS
# ---------------------------------------------------------------------------


class TestLUKS:
    def test_encrypted(self) -> None:
        """lsblk JSON contains crypto_LUKS -> ok."""
        scanner = PrivacyScanner()
        lsblk_data = {
            "blockdevices": [
                {
                    "name": "sda",
                    "type": "disk",
                    "fstype": None,
                    "children": [
                        {"name": "sda1", "type": "part", "fstype": "crypto_LUKS"}
                    ],
                }
            ]
        }
        with patch(
            "subprocess.run",
            return_value=_make_proc(stdout=json.dumps(lsblk_data)),
        ):
            result = scanner.check_luks()
        assert result.status == "ok"

    def test_not_encrypted(self) -> None:
        """lsblk JSON has only ext4 -> fail."""
        scanner = PrivacyScanner()
        lsblk_data = {
            "blockdevices": [
                {"name": "sda", "type": "disk", "fstype": None},
                {"name": "sda1", "type": "part", "fstype": "ext4"},
            ]
        }
        with patch(
            "subprocess.run",
            return_value=_make_proc(stdout=json.dumps(lsblk_data)),
        ):
            result = scanner.check_luks()
        assert result.status == "fail"


# ---------------------------------------------------------------------------
# TestScreenRecording
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("posix_platform")
class TestScreenRecording:
    def test_none_running(self) -> None:
        """No screen-recording processes -> ok."""
        scanner = PrivacyScanner()
        with patch(
            "subprocess.run",
            return_value=_make_proc(returncode=1, stdout=""),
        ):
            result = scanner.check_screen_recording()
        assert result.status == "ok"

    def test_teamviewer_running(self) -> None:
        """TeamViewer found -> warn."""
        scanner = PrivacyScanner()

        def _pgrep_side_effect(cmd, **kwargs):
            if "TeamViewer" in cmd:
                return _make_proc(returncode=0, stdout="5678")
            return _make_proc(returncode=1, stdout="")

        with patch("subprocess.run", side_effect=_pgrep_side_effect):
            result = scanner.check_screen_recording()
        assert result.status == "warn"


# ---------------------------------------------------------------------------
# TestPlatformFiltering
# ---------------------------------------------------------------------------


class TestPlatformFiltering:
    def test_run_all_filters_to_current_platform(self) -> None:
        """run_all() returns only current-platform + 'all' checks."""
        scanner = PrivacyScanner()
        current_plat = PrivacyScanner._current_platform()

        with patch.object(scanner, "_get_all_checks") as mock_get:
            darwin_ck = MagicMock(return_value=ScanResult("d", "ok", "msg", "darwin"))
            linux_ck = MagicMock(return_value=ScanResult("l", "ok", "msg", "linux"))
            all_ck = MagicMock(return_value=ScanResult("a", "ok", "msg", "all"))

            mock_get.return_value = [darwin_ck, linux_ck, all_ck]
            results = scanner.run_all()

        result_platforms = {r.platform for r in results}
        assert result_platforms <= {current_plat, "all"}
        assert "all" in result_platforms or current_plat in result_platforms


# ---------------------------------------------------------------------------
# TestRemoteAccess
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("posix_platform")
class TestRemoteAccess:
    """Tests for check_remote_access (Linux)."""

    def test_no_remote_access(self) -> None:
        scanner = PrivacyScanner()
        with patch.object(scanner, "_run") as mock_run:
            mock_run.return_value = CompletedProcess([], 1, stdout="", stderr="")
            result = scanner.check_remote_access()
        assert result.status == "ok"

    def test_xrdp_running(self) -> None:
        scanner = PrivacyScanner()
        with patch.object(scanner, "_run") as mock_run:

            def side_effect(cmd, **kw):
                if any("xrdp" in str(c) for c in cmd):
                    return CompletedProcess(cmd, 0, stdout="12345", stderr="")
                return CompletedProcess(cmd, 1, stdout="", stderr="")

            mock_run.side_effect = side_effect
            result = scanner.check_remote_access()
        assert result.status == "warn"


# ---------------------------------------------------------------------------
# TestICloudSync
# ---------------------------------------------------------------------------


class TestICloudSync:
    """Tests for check_icloud_sync (macOS)."""

    def test_no_icloud_sync(self) -> None:
        scanner = PrivacyScanner()
        with patch.object(scanner, "_run") as mock_run:
            mock_run.return_value = CompletedProcess(
                [], 0, stdout="no relevant output", stderr=""
            )
            result = scanner.check_icloud_sync()
        assert result.status in ("ok", "skip")

    def test_icloud_defaults_error_falls_through_to_ok(self) -> None:
        scanner = PrivacyScanner()
        with patch.object(scanner, "_run", side_effect=FileNotFoundError):
            result = scanner.check_icloud_sync()
        assert result.status == "ok"


# ---------------------------------------------------------------------------
# TestRunQuick
# ---------------------------------------------------------------------------


class TestRunQuick:
    """Tests for run_quick subset."""

    def test_run_quick_returns_subset(self) -> None:
        scanner = PrivacyScanner()
        plat = sys.platform
        with (
            patch.object(scanner, "check_filevault") as fv,
            patch.object(scanner, "check_luks") as luks,
            patch.object(scanner, "check_icloud_sync") as ic,
            patch.object(scanner, "check_cloud_sync_agents") as cs,
        ):
            fv.return_value = ScanResult("FV", "ok", "ok", "darwin")
            luks.return_value = ScanResult("LUKS", "ok", "ok", "linux")
            ic.return_value = ScanResult("iCloud", "ok", "ok", "darwin")
            cs.return_value = ScanResult("Cloud", "ok", "ok", plat)
            results = scanner.run_quick()
        for r in results:
            assert r.platform in (plat, "all")
        names = {r.name for r in results}
        assert "Network Exposure" not in names
        assert "Screen Recording" not in names

    def test_windows_never_runs_linux_or_macos_disk_checks(self) -> None:
        scanner = PrivacyScanner()
        with (
            patch("sys.platform", "win32"),
            patch.object(scanner, "check_filevault") as fv,
            patch.object(scanner, "check_luks") as luks,
            patch.object(scanner, "check_cloud_sync_agents") as cs,
        ):
            cs.return_value = ScanResult("Cloud", "ok", "ok", "all")
            results = scanner.run_quick()
        fv.assert_not_called()
        luks.assert_not_called()
        assert [r.name for r in results] == ["Cloud"]


# ---------------------------------------------------------------------------
# TestWindowsProcesses
# ---------------------------------------------------------------------------

_TASKLIST = (
    '"System Idle Process","0","Services","0","8 K"\n'
    '"OneDrive.exe","4321","Console","1","90.000 K"\n'
    '"AnyDesk.exe","5555","Console","1","20.000 K"\n'
)


class TestWindowsProcesses:
    """Windows has no pgrep; the process checks read tasklist."""

    def test_running_agent_is_reported(self) -> None:
        scanner = PrivacyScanner()
        with (
            patch("sys.platform", "win32"),
            patch.object(scanner, "_run", return_value=_make_proc(stdout=_TASKLIST)),
        ):
            cloud = scanner.check_cloud_sync_agents()
            remote = scanner.check_remote_access()
        assert cloud.status == "warn"
        assert "OneDrive" in cloud.message
        assert remote.status == "warn"
        assert "AnyDesk" in remote.message

    def test_no_agent_running(self) -> None:
        scanner = PrivacyScanner()
        idle = '"System Idle Process","0","Services","0","8 K"\n'
        with (
            patch("sys.platform", "win32"),
            patch.object(scanner, "_run", return_value=_make_proc(stdout=idle)),
        ):
            result = scanner.check_cloud_sync_agents()
        assert result.status == "ok"

    def test_missing_tasklist_is_skipped_not_ok(self) -> None:
        scanner = PrivacyScanner()
        with (
            patch("sys.platform", "win32"),
            patch.object(scanner, "_run", side_effect=FileNotFoundError),
        ):
            result = scanner.check_cloud_sync_agents()
        assert result.status == "skip"

    def test_missing_pgrep_is_skipped_not_ok(self) -> None:
        scanner = PrivacyScanner()
        with (
            patch("sys.platform", "linux"),
            patch.object(scanner, "_run", side_effect=FileNotFoundError),
        ):
            result = scanner.check_remote_access()
        assert result.status == "skip"

    def test_network_exposure_reads_netstat(self) -> None:
        scanner = PrivacyScanner()
        netstat = "  TCP    0.0.0.0:11434          0.0.0.0:0              LISTENING\n"
        with (
            patch("sys.platform", "win32"),
            patch.object(
                scanner, "_run", return_value=_make_proc(stdout=netstat)
            ) as run,
        ):
            result = scanner.check_network_exposure()
        assert run.call_args.args[0][0] == "netstat"
        assert result.status == "warn"
        assert "11434" in result.message


# ---------------------------------------------------------------------------
# TestDNS
# ---------------------------------------------------------------------------


class TestDNS:
    """Tests for check_dns (macOS)."""

    def test_encrypted_dns_detected(self) -> None:
        scanner = PrivacyScanner()
        scutil_out = (
            "resolver #1\n  nameserver[0] : 127.0.0.1\n  flags    : dns-over-https\n"
        )
        with (
            patch("sys.platform", "darwin"),
            patch("subprocess.run", return_value=_make_proc(stdout=scutil_out)),
        ):
            result = scanner.check_dns()
        assert result.status == "ok"
        assert "Encrypted" in result.message or "DoH" in result.message

    def test_plain_dns_detected(self) -> None:
        scanner = PrivacyScanner()
        scutil_out = (
            "resolver #1\n  nameserver[0] : 8.8.8.8\n  nameserver[1] : 8.8.4.4\n"
        )
        with (
            patch("sys.platform", "darwin"),
            patch("subprocess.run", return_value=_make_proc(stdout=scutil_out)),
        ):
            result = scanner.check_dns()
        assert result.status == "warn"
        assert "8.8.8.8" in result.message

    def test_private_dns(self) -> None:
        scanner = PrivacyScanner()
        scutil_out = "resolver #1\n  nameserver[0] : 192.168.1.1\n"
        with (
            patch("sys.platform", "darwin"),
            patch("subprocess.run", return_value=_make_proc(stdout=scutil_out)),
        ):
            result = scanner.check_dns()
        assert result.status == "ok"
        assert "192.168.1.1" in result.message

    def test_skip_on_linux(self) -> None:
        scanner = PrivacyScanner()
        with patch("sys.platform", "linux"):
            result = scanner.check_dns()
        assert result.status == "skip"

    def test_scutil_not_available(self) -> None:
        scanner = PrivacyScanner()
        with (
            patch("sys.platform", "darwin"),
            patch("subprocess.run", side_effect=FileNotFoundError),
        ):
            result = scanner.check_dns()
        assert result.status == "skip"


# ---------------------------------------------------------------------------
# TestExpandedRemoteAccess
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("posix_platform")
class TestExpandedRemoteAccess:
    """Verify expanded remote-access process list."""

    def test_ngrok_detected(self) -> None:
        scanner = PrivacyScanner()
        with patch.object(scanner, "_run") as mock_run:

            def side_effect(cmd, **kw):
                if any("ngrok" in str(c) for c in cmd):
                    return CompletedProcess(cmd, 0, stdout="99999", stderr="")
                return CompletedProcess(cmd, 1, stdout="", stderr="")

            mock_run.side_effect = side_effect
            result = scanner.check_remote_access()
        assert result.status == "warn"
        assert "ngrok" in result.message

    def test_tailscaled_detected(self) -> None:
        scanner = PrivacyScanner()
        with patch.object(scanner, "_run") as mock_run:

            def side_effect(cmd, **kw):
                if any("tailscaled" in str(c) for c in cmd):
                    return CompletedProcess(cmd, 0, stdout="88888", stderr="")
                return CompletedProcess(cmd, 1, stdout="", stderr="")

            mock_run.side_effect = side_effect
            result = scanner.check_remote_access()
        assert result.status == "warn"


# ---------------------------------------------------------------------------
# TestJsonOutput
# ---------------------------------------------------------------------------


class TestJsonOutput:
    """Test --json output flag."""

    def test_json_output_structure(self) -> None:
        from click.testing import CliRunner

        from nicx.comandos.instalacao.scan import scan

        runner = CliRunner()
        with patch(
            "nicx.comandos.instalacao.scan.PrivacyScanner.run_all",
            return_value=[
                ScanResult("Test", "ok", "all good", "all"),
            ],
        ):
            result = runner.invoke(scan, ["--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert data[0]["name"] == "Test"
        assert data[0]["status"] == "ok"
