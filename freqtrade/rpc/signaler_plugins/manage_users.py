from pyrogram import Client, filters, emoji
from pyrogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from freqtrade.rpc.signaler_database import SignalerUser
from freqtrade.rpc.signaler_messages import APPROVAL_MESSAGE, MENTION
from freqtrade.rpc.signaler_plugins.helper import extract_user_id
from typing import Union
import logging

logger = logging.getLogger(__name__)


@Client.on_message(filters.command(["demand"]))
@Client.on_callback_query(filters.regex("demand"))
async def demand_handler(client: Client, message: Union[Message, CallbackQuery]):
    """
    Handles the demand command (which sends an approval request to all owners)
    """
    if isinstance(message, CallbackQuery):
        user_id = await extract_user_id(message.data)
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        "Approve", callback_data=f"approve{user_id}"
                    ),
                    InlineKeyboardButton(
                        "Deny", callback_data=f"deny{user_id}"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "Who is", callback_data=f"whois{user_id}"
                    ),
                ],
            ]
        )
        user = await client.get_users(await extract_user_id(message.data))
        user_mention = MENTION.format(user.first_name, user.id)
        text = APPROVAL_MESSAGE.format(emoji.WARNING, user_mention, emoji.WARNING)
        await message.edit_message_text(text=text, reply_markup=keyboard)
    else:
        # Check both is_allowed and has_demanded. If both are False this is the first time this user is asking
        if not SignalerUser.user_is_allowed(message.from_user.id) \
                and not SignalerUser.user_has_demanded(message.from_user.id):
            owners = SignalerUser.get_owners()
            if owners:
                logger.info(f'rpc.signaler received a approval demand from {message.chat.id}')
                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                "Approve", callback_data=f"approve{message.from_user.id}"
                            ),
                            InlineKeyboardButton(
                                "Deny", callback_data=f"deny{message.from_user.id}"
                            ),
                        ],
                        [
                            InlineKeyboardButton(
                                "Who is", callback_data=f"whois{message.from_user.id}"
                            ),
                        ],
                    ]
                )
                user = await client.get_users(message.from_user.id)
                signaler_user = SignalerUser.get_user(message.from_user.id)
                signaler_user.just_demanded()
                user_mention = MENTION.format(user.first_name, user.id)
                text = APPROVAL_MESSAGE.format(emoji.WARNING, user_mention, emoji.WARNING)
                for owner in owners:
                    await client.send_message(owner.user_id,
                                              text=text, reply_markup=keyboard)
                await message.reply_text(f"Sent approval request to {[(o.user_name + ' ') for o in owners]}")
            else:
                logger.warning(f'No owner in the signaler database!')
                await message.reply_text("This bot seems abandonned...")
        elif SignalerUser.user_has_demanded(message.from_user.id):
            logger.warning('rpc.signaler received a approval demand from a spamming user!')
        else:
            logger.warning('rpc.signaler received a approval demand from an already approved user!')


@Client.on_callback_query(filters.regex("approve"))
async def approve_handler(client: Client, message: Union[Message, CallbackQuery]):
    """
    Handles the approval of a user
    """
    if SignalerUser.allow_owners_only(message.from_user.id, "approve"):
        user_demanding = SignalerUser.get_user(await extract_user_id(message.data))
        if user_demanding:
            user_demanding.allow_user()
            for owner in SignalerUser.get_owners():
                await client.send_message(owner.user_id,
                                          text=f"{user_demanding.user_name} was approved to use this bot!")
        else:
            logger.warning('rpc.signaler tried to approve a user that was missing in the DB!')


@Client.on_callback_query(filters.regex("deny"))
async def deny_handler(client: Client, message: CallbackQuery):
    """
    Handles the removal of access to a user
    """
    if SignalerUser.allow_owners_only(message.from_user.id, "deny"):
        user_demanding = SignalerUser.get_user(await extract_user_id(message.data))
        if user_demanding:
            user_demanding.deny_user()
            for owner in SignalerUser.get_owners():
                await client.send_message(owner.user_id,
                                          text=f"{user_demanding.user_name} was denied to use this bot!")
        else:
            logger.warning('rpc.signaler tried to deny a user that was missing in the DB!')


@Client.on_callback_query(filters.regex("whois"))
async def whois_handler(client: Client, message: CallbackQuery):
    """
    Handles the whois query given by owners during approval process
    """
    if SignalerUser.allow_owners_only(message.from_user.id, "whois"):
        user_id = await extract_user_id(message.data)
        user_to_whois = await client.get_users(user_id)
        signaler_user = SignalerUser.get_user(user_id)
        if user_to_whois and signaler_user:
            whois_info = f"Telegram: {MENTION.format(user_to_whois.first_name, user_to_whois.id)} \n"
            whois_info += f"Signaler join date : {signaler_user.join_date}"
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            "Back to demand", callback_data=f"demand{user_id}"
                        )
                    ]
                ]
            )
            await message.edit_message_text(text=whois_info, reply_markup=keyboard)
