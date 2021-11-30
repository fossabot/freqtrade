from pyrogram import filters, emoji, Client
from pyrogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from freqtrade.rpc.signaler import Signaler
from freqtrade.rpc.signaler_database import SignalerUser, SPAMMER_LEVEL_COOLDOWNS
from freqtrade.rpc.signaler_messages import APPROVAL_MESSAGE, MENTION, WHOIS_MESSAGE, USER_MENU_MARKUP
from freqtrade.rpc.signaler_plugins.helper import extract_user_id, return_status_icon, return_spammer_icon
from typing import Union
from functools import wraps
import datetime
import logging
import asyncio

logger = logging.getLogger(__name__)


def prevent_spam(
        can_increase_spammer_level: bool = True,
        send_warning_reply: bool = True
):
    """
    Decorator to handle spammers
    :param can_increase_spammer_level: If the cooldown is not respected, can the user raise his spammer level
    :param send_warning_reply: Send the user a warning about his spamming
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(
                client: Client, message: Union[CallbackQuery, Message]
        ):
            signaler_user = SignalerUser.get_user(message.from_user.id)
            if not signaler_user.is_owner:
                if signaler_user.last_command_received is not None:  # Not the first command received from user
                    spammer_cooldown = SPAMMER_LEVEL_COOLDOWNS.get(signaler_user.spammer_level, None)
                    if spammer_cooldown is not None:  # Spammer level is under 4
                        command_should_be_after = signaler_user.last_command_received + datetime.timedelta(
                            seconds=spammer_cooldown)
                        time_difference = (command_should_be_after - datetime.datetime.utcnow())
                        signaler_user.set_last_command_received()
                        if time_difference.total_seconds() < spammer_cooldown:
                            if can_increase_spammer_level:
                                signaler_user.increase_spammer_level()
                            if send_warning_reply:
                                replied_msg = await client.send_message(message.from_user.id,
                                                          f"Command was denied,"
                                                          f" you have a command cooldown of {spammer_cooldown}!")
                                logger.info(f'rpc.signaler sent a warning to {signaler_user.user_name}')
                                await tick_down(replied_msg, spammer_cooldown)
                        else:  # Command respected cooldown
                            signaler_user.reset_spammer_level()
                            await func(client, message)
                    else:  # a user with a spammer_cooldown of None means above 3, so we deny those!
                        if signaler_user.spammer_level == 4:  # only send warning to owners once
                            spammer_mention = MENTION.format(message.from_user.username, message.from_user.id)
                            signaler_user.disallow_user()
                            signaler_user.increase_spammer_level()
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
                            for owner in SignalerUser.get_owners():
                                print(f'sent message to {owner.user_name} about spammer')
                                await client.send_message(owner.user_id,
                                                          text=f"{spammer_mention} "
                                                               f" just reached spammer level 4!"
                                                               f"{emoji.WARNING}!"
                                                               f"He is now denied",
                                                          reply_markup=keyboard)
                            if send_warning_reply:
                                await client.send_message(message.from_user.id,
                                                          f"{emoji.WARNING} Command was denied, you reached spammer "
                                                          f"level 4!"
                                                          f" {emoji.WARNING}")
                else:
                    signaler_user.set_last_command_received()
                    await func(client, message)
            else:
                # owners are exempted from spamming checks
                signaler_user.reset_spammer_level()
                signaler_user.set_last_command_received()
                await func(client, message)

        return wrapper

    return decorator


async def tick_down(message: Message, delay: int):
    if delay > 0:
        delay -= 1
        message_text = message.text
        current_second_value = ''.join(x for x in message_text if x.isdigit())
        await asyncio.sleep(1)
        next_value_to_show = str(int(current_second_value) - 1)
        reply = await message.edit_text(message_text.replace(current_second_value, next_value_to_show))
        await tick_down(reply, delay)
    else:
        await message.edit_text(f"{emoji.B_BUTTON_BLOOD_TYPE}I AM NOW READY FOR YO SPAM{emoji.B_BUTTON_BLOOD_TYPE}")


@Signaler.on_message(filters.command(["demand"]))
@Signaler.on_callback_query(filters.regex("demand"))
@prevent_spam()
async def demand_handler(client: Signaler, message: Union[Message, CallbackQuery]):
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
                owner_names = {[(o.user_name + ' ') for o in owners]}
                await message.reply_text(f"Sent approval request to {owner_names}")
            else:
                logger.warning(f'No owner in the signaler database!')
                await message.reply_text("This bot seems abandonned...")
        elif SignalerUser.user_has_demanded(message.from_user.id):
            logger.warning('rpc.signaler received an approval demand from a spamming user!')
            await message.reply_text("Your approval request is currently being reviewed.")
        else:
            logger.warning('rpc.signaler received an approval demand from an already approved user!')
            await message.reply_text(f"You are already approved! {emoji.CHECK_MARK}")


@Signaler.on_callback_query(filters.regex("approve"))
@Signaler.on_message(filters.command(["approve"]))
async def approve_handler(client: Signaler, message: Union[Message, CallbackQuery]):
    """
    Handles the approval of a user
    """
    if len(message.command) <= 1 and isinstance(message, Message):
        await message.reply_text(f"Missing username argument {emoji.WARNING}\n"
                                 f"Usage: /approve username", parse_mode='html')
    elif SignalerUser.allow_owners_only(message.from_user.id, "approve"):
        was_command = await client.get_users(message.command[1]) if isinstance(message, Message) else None
        user_demanding = SignalerUser.get_user(await extract_user_id(message.data)) if was_command is None \
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


@Signaler.on_callback_query(filters.regex("deny"))
@Signaler.on_message(filters.command(["deny"]))
async def deny_handler(client: Signaler, message: Union[CallbackQuery, Message]):
    """
    Handles the removal of access to a user
    """
    if len(message.command) <= 1 and isinstance(message, Message):
        await message.reply_text(f"Missing username argument {emoji.WARNING}\n"
                                 f"Usage: /deny username")
    elif SignalerUser.allow_owners_only(message.from_user.id, "deny"):
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


@Signaler.on_callback_query(filters.regex("whois"))
async def whois_handler(client: Signaler, message: CallbackQuery):
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
                await return_status_icon(user_to_whois),
                signaler_user.join_date.date(),
                (emoji.CHECK_BOX_WITH_CHECK if signaler_user.is_allowed else emoji.CROSS_MARK),
                (emoji.CROWN if signaler_user.is_owner else emoji.CROSS_MARK),
                await return_spammer_icon(signaler_user)

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
            await message.answer()
            await message.edit_message_text(text=whois_info, reply_markup=keyboard)


@Signaler.on_message(filters.command(["listusers"]))
@Signaler.on_callback_query(filters.regex("listusers"))
@prevent_spam()
async def listusers_handler(client: Signaler, message: Union[Message, CallbackQuery]):
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
            logger.info(f'rpc.signaler sending user list to {SignalerUser.get_user(message.from_user.id).user_name}')
            await message.reply_text(text=reply_text, reply_markup=InlineKeyboardMarkup(keyboard))


@Signaler.on_message(filters.command(["owner", "setowner"]))
@prevent_spam()
async def owner_handler(client: Signaler, message: Message):
    """
    Handles the owner/setowner command
    """
    if len(message.command) <= 1:
        await message.reply_text(f"Missing username argument {emoji.WARNING}\n"
                                 f"Usage: /owner username")
    elif SignalerUser.allow_owners_only(message.from_user.id, "owner"):
        user_demanded = SignalerUser.get_user(message.command[1])
        keyboard = [] + [[
            InlineKeyboardButton(f"Whois {user_demanded.user_name}",
                                 callback_data=f"whois{user_demanded.user_id}list")
        ]]
        if user_demanded:
            if not user_demanded.is_owner:
                user_demanded.set_owner()
                for owner in SignalerUser.get_owners():
                    await client.send_message(owner.user_id,
                                              text=f"{MENTION.format(user_demanded.user_name, user_demanded.user_id)}"
                                                   f" was promoted to owner of this bot"
                                                   f"{emoji.PARTY_POPPER}!",
                                              reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                await message.reply_text(f"That user is already owner {emoji.CHECK_MARK}",
                                         reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            logger.warning('rpc.signaler tried to setowner on a user that was missing in the DB!')
    else:
        out_of_bounds_user = SignalerUser.get_user(message.from_user.id)
        keyboard = [] + [[
            InlineKeyboardButton(f"Whois {out_of_bounds_user.user_name}?",
                                 callback_data=f"whois{out_of_bounds_user.user_id}list")
        ]]
        for owner in SignalerUser.get_owners():
            await client.send_message(owner.user_id,
                                      text=f"{MENTION.format(out_of_bounds_user.user_name, out_of_bounds_user.user_id)}"
                                           f" is using the /owner command when not permitted"
                                           f"{emoji.WARNING}!",
                                      reply_markup=InlineKeyboardMarkup(keyboard))


@Signaler.on_message(filters.command(["disown", "unsetowner"]))
@prevent_spam()
async def disown_handler(client: Signaler, message: Message):
    """
    Handles the disown/unsetowner command
    """
    if len(message.command) <= 1:
        await message.reply_text(f"Missing username argument {emoji.WARNING}\n"
                                 f"Usage: /disown username")
    elif SignalerUser.allow_owners_only(message.from_user.id, "disown"):
        user_demanded = SignalerUser.get_user(message.command[1])
        user_to_query = await client.get_users(user_demanded.user_id)

        if user_demanded:
            keyboard = [] + [[
                InlineKeyboardButton(f"Whois {user_demanded.user_name}?",
                                     callback_data=f"whois{user_demanded.user_id}list")
            ]]
            if user_demanded.is_owner:
                user_demanded.disallow_user()
                await client.send_message(user_to_query.id,
                                          f"Sorry but "
                                          f"{MENTION.format(message.from_user.username, message.from_user.id)}"
                                          f" has removed you from this bot's owners list{emoji.WARNING}",
                                          reply_markup=USER_MENU_MARKUP)
                for owner in SignalerUser.get_owners():
                    await client.send_message(owner.user_id,
                                              text=f"{MENTION.format(user_demanded.user_name, user_demanded.user_id)}"
                                                   f" was removed from the owners of this bot"
                                                   f"{emoji.STOP_SIGN}!",
                                              reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                await message.reply_text(f"That user is not owner {emoji.CROSS_MARK}",
                                         reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            logger.warning('rpc.signaler tried to disown a user that was missing in the DB!')
