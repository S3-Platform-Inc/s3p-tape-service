import pytest

from tape_service.settings import Settings


def test_settings_loads_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/db")
    monkeypatch.setenv("REDIS_URL", "redis://:pw@h:6379/0")
    monkeypatch.setenv("SESSION_SECRET", "x" * 40)
    s = Settings()
    assert str(s.database_url).startswith("postgresql://")
    assert str(s.redis_url).startswith("redis://")
    assert s.session_cookie_name == "s3p_session"
    assert s.session_absolute_ttl_days == 30
    assert s.session_idle_ttl_days == 14
    assert s.login_rate_limit_per_ip == 10
    assert s.login_rate_limit_window_seconds == 300


def test_settings_rejects_short_secret(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/db")
    monkeypatch.setenv("REDIS_URL", "redis://:pw@h:6379/0")
    monkeypatch.setenv("SESSION_SECRET", "short")
    with pytest.raises(ValueError):
        Settings()


def test_cors_allow_origins_defaults_to_empty(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/db")
    monkeypatch.setenv("REDIS_URL", "redis://:pw@h:6379/0")
    monkeypatch.setenv("SESSION_SECRET", "x" * 40)
    monkeypatch.delenv("CORS_ALLOW_ORIGINS", raising=False)
    s = Settings()
    assert s.cors_allow_origins == []


def test_cors_allow_origins_parses_json_array(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/db")
    monkeypatch.setenv("REDIS_URL", "redis://:pw@h:6379/0")
    monkeypatch.setenv("SESSION_SECRET", "x" * 40)
    monkeypatch.setenv(
        "CORS_ALLOW_ORIGINS",
        '["https://score.s3platform.ru","https://other.example"]',
    )
    s = Settings()
    assert s.cors_allow_origins == [
        "https://score.s3platform.ru",
        "https://other.example",
    ]


def test_samesite_none_is_accepted(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/db")
    monkeypatch.setenv("REDIS_URL", "redis://:pw@h:6379/0")
    monkeypatch.setenv("SESSION_SECRET", "x" * 40)
    monkeypatch.setenv("SESSION_COOKIE_SAMESITE", "None")
    s = Settings()
    assert s.session_cookie_samesite == "none"
