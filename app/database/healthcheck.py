import asyncio

from sqlalchemy.exc import SQLAlchemyError

from app.config import get_settings
from app.database.session import create_async_engine_from_settings, ping_database
from app.logging_config import configure_logging


async def async_main() -> int:
    settings = get_settings()
    configure_logging(settings.log_level)
    engine = create_async_engine_from_settings(settings)

    try:
        await ping_database(engine)
    except SQLAlchemyError as exc:
        print(f"PostgreSQL connection failed: {exc}")
        return 1
    finally:
        await engine.dispose()

    print("PostgreSQL connection OK")
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(async_main()))


if __name__ == "__main__":
    main()
