"""Unit tests for reproducibility metadata utilities."""

from __future__ import annotations

import hashlib
import json
import subprocess
from unittest.mock import Mock, patch

import pytest

from intellifl.utils.reproducibility import (
    get_file_checksum,
    get_system_metadata,
    save_reproducibility_manifest,
)


class TestGetFileChecksum:
    def test_matches_hashlib_for_known_content(self, tmp_path):
        f = tmp_path / "x.txt"
        content = b"hello world"
        f.write_bytes(content)
        expected = hashlib.sha256(content).hexdigest()
        assert get_file_checksum(f) == expected

    def test_handles_files_larger_than_block_size(self, tmp_path):
        # 4 KB chunked reader — push past one block boundary
        f = tmp_path / "big.bin"
        content = b"a" * (4096 * 3 + 17)
        f.write_bytes(content)
        assert get_file_checksum(f) == hashlib.sha256(content).hexdigest()

    def test_accepts_string_path(self, tmp_path):
        f = tmp_path / "x.txt"
        f.write_bytes(b"abc")
        assert get_file_checksum(str(f)) == hashlib.sha256(b"abc").hexdigest()

    def test_empty_file(self, tmp_path):
        f = tmp_path / "empty"
        f.write_bytes(b"")
        assert get_file_checksum(f) == hashlib.sha256(b"").hexdigest()


def _fail_subprocess(cmd, *_args, **_kwargs):
    """Default subprocess.check_output side-effect: simulate every external tool missing.

    Git block catches FileNotFoundError; uv/pip blocks only catch SubprocessError.
    Use the right exception per command so the SUT exercises its full fallback path.
    """
    if cmd and cmd[0] == "git":
        raise FileNotFoundError
    raise subprocess.SubprocessError("not available")


class TestGetSystemMetadata:
    def test_returns_required_top_level_keys(self):
        with (
            patch("intellifl.utils.reproducibility.torch.cuda.is_available", return_value=False),
            patch("intellifl.utils.reproducibility.shutil.which", return_value=None),
            patch(
                "intellifl.utils.reproducibility.subprocess.check_output",
                side_effect=_fail_subprocess,
            ),
        ):
            md = get_system_metadata()
        assert {"os", "python", "hardware"}.issubset(md)
        assert "system" in md["os"]
        assert "version" in md["python"]
        assert "cpu_count" in md["hardware"]

    def test_includes_gpu_info_when_cuda_available(self):
        fake_props = Mock(name="GPU0", total_memory=8 * 1024**3, major=8, minor=6)
        fake_props.name = "Fake GPU"
        with (
            patch("intellifl.utils.reproducibility.torch.cuda.is_available", return_value=True),
            patch("intellifl.utils.reproducibility.torch.cuda.device_count", return_value=1),
            patch(
                "intellifl.utils.reproducibility.torch.cuda.get_device_properties",
                return_value=fake_props,
            ),
            patch("intellifl.utils.reproducibility.shutil.which", return_value=None),
            patch(
                "intellifl.utils.reproducibility.subprocess.check_output",
                side_effect=_fail_subprocess,
            ),
        ):
            md = get_system_metadata()
        gpus = md["hardware"]["gpus"]
        assert len(gpus) == 1
        assert gpus[0]["index"] == 0
        assert gpus[0]["name"] == "Fake GPU"
        assert gpus[0]["capability"] == "8.6"

    def test_includes_git_metadata_when_git_present(self):
        def fake_check_output(cmd, *_args, **_kwargs):
            if cmd[:3] == ["git", "rev-parse", "--abbrev-ref"]:
                return b"main\n"
            if cmd[:3] == ["git", "rev-parse", "HEAD"]:
                return b"abc123\n"
            raise subprocess.SubprocessError("uv/pip not used in this test")

        with (
            patch("intellifl.utils.reproducibility.torch.cuda.is_available", return_value=False),
            patch("intellifl.utils.reproducibility.shutil.which", return_value=None),
            patch(
                "intellifl.utils.reproducibility.subprocess.check_output",
                side_effect=fake_check_output,
            ),
        ):
            md = get_system_metadata()
        assert md["git"] == {"branch": "main", "commit": "abc123"}

    def test_omits_git_when_subprocess_fails(self):
        def fake(cmd, *_a, **_k):
            if cmd and cmd[0] == "git":
                raise subprocess.SubprocessError("git error")
            raise subprocess.SubprocessError("not available")

        with (
            patch("intellifl.utils.reproducibility.torch.cuda.is_available", return_value=False),
            patch("intellifl.utils.reproducibility.shutil.which", return_value=None),
            patch(
                "intellifl.utils.reproducibility.subprocess.check_output",
                side_effect=fake,
            ),
        ):
            md = get_system_metadata()
        assert "git" not in md

    def test_prefers_uv_over_pip_for_packages(self):
        captured: dict[str, list[str]] = {"calls": []}

        def fake_check_output(cmd, *_args, **_kwargs):
            captured["calls"].append(cmd[0])
            if cmd[0] == "uv":
                return b"numpy==1.26.0\nrequests==2.31.0\n"
            if cmd[0] == "git":
                raise FileNotFoundError
            return b"should-not-be-called\n"

        with (
            patch("intellifl.utils.reproducibility.torch.cuda.is_available", return_value=False),
            patch("intellifl.utils.reproducibility.shutil.which", return_value="/usr/bin/uv"),
            patch(
                "intellifl.utils.reproducibility.subprocess.check_output",
                side_effect=fake_check_output,
            ),
        ):
            md = get_system_metadata()
        assert md["packages"] == ["numpy==1.26.0", "requests==2.31.0"]
        # pip must not have been consulted
        assert "uv" in captured["calls"]
        assert all(c != "/usr/bin/python" for c in captured["calls"])

    def test_falls_back_to_pip_when_uv_freeze_fails(self):
        def fake_check_output(cmd, *_args, **_kwargs):
            if cmd[0] == "uv":
                raise subprocess.SubprocessError("uv broken")
            if cmd[0] == "git":
                raise FileNotFoundError
            # pip path
            if "pip" in cmd:
                return b"flask==3.0.0\n"
            raise subprocess.SubprocessError("unexpected call")

        with (
            patch("intellifl.utils.reproducibility.torch.cuda.is_available", return_value=False),
            patch("intellifl.utils.reproducibility.shutil.which", return_value="/usr/bin/uv"),
            patch(
                "intellifl.utils.reproducibility.subprocess.check_output",
                side_effect=fake_check_output,
            ),
        ):
            md = get_system_metadata()
        assert md["packages"] == ["flask==3.0.0"]

    def test_omits_packages_when_both_uv_and_pip_fail(self):
        with (
            patch("intellifl.utils.reproducibility.torch.cuda.is_available", return_value=False),
            patch("intellifl.utils.reproducibility.shutil.which", return_value=None),
            patch(
                "intellifl.utils.reproducibility.subprocess.check_output",
                side_effect=subprocess.SubprocessError,
            ),
        ):
            md = get_system_metadata()
        assert "packages" not in md


