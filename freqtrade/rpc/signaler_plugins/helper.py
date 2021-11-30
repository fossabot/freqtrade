import logging
from typing import Union
from freqtrade.rpc.signaler import Signaler
from freqtrade.rpc.signaler_database import SignalerUser
from pyrogram import emoji, filters
from pyrogram.types import User, Message

logger = logging.getLogger(__name__)


async def extract_user_id(query: Union[str, bytes, None]) -> int:
    """
    Helper function to extract user_id from callback queries
    """
    return int(''.join(c for c in query if c.isdigit()))


async def return_status_icon(user: User) -> str:
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


async def return_spammer_icon(user: SignalerUser) -> str:
    """
    Helper function to return emoji based on SignalerUser spammer level
    """
    if user.spammer_level == 0:
        return f"{emoji.BABY_ANGEL} Lv0"
    elif user.spammer_level == 1:
        return f"{emoji.YELLOW_CIRCLE} Lv1"
    elif user.spammer_level == 2:
        return f"{emoji.ORANGE_CIRCLE} Lv2"
    elif user.spammer_level == 3:
        return f"{emoji.RED_CIRCLE} Lv3"
    else:
        return f"{emoji.BUS_STOP}{emoji.WARNING}"


@Signaler.on_message(filters.command(['help']))
async def help_message(client: Signaler, message: Message):
    user_demanding = SignalerUser.get_user(message.from_user.id)
    if user_demanding:
        if user_demanding.is_owner:
            await message.reply_text("**Owners Help menu missing for now!**")
        elif user_demanding.is_allowed:
            await message.reply_text("**Allowed Users Help menu missing for now!**")
        elif not user_demanding.is_allowed and user_demanding.has_demanded:
            await message.reply_text("**Denied Users Help menu missing for now!**")
        else:  # user has not demanded and is not approved either
            await message.reply_text("**Pending User Help menu missing for now!**")
    else:
        logger.warning('rpc.signaler tried to send help to a user that was missing in the DB!')
