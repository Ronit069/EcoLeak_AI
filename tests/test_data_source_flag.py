"""Phase 2 P3: the USE_MOCK_DATA mock-to-real gate.

Default must stay on the Phase 1 mock fixture so ``main`` is demo-able without a
database; the real SQL path activates only when explicitly selected.
"""

from __future__ import annotations

import pytest

from engine.data_source import default_data_source, resolve_use_mock_data
from engine.service import build_engine


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("ECOLEAK_USE_MOCK_DATA", raising=False)
    monkeypatch.delenv("ECOLEAK_SQL_DSN", raising=False)
    monkeypatch.delenv("ENGINE_DSN", raising=False)
    yield


def test_flag_precedence_and_parsing(monkeypatch):
    assert resolve_use_mock_data() is None
    assert resolve_use_mock_data(True) is True
    assert resolve_use_mock_data(False) is False
    monkeypatch.setenv("ECOLEAK_USE_MOCK_DATA", "false")
    assert resolve_use_mock_data() is False
    monkeypatch.setenv("ECOLEAK_USE_MOCK_DATA", "TRUE")
    assert resolve_use_mock_data() is True
    # explicit argument beats the env var
    assert resolve_use_mock_data(False) is False


def test_default_is_mock_without_flag_or_dsn():
    assert type(default_data_source()).__name__ == "MockDataSource"
    assert type(build_engine().data_source).__name__ == "MockDataSource"


def test_force_mock_even_with_dsn(monkeypatch, tmp_path):
    monkeypatch.setenv("ECOLEAK_SQL_DSN", f"sqlite+pysqlite:///{tmp_path / 'x.db'}")
    monkeypatch.setenv("ECOLEAK_USE_MOCK_DATA", "true")
    assert type(default_data_source()).__name__ == "MockDataSource"


def test_force_real_without_dsn_raises(monkeypatch):
    monkeypatch.setenv("ECOLEAK_USE_MOCK_DATA", "false")
    with pytest.raises(ValueError):
        default_data_source()


def test_legacy_dsn_presence_still_selects_sql(monkeypatch, tmp_path):
    monkeypatch.setenv("ECOLEAK_SQL_DSN", f"sqlite+pysqlite:///{tmp_path / 'legacy.db'}")
    assert type(default_data_source()).__name__ == "SQLActivityDataSource"


def test_explicit_mock_override_wins_over_dsn(tmp_path):
    engine = build_engine(use_mock_data=True, dsn=f"sqlite+pysqlite:///{tmp_path / 'x.db'}")
    assert type(engine.data_source).__name__ == "MockDataSource"


def test_explicit_dsn_selects_sql(tmp_path):
    engine = build_engine(dsn=f"sqlite+pysqlite:///{tmp_path / 'x.db'}")
    assert type(engine.data_source).__name__ == "SQLActivityDataSource"
