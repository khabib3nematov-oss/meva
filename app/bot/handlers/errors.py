import logging

from aiogram import Router
from aiogram.types import ErrorEvent


logger = logging.getLogger(__name__)
router = Router(name=__name__)


@router.errors()
async def handle_errors(event: ErrorEvent) -> bool:
    logger.error(
        "telegram_update_failed",
        exc_info=(
            type(event.exception),
            event.exception,
            event.exception.__traceback__,
        ),
    )
    return True
