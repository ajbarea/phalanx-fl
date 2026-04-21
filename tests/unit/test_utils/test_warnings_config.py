"""Unit tests for the centralized warning suppression registry."""

from __future__ import annotations

import os
import warnings
from unittest.mock import patch

import pytest

from intellifl.utils import warnings_config
from intellifl.utils.warnings_config import (
    WARNING_FILTERS,
    apply_env_vars,
    apply_filter,
    configure_warnings,
    get_subprocess_env_vars,
    list_filters,
)


@pytest.fixture
def clean_env(monkeypatch):
    """Strip every env var the registry might set, so apply_* starts from a clean slate."""
    for cfg in WARNING_FILTERS.values():
        for var in cfg.get("env_vars", {}):
            monkeypatch.delenv(var, raising=False)
    return monkeypatch


class TestApplyEnvVars:
    def test_applies_all_filters_when_no_keys_given(self, clean_env):
        apply_env_vars()
        # Pick a representative env var from a known entry
        assert os.environ.get("RAY_ENABLE_METRICS_COLLECTION") == "0"

    def test_applies_only_requested_keys(self, clean_env):
        apply_env_vars(["ray_accel_env_var"])
        assert os.environ.get("RAY_ACCEL_ENV_VAR_OVERRIDE_ON_ZERO") == "0"
        # Should not have applied unrelated entries
        assert "RAY_ENABLE_METRICS_COLLECTION" not in os.environ

    def test_unknown_key_logs_warning_and_skips(self, clean_env, caplog):
        with caplog.at_level("WARNING", logger=warnings_config.logger.name):
            apply_env_vars(["does_not_exist"])
        assert any("Unknown warning filter key" in r.message for r in caplog.records)

    def test_does_not_overwrite_preexisting_env_var(self, clean_env):
        clean_env.setenv("RAY_ENABLE_METRICS_COLLECTION", "preserved")
        apply_env_vars(["ray_metrics_agent"])
        # setdefault semantics: existing value wins
        assert os.environ["RAY_ENABLE_METRICS_COLLECTION"] == "preserved"


class TestGetSubprocessEnvVars:
    def test_returns_dict_for_all_filters(self):
        env = get_subprocess_env_vars()
        assert isinstance(env, dict)
        assert "RAY_ENABLE_METRICS_COLLECTION" in env
        assert env["RAY_ENABLE_METRICS_COLLECTION"] == "0"

    def test_filters_to_requested_keys(self):
        env = get_subprocess_env_vars(["ray_accel_env_var"])
        assert env == {"RAY_ACCEL_ENV_VAR_OVERRIDE_ON_ZERO": "0"}

    def test_silently_skips_unknown_key(self):
        env = get_subprocess_env_vars(["nope"])
        assert env == {}

    def test_filter_with_no_env_vars_yields_no_entries(self):
        # numpy_runtime has no env_vars, only filter_kwargs
        env = get_subprocess_env_vars(["numpy_runtime"])
        assert env == {}


class TestApplyFilter:
    def test_applies_known_filter(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.resetwarnings()
            apply_filter("numpy_runtime")
            warnings.warn("overflow", RuntimeWarning, stacklevel=2)
        # The filter targets module=numpy.*, so a non-numpy warning still surfaces
        assert any(issubclass(w.category, RuntimeWarning) for w in caught)

    def test_unknown_key_is_a_no_op(self, caplog):
        with caplog.at_level("WARNING", logger=warnings_config.logger.name):
            apply_filter("nonexistent")
        assert any("Unknown warning filter key" in r.message for r in caplog.records)

    def test_filter_without_filter_kwargs_does_not_raise(self):
        # ray_metrics_agent has only env_vars
        apply_filter("ray_metrics_agent")  # must not raise


class TestConfigureWarnings:
    def test_apply_all_filters_default(self, clean_env):
        with warnings.catch_warnings():
            configure_warnings()
        # Env vars from the registry should be set
        assert "RAY_ENABLE_METRICS_COLLECTION" in os.environ

    def test_exclude_drops_specific_keys(self, clean_env):
        with warnings.catch_warnings():
            configure_warnings(exclude=["ray_metrics_agent"])
        assert "RAY_ENABLE_METRICS_COLLECTION" not in os.environ

    def test_include_only_restricts_application(self, clean_env):
        with warnings.catch_warnings():
            configure_warnings(include_only=["ray_accel_env_var"])
        assert "RAY_ACCEL_ENV_VAR_OVERRIDE_ON_ZERO" in os.environ
        assert "RAY_ENABLE_METRICS_COLLECTION" not in os.environ

    def test_include_only_silently_ignores_unknown_keys(self, clean_env):
        with warnings.catch_warnings():
            configure_warnings(include_only=["bogus", "ray_accel_env_var"])
        assert "RAY_ACCEL_ENV_VAR_OVERRIDE_ON_ZERO" in os.environ

    def test_verbose_logs_each_filter(self, clean_env, caplog):
        with caplog.at_level("INFO", logger=warnings_config.logger.name):
            with warnings.catch_warnings():
                configure_warnings(include_only=["numpy_runtime"], verbose=True)
        messages = [r.message for r in caplog.records]
        assert any("Applying warning filter: numpy_runtime" in m for m in messages)
        assert any("Applied 1 warning filters" in m for m in messages)


class TestListFilters:
    def test_prints_every_registered_filter(self, capsys):
        list_filters()
        captured = capsys.readouterr().out
        for key in WARNING_FILTERS:
            assert f"[{key}]" in captured
        assert "Available Warning Filters" in captured


class TestRegistryShape:
    def test_every_entry_has_a_description(self):
        for key, cfg in WARNING_FILTERS.items():
            assert "description" in cfg, f"{key} missing description"

    def test_every_entry_has_either_env_vars_or_filter_kwargs(self):
        for key, cfg in WARNING_FILTERS.items():
            assert "env_vars" in cfg or "filter_kwargs" in cfg, f"{key} has nothing to apply"


def test_apply_env_vars_handles_caplog_isolation(clean_env):
    """Regression: apply_env_vars must not raise when the logger has no handlers."""
    with patch.object(warnings_config.logger, "warning") as mock_warn:
        apply_env_vars(["unknown_key"])
        mock_warn.assert_called_once()