class TestSaveReproducibilityManifest:
    @pytest.fixture
    def stub_metadata(self):
        with patch(
            "intellifl.utils.reproducibility.get_system_metadata",
            return_value={"stubbed": True},
        ) as m:
            yield m

    def test_writes_manifest_with_system_block(self, tmp_path, stub_metadata):
        save_reproducibility_manifest(tmp_path)
        manifest_path = tmp_path / "MANIFEST.json"
        assert manifest_path.exists()
        data = json.loads(manifest_path.read_text())
        assert data["manifest_version"] == "1.0"
        assert "timestamp" in data
        assert data["system"] == {"stubbed": True}
        assert "config_checksum" not in data

    def test_includes_config_checksum_when_path_exists(self, tmp_path, stub_metadata):
        config = tmp_path / "config.json"
        config.write_bytes(b'{"foo": 1}')
        save_reproducibility_manifest(tmp_path, config_path=config)
        data = json.loads((tmp_path / "MANIFEST.json").read_text())
        assert data["config_checksum"]["file"] == "config.json"
        assert data["config_checksum"]["sha256"] == hashlib.sha256(b'{"foo": 1}').hexdigest()

    def test_skips_config_checksum_when_path_missing(self, tmp_path, stub_metadata):
        save_reproducibility_manifest(tmp_path, config_path=tmp_path / "nope.json")
        data = json.loads((tmp_path / "MANIFEST.json").read_text())
        assert "config_checksum" not in data

    def test_logs_error_but_does_not_raise_on_oserror(self, tmp_path, stub_metadata, caplog):
        with patch("intellifl.utils.reproducibility.open", side_effect=OSError("disk full")):
            with caplog.at_level("ERROR"):
                save_reproducibility_manifest(tmp_path)
        assert any("Failed to save reproducibility manifest" in r.message for r in caplog.records)
