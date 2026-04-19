"""Unit tests for the platform-aware Ray initialization helper."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest

from intellifl.utils.ray_config import RayConfig


@pytest.fixture
def clean_env(monkeypatch):
    """Strip the env vars RayConfig touches so each test starts from a known state."""
    for var in (
        "RAY_ACCEL_ENV_VAR_OVERRIDE_ON_ZERO",
        "RAY_OVERRIDE_RUNTIME_ENV_DEFAULT_EXCLUDES",
        "RAY_BACKEND_LOG_LEVEL",
        "VIRTUAL_ENV",
    ):
        monkeypatch.delenv(var, raising=False)
    return monkeypatch


class TestGetInitArgs:
    def test_returns_expected_keys_with_dashboard_disabled(self, clean_env):
        args = RayConfig.get_init_args()
        assert args["include_dashboard"] is False
        assert args["ignore_reinit_error"] is True
        assert args["configure_logging"] is True
        assert args["logging_level"] == logging.WARNING

    def test_sets_accelerator_warning_suppressor(self, clean_env):
        import os
        RayConfig.get_init_args()
        assert os.environ["RAY_ACCEL_ENV_VAR_OVERRIDE_ON_ZERO"] == "0"

    def test_sets_runtime_env_excludes_to_empty(self, clean_env):
        import os
        RayConfig.get_init_args()
        assert os.environ["RAY_OVERRIDE_RUNTIME_ENV_DEFAULT_EXCLUDES"] == ""

    def test_unsets_virtual_env(self, clean_env):
        import os
        clean_env.setenv("VIRTUAL_ENV", "/some/venv")
        RayConfig.get_init_args()
        assert "VIRTUAL_ENV" not in os.environ

    def test_virtual_env_unset_is_idempotent(self, clean_env):
        # Must not raise when VIRTUAL_ENV is already absent
        RayConfig.get_init_args()

    def test_backend_log_level_defaults_to_error(self, clean_env):
        import os
        RayConfig.get_init_args()
        assert os.environ["RAY_BACKEND_LOG_LEVEL"] == "error"

    def test_backend_log_level_respects_existing_value(self, clean_env):
        import os
        clean_env.setenv("RAY_BACKEND_LOG_LEVEL", "debug")
        RayConfig.get_init_args()
        # setdefault semantics: pre-existing value wins
        assert os.environ["RAY_BACKEND_LOG_LEVEL"] == "debug"


class TestInitialize:
    def test_skips_when_already_initialized(self, clean_env, caplog):
        with (
            patch("intellifl.utils.ray_config.ray.is_initialized", return_value=True),
            patch("intellifl.utils.ray_config.ray.init") as mock_init,
        ):
            with caplog.at_level("INFO", logger="intellifl.utils.ray_config"):
                RayConfig.initialize()
        mock_init.assert_not_called()
        assert any("already active" in r.message for r in caplog.records)

    def test_calls_ray_init_with_get_init_args_payload(self, clean_env):
        fake_context = MagicMock()
        fake_context.address_info = {"node_ip_address": "127.0.0.1"}
        with (
            patch("intellifl.utils.ray_config.ray.is_initialized", return_value=False),
            patch("intellifl.utils.ray_config.ray.init", return_value=fake_context) as mock_init,
        ):
            RayConfig.initialize()
        mock_init.assert_called_once()
        kwargs = mock_init.call_args.kwargs
        assert kwargs["include_dashboard"] is False
        assert kwargs["ignore_reinit_error"] is True

    def test_logs_address_after_successful_init(self, clean_env, caplog):
        fake_context = MagicMock()
        fake_context.address_info = {"node_ip_address": "10.0.0.5"}
        with (
            patch("intellifl.utils.ray_config.ray.is_initialized", return_value=False),
            patch("intellifl.utils.ray_config.ray.init", return_value=fake_context),
            patch("intellifl.utils.ray_config.ray.__version__", "2.99.0"),
        ):
            with caplog.at_level("INFO", logger="intellifl.utils.ray_config"):
                RayConfig.initialize()
        joined = " ".join(r.message for r in caplog.records)
        assert "10.0.0.5" in joined
        assert "2.99.0" in joined

    def test_reraises_init_failure_after_logging(self, clean_env, caplog):
        with (
            patch("intellifl.utils.ray_config.ray.is_initialized", return_value=False),
            patch(
                "intellifl.utils.ray_config.ray.init",
                side_effect=RuntimeError("dashboard port in use"),
            ),
        ):
            with caplog.at_level("ERROR", logger="intellifl.utils.ray_config"):
                with pytest.raises(RuntimeError, match="dashboard port in use"):
                    RayConfig.initialize()
        assert any("Critical failure" in r.message for r in caplog.records)
