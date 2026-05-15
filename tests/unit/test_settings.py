import pytest

from tape_service.settings import Settings


def test_settings_loads_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/db")
    monkeypatch.setenv("SESSION_SECRET", "x" * 40)
    s = Settings()
    assert str(s.database_url).startswith("postgresql://")
    assert s.session_cookie_name == "s3p_session"
    assert s.session_absolute_ttl_days == 30
    assert s.session_idle_ttl_days == 14
    assert s.login_rate_limit_per_ip == 10
    assert s.login_rate_limit_window_seconds == 300


def test_settings_rejects_short_secret(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/db")
    monkeypatch.setenv("SESSION_SECRET", "short")
    with pytest.raises(ValueError):
        Settings()
