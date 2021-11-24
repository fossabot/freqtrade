import logging

from pyrogram import Client, filters
from pyrogram.types import Message
from freqtrade.rpc.signaler_database import SignalerUser

logger = logging.getLogger(__name__)


@Client.on_message(filters.command(["approve"]))
async def approve_user(_, message: Message):
    user = SignalerUser.get_user(message.from_user.id)
    if not user:
        logger.warning('rpc signaler tried to approve someone that is not in the DB!'
                       f'({user.user_name})')
        await message.reply_text(f"Could not find {user.user_name} in the signaler database!")
    elif user.is_allowed:
        logger.warning('rpc signaler tried to approve someone already approved!'
                       f'({user.user_name})')
    return None
