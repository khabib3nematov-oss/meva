from app.config import Settings


def test_database_url_is_built_from_postgres_settings() -> None:
    settings = Settings(
        _env_file=None,
        use_sqlite=False,
        bot_token="123456:test-token",
        postgres_host="db",
        postgres_port=5432,
        postgres_user="mevachi",
        postgres_password="secret",
        postgres_db="mevachi",
    )

    assert (
        settings.sqlalchemy_database_url
        == "postgresql+asyncpg://mevachi:secret@db:5432/mevachi"
    )


def test_database_url_normalizes_postgresql_driver() -> None:
    settings = Settings(
        _env_file=None,
        use_sqlite=False,
        database_url="postgresql://user:pass@localhost:5432/db",
    )

    assert (
        settings.sqlalchemy_database_url
        == "postgresql+asyncpg://user:pass@localhost:5432/db"
    )
