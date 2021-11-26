from pyrogram import Client, filters, emoji
from pyrogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from freqtrade.rpc.signaler import Signaler
from freqtrade.rpc.signaler_database import SignalerUser
from freqtrade.rpc.signaler_messages import APPROVAL_MESSAGE, MENTION, WHOIS_MESSAGE
from freqtrade.rpc.signaler_plugins.helper import extract_user_id, return_status_icon
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
            logger.warning('rpc.signaler received an approval demand from a spamming user!')
            await message.reply_text("Your approval request is currently being reviewed.")
        else:
            logger.warning('rpc.signaler received an approval demand from an already approved user!')
            await message.reply_text(f"You are already approved! {emoji.CHECK_MARK}")


@Client.on_callback_query(filters.regex("approve"))
@Client.on_message(filters.command(["approve"]))
async def approve_handler(client: Client, message: Union[Message, CallbackQuery]):
    """
    Handles the approval of a user
    """
    if SignalerUser.allow_owners_only(message.from_user.id, "approve"):
        was_command = await client.get_users(message.command[1]) if isinstance(message, Message) else None
        user_demanding = SignalerUser.get_user(await extract_user_id(message.data)) if was_command is None\
            else SignalerUser.get_user(was_command.id)
        if user_demanding:
            if not user_demanding.is_allowed:
                user_demanding.allow_user()
                for owner in SignalerUser.get_owners():
                    await client.send_message(owner.user_id,
                                              text=f"{user_demanding.user_name} was approved to use this bot!")
            else:
                logger.warning('rpc.signaler tried to approve a user that was already approved!')
                if was_command is None:
                    await message.reply_text(f"That user is already approved {emoji.CHECK_MARK}")
                else:
                    await message.edit_message_text(f"That user is already approved {emoji.CHECK_MARK}")
        else:
            logger.warning('rpc.signaler tried to approve a user that was missing in the DB!')


@Client.on_callback_query(filters.regex("deny"))
@Client.on_message(filters.command(["deny"]))
async def deny_handler(client: Client, message: Union[CallbackQuery, Message]):
    """
    Handles the removal of access to a user
    """
    if SignalerUser.allow_owners_only(message.from_user.id, "deny"):
        was_command = await client.get_users(message.command[1]) if isinstance(message, Message) else None
        user_demanding = SignalerUser.get_user(await extract_user_id(message.data)) if was_command is None \
            else SignalerUser.get_user(was_command.id)
        if user_demanding:
            if user_demanding.is_allowed and not user_demanding.is_owner:
                user_demanding.disallow_user()
                for owner in SignalerUser.get_owners():
                    await client.send_message(owner.user_id,
                                              text=f"{user_demanding.user_name} was denied from using this bot!"
                                                   f" {emoji.CROSS_MARK}")
            elif user_demanding.is_allowed and user_demanding.is_owner:
                # TO-DO Never allow removing the 'main bot owner' (get value in freq conf)
                logger.warning(f'rpc.signaler is removing {user_demanding.user_name} from the owners!')
                user_demanding.disallow_user()
                for owner in SignalerUser.get_owners():
                    await client.send_message(owner.user_id,
                                              text=f"{user_demanding.user_name} is no longer a owner of this bot!"
                                                   f" {emoji.CROSS_MARK}")
            else:
                logger.warning('rpc.signaler tried to deny a user that wasn''t approved!')
                if was_command is None:
                    await message.reply_text("That user isn't approved")
                else:
                    await message.edit_message_text("That user isn't approved")
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
            whois_info = WHOIS_MESSAGE.format(
                (user_to_whois.first_name + " " + user_to_whois.last_name
                 if user_to_whois.last_name else user_to_whois.first_name),
                user_to_whois.id,
                user_to_whois.id,
                user_to_whois.first_name,
                user_to_whois.last_name,
                user_to_whois.username,
                user_to_whois.status,
                signaler_user.join_date.date(),
                (emoji.CHECK_BOX_WITH_CHECK if signaler_user.is_allowed else emoji.CROSS_MARK),
                (emoji.CROWN if signaler_user.is_owner else emoji.CROSS_MARK),
                ((emoji.ANGRY_FACE + emoji.WARNING) if user_to_whois.is_scam else emoji.BABY_ANGEL)
            )
            # Generate the keyboard based on query data
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            "Back to demand", callback_data=f"demand{user_id}"
                        )
                    ]
                ]
            ) if "list" not in message.data else InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            "Back to user list", callback_data=f"listusers"
                        )
                    ]
                ]
            )
            await message.edit_message_text(text=whois_info, reply_markup=keyboard)


@Client.on_message(filters.command(["listusers"]))
@Client.on_callback_query(filters.regex("listusers"))
async def listusers_handler(client: Client, message: Union[Message, CallbackQuery]):
    if SignalerUser.allow_owners_only(message.from_user.id, "listusers"):
        users = SignalerUser.get_users()
        reply_text = "**====Freqtrade Signaler Users====**\n"
        owners_text = "**==========Owners============**\n"
        approved_users_text = "**=======Approved Users========**\n"
        denied_users_text = "**=======Denied Users==========**\n"
        pending_users_text = "**========Pending Users========**\n"
        keyboard = []
        for user in users:
            tg_user = await client.get_users(user.user_id)
            keyboard = keyboard + [[
                InlineKeyboardButton(f"Whois {user.user_name}", callback_data=f"whois{user.user_id}list")
            ]]
            if user.is_owner:
                owners_text += f"{emoji.CROWN} {MENTION.format(user.user_name, user.user_id)} " \
                               f"({await return_status_icon(tg_user)}):\n"
            elif user.is_allowed:
                approved_users_text += f"{emoji.CHECK_MARK} {MENTION.format(user.user_name, user.user_id)} " \
                                       f"({await return_status_icon(tg_user)})\n"
            elif not user.is_allowed and user.has_demanded:
                denied_users_text += f"{emoji.CROSS_MARK} {MENTION.format(user.user_name, user.user_id)} " \
                                     f"({await return_status_icon(tg_user)})\n"
            else:
                pending_users_text += f"{emoji.QUESTION_MARK} {MENTION.format(user.user_name, user.user_id)} " \
                                      f"({await return_status_icon(tg_user)})\n"
        if any(char.isdigit() for char in owners_text):
            reply_text += owners_text
        if any(char.isdigit() for char in approved_users_text):
            reply_text += approved_users_text
        if any(char.isdigit() for char in denied_users_text):
            reply_text += denied_users_text
        if any(char.isdigit() for char in pending_users_text):
            reply_text += pending_users_text
        if isinstance(message, CallbackQuery):
            await message.edit_message_text(text=reply_text, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            logger.info(f'rpc.signaler sending user list to {message.from_user.username}')
            await message.reply_text(text=reply_text, reply_markup=InlineKeyboardMarkup(keyboard))
