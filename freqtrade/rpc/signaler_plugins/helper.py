import logging
from typing import Union
from pyrogram import emoji
from pyrogram.types import User

logger = logging.getLogger(__name__)


async def extract_user_id(query: Union[str, bytes, None]) -> int:
    """
    Helper function to extract user_id from callback queries
    """
    return int(''.join(c for c in query if c.isdigit()))


async def return_status_icon(user: User):
    """
    Helper function to return emoji based on telegram User status
    """
    if user.status == "online"\
            or user.status == "recently":
        return emoji.GREEN_CIRCLE
    elif user.status == "offline"\
            or user.status == "within_week":
        return emoji.RED_CIRCLE
    else:
        return emoji.HOLLOW_RED_CIRCLE
